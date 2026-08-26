from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str

    def safe_summary(self) -> dict[str, object]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


@dataclass(slots=True)
class DoctorReport:
    version: str
    checks: list[DoctorCheck] = field(default_factory=list)
    site_key: str | None = None
    diagnostic_file: str | None = None

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append(DoctorCheck(name=name, ok=ok, detail=detail))

    def safe_summary(self) -> dict[str, object]:
        return {
            "version": self.version,
            "ok": self.ok,
            "site_key": self.site_key,
            "checks": [check.safe_summary() for check in self.checks],
            "diagnostic_file_present": self.diagnostic_file is not None,
        }
