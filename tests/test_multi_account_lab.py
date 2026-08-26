from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lab.multi_account_coordinator import (
    AccountWorkerSpec,
    IsolatedAccountCoordinator,
    RecipientTask,
)


def worker(name: str, *, cooldown: bool = False, capacity: int = 2) -> AccountWorkerSpec:
    return AccountWorkerSpec(
        account_id=name,
        scheduler_id=f"scheduler-{name}",
        session_path=Path(f"/lab/{name}/session.json"),
        database_path=Path(f"/lab/{name}/state.sqlite3"),
        diagnostics_path=Path(f"/lab/{name}/diagnostics"),
        max_tasks_per_plan=capacity,
        cooldown_until=(
            datetime.now(timezone.utc) + timedelta(hours=1) if cooldown else None
        ),
    )


def test_isolation_rejects_shared_session_path() -> None:
    first = worker("a")
    second = worker("b")
    second = AccountWorkerSpec(
        account_id=second.account_id,
        scheduler_id=second.scheduler_id,
        session_path=first.session_path,
        database_path=second.database_path,
        diagnostics_path=second.diagnostics_path,
    )
    with pytest.raises(ValueError, match="session_path"):
        IsolatedAccountCoordinator([first, second])


def test_plan_deduplicates_and_honours_safety_states_and_cooldown() -> None:
    coordinator = IsolatedAccountCoordinator([worker("a"), worker("b", cooldown=True)])
    plan = coordinator.plan(
        [
            RecipientTask("one", "+989120000001"),
            RecipientTask("duplicate", "+989120000001"),
            RecipientTask("optout", "+989120000002", opt_out=True),
            RecipientTask("blocked", "+989120000003", sendable=False),
            RecipientTask("two", "+989120000004"),
            RecipientTask("capacity", "+989120000005"),
        ]
    )
    assert [item.account_id for item in plan.assignments] == ["a", "a"]
    assert plan.omitted_duplicates == ("duplicate",)
    assert plan.omitted_opt_out == ("optout",)
    assert plan.omitted_not_sendable == ("blocked",)
    assert plan.unassigned_capacity == ("capacity",)
