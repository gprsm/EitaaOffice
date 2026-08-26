from __future__ import annotations

import threading
import time

from eitaa_bridge.application.scheduler import EitaaOperationScheduler, EitaaPriority


def test_scheduler_runs_ready_high_priority_task_before_delayed_read() -> None:
    scheduler = EitaaOperationScheduler()
    order: list[str] = []
    read = scheduler.submit(
        priority=EitaaPriority.READ_RECEIPT,
        kind="read",
        callback=lambda: order.append("read"),
        delay_seconds=0.08,
    )
    active = scheduler.submit(
        priority=EitaaPriority.ACTIVE_MESSAGES,
        kind="messages",
        callback=lambda: order.append("messages"),
    )
    active.result(timeout=1)
    read.result(timeout=1)
    assert order == ["messages", "read"]
    scheduler.close()


def test_scheduler_serializes_operations() -> None:
    scheduler = EitaaOperationScheduler()
    gate = threading.Event()
    running = 0
    max_running = 0
    lock = threading.Lock()

    def task() -> None:
        nonlocal running, max_running
        with lock:
            running += 1
            max_running = max(max_running, running)
        gate.wait(0.05)
        with lock:
            running -= 1

    first = scheduler.submit(priority=10, kind="first", callback=task)
    second = scheduler.submit(priority=10, kind="second", callback=task)
    time.sleep(0.02)
    gate.set()
    first.result(timeout=1)
    second.result(timeout=1)
    assert max_running == 1
    scheduler.close()
