from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH_SOURCE = ROOT / "ui" / "src" / "ui33-runtime-patch.js"
INDEX = ROOT / "ui" / "dist" / "index.html"
FINALIZER = ROOT / "ui" / "scripts" / "finalize-ui-build.mjs"
DOMAIN = ROOT / "src" / "eitaa_bridge" / "domain" / "composer.py"
WORKFLOW = ROOT / "src" / "eitaa_bridge" / "application" / "workflows" / "compose_wordpress_post.py"


def test_wordpress_success_exposes_only_verified_committed_source_keys():
    domain = DOMAIN.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    patch = PATCH_SOURCE.read_text(encoding="utf-8")

    assert '"confirmed_source_keys"' in domain
    assert "composition_usage_commit_unverified" in workflow
    assert "composition_publication_commit_unverified" in workflow
    assert "composition_source_index_unverified" in workflow
    assert "self._verify_committed_sources" in workflow
    assert "confirmed_source_keys" in patch
    assert "rememberConfirmedSources" in patch
    assert "eitaa-bridge:usage-confirmed" in patch
    assert "ui33-confirmed-fallback" in patch
    assert "stopImmediatePropagation" in patch


def test_runtime_patch_is_loaded_before_frozen_application_bundle_and_is_reproducible():
    source = PATCH_SOURCE.read_bytes()
    index = INDEX.read_text(encoding="utf-8")
    match = re.search(r'ui33-runtime-patch-([0-9a-f]{16})\.js', index)

    assert match is not None
    dist = (ROOT / "ui" / "dist" / "assets" / match.group(0)).read_bytes()
    assert source == dist
    assert source
    assert match.group(1) == hashlib.sha256(source).hexdigest()[:16]
    assert "ui33-runtime-patch.js" not in index
    assert not (ROOT / "ui" / "dist" / "assets" / "ui33-runtime-patch.js").exists()
    patch_position = index.index(match.group(0))
    main_position = index.index('type="module"')
    assert patch_position < main_position


def test_runtime_patch_build_uses_content_hash_cache_busting():
    finalizer = FINALIZER.read_text(encoding="utf-8")

    assert "createHash('sha256')" in finalizer
    assert "ui33-runtime-patch-${patchHash}.js" in finalizer
    assert "const distPatch = path.join(assetsDir, 'ui33-runtime-patch.js')" not in finalizer
    assert 'src="./assets/ui33-runtime-patch.js"' not in finalizer


def test_reading_position_is_local_bounded_throttled_and_idle_persisted():
    patch = PATCH_SOURCE.read_text(encoding="utf-8")

    assert "eitaa-bridge.ui.reading-positions.v1" in patch
    assert "const MAX_POSITIONS = 120" in patch
    assert "const SAVE_DELAY_MS = 2500" in patch
    assert "requestIdleCallback" in patch
    assert "firstVisibleId" in patch
    assert "lastVisibleId" in patch
    assert "anchorKey" in patch
    assert "anchorOffset" in patch
    assert "requestIdleCallback" in patch
    assert "MAX_USAGE = 2000" in patch


def test_unread_point_overrides_remembered_position_and_saved_location_remains_available():
    patch = PATCH_SOURCE.read_text(encoding="utf-8")

    unread_branch = "Number(dialog?.unread_count || 0) > 0 && unread"
    remembered_branch = "Number(dialog?.unread_count || 0) <= 0 && checkpoint?.anchorKey"
    assert unread_branch in patch
    assert remembered_branch in patch
    assert patch.index(unread_branch) < patch.index(remembered_branch)
    assert "ادامه از آخرین موقعیت" in patch


def test_saved_reading_position_never_rewrites_the_latest_message_request():
    patch = PATCH_SOURCE.read_text(encoding="utf-8")
    fetch_wrapper = patch[patch.index("window.fetch = async"):patch.index("const rowForKey")]

    assert "originalFetch(input, init)" in fetch_wrapper
    assert "body.before_id =" not in fetch_wrapper
    assert "body.limit =" not in fetch_wrapper
    assert "checkpoint?.lastVisibleId" not in fetch_wrapper


def test_runtime_patch_does_not_add_network_writes_for_reading_positions():
    patch = PATCH_SOURCE.read_text(encoding="utf-8")
    position_section = patch[patch.index("const saveCheckpoint"):patch.index("const bindScroll")]
    assert "fetch(" not in position_section
    assert "originalFetch" not in position_section
    assert "localStorage" not in position_section  # persistence is delayed through the shared scheduler
    assert "schedulePositionSave()" in position_section
