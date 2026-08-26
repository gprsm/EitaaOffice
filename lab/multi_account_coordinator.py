"""Offline laboratory coordinator for operator-owned, isolated account workers.

This module deliberately has no Eitaa client import and no RPC execution API.
It only validates isolation and creates an idempotent assignment plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class AccountWorkerSpec:
    account_id: str
    scheduler_id: str
    session_path: Path
    database_path: Path
    diagnostics_path: Path
    max_tasks_per_plan: int = 1
    cooldown_until: datetime | None = None

    def validate(self) -> None:
        if not self.account_id.strip() or not self.scheduler_id.strip():
            raise ValueError("Account and scheduler IDs are required.")
        if self.max_tasks_per_plan < 1:
            raise ValueError("Worker capacity must be positive.")
        paths = (
            self.session_path.expanduser().resolve(),
            self.database_path.expanduser().resolve(),
            self.diagnostics_path.expanduser().resolve(),
        )
        if len(set(paths)) != len(paths):
            raise ValueError("A worker's session, database, and diagnostics paths must differ.")
        if self.cooldown_until is not None and self.cooldown_until.tzinfo is None:
            raise ValueError("Cooldown timestamp must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class RecipientTask:
    task_id: str
    recipient_key: str
    sendable: bool = True
    opt_out: bool = False

    def validate(self) -> None:
        if not self.task_id.strip() or not self.recipient_key.strip():
            raise ValueError("Task and recipient keys are required.")


@dataclass(frozen=True, slots=True)
class Assignment:
    account_id: str
    scheduler_id: str
    task_id: str
    recipient_key: str


@dataclass(frozen=True, slots=True)
class AssignmentPlan:
    assignments: tuple[Assignment, ...]
    omitted_opt_out: tuple[str, ...]
    omitted_not_sendable: tuple[str, ...]
    omitted_duplicates: tuple[str, ...]
    unassigned_capacity: tuple[str, ...]


class IsolatedAccountCoordinator:
    """Partition tasks; worker processes remain solely responsible for RPCs."""

    def __init__(self, workers: Sequence[AccountWorkerSpec]) -> None:
        if not workers:
            raise ValueError("At least one account worker is required.")
        for worker in workers:
            worker.validate()
        if len({worker.account_id for worker in workers}) != len(workers):
            raise ValueError("Account IDs must be unique.")
        if len({worker.scheduler_id for worker in workers}) != len(workers):
            raise ValueError("Every account must own a distinct scheduler.")
        for attribute in ("session_path", "database_path", "diagnostics_path"):
            resolved = [getattr(worker, attribute).expanduser().resolve() for worker in workers]
            if len(set(resolved)) != len(resolved):
                raise ValueError(f"Workers must not share {attribute}.")
        all_paths = [
            path.expanduser().resolve()
            for worker in workers
            for path in (worker.session_path, worker.database_path, worker.diagnostics_path)
        ]
        if len(set(all_paths)) != len(all_paths):
            raise ValueError("No session, database, or diagnostics path may be reused across workers.")
        self._workers = tuple(sorted(workers, key=lambda item: item.account_id))

    def plan(
        self,
        tasks: Iterable[RecipientTask],
        *,
        now: datetime | None = None,
    ) -> AssignmentPlan:
        selected_now = now or datetime.now(timezone.utc)
        if selected_now.tzinfo is None:
            raise ValueError("Planning timestamp must be timezone-aware.")
        available = [
            worker
            for worker in self._workers
            if worker.cooldown_until is None or worker.cooldown_until <= selected_now
        ]
        capacities = {worker.account_id: worker.max_tasks_per_plan for worker in available}
        assignments: list[Assignment] = []
        omitted_opt_out: list[str] = []
        omitted_not_sendable: list[str] = []
        omitted_duplicates: list[str] = []
        unassigned: list[str] = []
        seen_recipients: set[str] = set()
        cursor = 0
        for task in tasks:
            task.validate()
            if task.opt_out:
                omitted_opt_out.append(task.task_id)
                continue
            if not task.sendable:
                omitted_not_sendable.append(task.task_id)
                continue
            if task.recipient_key in seen_recipients:
                omitted_duplicates.append(task.task_id)
                continue
            seen_recipients.add(task.recipient_key)
            eligible = [worker for worker in available if capacities[worker.account_id] > 0]
            if not eligible:
                unassigned.append(task.task_id)
                continue
            worker = eligible[cursor % len(eligible)]
            cursor += 1
            capacities[worker.account_id] -= 1
            assignments.append(
                Assignment(
                    account_id=worker.account_id,
                    scheduler_id=worker.scheduler_id,
                    task_id=task.task_id,
                    recipient_key=task.recipient_key,
                )
            )
        return AssignmentPlan(
            assignments=tuple(assignments),
            omitted_opt_out=tuple(omitted_opt_out),
            omitted_not_sendable=tuple(omitted_not_sendable),
            omitted_duplicates=tuple(omitted_duplicates),
            unassigned_capacity=tuple(unassigned),
        )
