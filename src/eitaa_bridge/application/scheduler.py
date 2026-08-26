"""Single-session priority scheduler for Eitaa operations.

The local API is served by a threaded HTTP server, but Eitaa operations share a
single mutable session file and must never overlap.  This scheduler serializes
all remote work while still allowing higher-priority UI operations to move
ahead of queued background work.
"""

from __future__ import annotations

import heapq
import itertools
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable


class EitaaPriority(IntEnum):
    """Lower values run first."""

    AUTH = 0
    ACTIVE_MESSAGES = 10
    DIALOG_PAGE = 20
    MEDIA_PREVIEW = 30
    AVATAR = 50
    BACKGROUND = 70
    READ_RECEIPT = 100


@dataclass(order=True, slots=True)
class _ScheduledTask:
    priority: int
    sequence: int
    not_before: float
    kind: str = field(compare=False)
    callback: Callable[[], Any] = field(compare=False)
    future: Future[Any] = field(compare=False)


class EitaaOperationScheduler:
    """Serialize Eitaa calls with priority and delayed low-priority work."""

    def __init__(self, *, worker_name: str = "eitaa-operation-scheduler") -> None:
        self._condition = threading.Condition(threading.RLock())
        self._queue: list[_ScheduledTask] = []
        self._sequence = itertools.count()
        self._active_priority: int | None = None
        self._active_kind: str | None = None
        self._closed = False
        self._worker_name = worker_name
        self._worker = threading.Thread(
            target=self._run,
            name=worker_name,
            daemon=True,
        )
        self._worker.start()

    def submit(
        self,
        *,
        priority: EitaaPriority | int,
        kind: str,
        callback: Callable[[], Any],
        delay_seconds: float = 0.0,
    ) -> Future[Any]:
        future: Future[Any] = Future()
        task = _ScheduledTask(
            int(priority),
            next(self._sequence),
            time.monotonic() + max(0.0, delay_seconds),
            kind,
            callback,
            future,
        )
        with self._condition:
            if self._closed:
                future.set_exception(RuntimeError("Eitaa scheduler is closed."))
                return future
            heapq.heappush(self._queue, task)
            self._condition.notify_all()
        return future

    def run_sync(
        self,
        *,
        priority: EitaaPriority | int,
        kind: str,
        callback: Callable[[], Any],
        delay_seconds: float = 0.0,
        timeout: float | None = None,
    ) -> Any:
        return self.submit(
            priority=priority,
            kind=kind,
            callback=callback,
            delay_seconds=delay_seconds,
        ).result(timeout=timeout)

    def has_higher_priority_work(self, priority: EitaaPriority | int) -> bool:
        threshold = int(priority)
        with self._condition:
            if self._active_priority is not None and self._active_priority < threshold:
                return True
            return any(task.priority < threshold and not task.future.cancelled() for task in self._queue)

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            counts: dict[str, int] = {}
            for task in self._queue:
                if task.future.cancelled():
                    continue
                counts[task.kind] = counts.get(task.kind, 0) + 1
            return {
                "worker_name": self._worker_name,
                "active_kind": self._active_kind,
                "active_priority": self._active_priority,
                "queued_count": sum(counts.values()),
                "queued_by_kind": counts,
            }

    def is_worker_thread(self) -> bool:
        return threading.current_thread() is self._worker

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            for task in self._queue:
                task.future.cancel()
            self._queue.clear()
            self._condition.notify_all()
        if threading.current_thread() is not self._worker:
            self._worker.join(timeout=5.0)

    def _pop_ready_task(self) -> _ScheduledTask | None:
        while self._queue:
            task = heapq.heappop(self._queue)
            if task.future.cancelled():
                continue
            now = time.monotonic()
            if task.not_before > now:
                heapq.heappush(self._queue, task)
                self._condition.wait(timeout=min(task.not_before - now, 0.5))
                return None
            return task
        return None

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._queue and not self._closed:
                    self._condition.wait()
                if self._closed and not self._queue:
                    return
                task = self._pop_ready_task()
                if task is None:
                    continue
                self._active_priority = task.priority
                self._active_kind = task.kind
            if not task.future.set_running_or_notify_cancel():
                with self._condition:
                    self._active_priority = None
                    self._active_kind = None
                continue
            try:
                task.future.set_result(task.callback())
            except BaseException as exc:  # Future transports the original exception
                task.future.set_exception(exc)
            finally:
                with self._condition:
                    self._active_priority = None
                    self._active_kind = None
                    self._condition.notify_all()
