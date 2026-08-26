from __future__ import annotations

import json

from eitaa_bridge.infrastructure.diagnostics import BridgeDiagnosticManager, mask_phone, redact


def test_redacts_secret_and_content():
    result = redact({"authorization": "Basic abc", "content": "private post", "token": "secret"})
    assert "Basic abc" not in json.dumps(result)
    assert "private post" not in json.dumps(result)
    assert "secret" not in json.dumps(result)


def test_masks_phone():
    masked = mask_phone("+989361234567")
    assert masked.startswith("+989")
    assert masked.endswith("4567")
    assert "123" not in masked


def test_manager_writes_safe_manifest_and_component(tmp_path):
    manager = BridgeDiagnosticManager(tmp_path)
    manager.emit("wordpress", "test", fields={"username": "editor", "body": "hello"})
    content = manager.file_for("wordpress").read_text(encoding="utf-8")
    assert "editor" not in content
    assert "hello" not in content
    manifest = json.loads((manager.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["security"]["wordpress_credentials_written"] is False
    assert manifest["security"]["message_or_post_content_written"] is False


def test_prune_old_diagnostic_runs_keeps_current_and_newest(tmp_path):
    import os
    import time
    from eitaa_bridge.infrastructure.diagnostics import prune_old_diagnostic_runs

    root = tmp_path / "diagnostics"
    root.mkdir()
    current = root / "current"
    current.mkdir()
    (current / "manifest.json").write_text("{}")
    old = root / "old"
    old.mkdir()
    (old / "manifest.json").write_text("{}")
    recent = root / "recent"
    recent.mkdir()
    (recent / "manifest.json").write_text("{}")
    stale = time.time() - 60 * 86400
    os.utime(old, (stale, stale))

    result = prune_old_diagnostic_runs(
        root,
        protected_run_ids={"current"},
        keep_newest=1,
        max_age_days=30,
    )
    assert current.exists()
    assert recent.exists()
    assert not old.exists()
    assert result["removed"] == 1
