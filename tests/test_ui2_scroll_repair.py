from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "ui" / "src" / "App.tsx"
MESSAGE_CARD = ROOT / "ui" / "src" / "MessageContentCard.tsx"
CSS = ROOT / "ui" / "src" / "styles.css"
SCROLL_MATH = ROOT / "ui" / "src" / "lib" / "scrollMath.ts"


def test_virtualizer_uses_stable_keys_content_estimates_and_resize_measurement():
    app = (APP.read_text(encoding="utf-8") + (APP.parent / "utils" / "helpers.tsx").read_text(encoding="utf-8"))
    scroll = SCROLL_MATH.read_text(encoding="utf-8")

    assert "getItemKey: index =>" in app
    assert "stableMessageKey(dialog.peer_key, message.id)" in app
    assert "estimateMessageRowSize(message" in app
    assert "estimateSize: () => 190" not in app
    assert "useAnimationFrameWithResizeObserver: true" in app
    assert "shouldAdjustScrollPositionOnItemSizeChange" in app
    assert "export function estimateMessageRowSize" in scroll


def test_prepend_restores_a_stable_message_anchor_instead_of_scrollheight_delta():
    app = (APP.read_text(encoding="utf-8") + (APP.parent / "utils" / "helpers.tsx").read_text(encoding="utf-8"))
    scroll = SCROLL_MATH.read_text(encoding="utf-8")

    assert "prependAnchor" in app
    assert "viewportOffset" in app
    assert "restoreMeasuredAnchor(anchor.key, anchorIndex, anchor.viewportOffset)" in app
    assert "data-message-key={key}" in app
    assert "scrollHeight - snapshot.scrollHeight" not in app
    assert "export function anchorScrollTop" in scroll


def test_auto_follow_and_pagination_have_explicit_behavioral_gates():
    app = (APP.read_text(encoding="utf-8") + (APP.parent / "utils" / "helpers.tsx").read_text(encoding="utf-8"))
    scroll = SCROLL_MATH.read_text(encoding="utf-8")

    assert "updateTopPaginationGate" in app
    assert "topPagination.current" in app
    assert "inFlight: true" in app
    assert "shouldAutoFollow(nearBottomRef.current, appended)" in app
    assert "appendedMessagesAfterTail" in app
    assert "loadOlder: () => Promise<number>" in app
    assert "TOP_PAGINATION_REARM_PX" in scroll
    assert "appended.some(message => message.outgoing)" in scroll


def test_each_dialog_preserves_its_scroll_anchor_and_loaded_message_window():
    app = (APP.read_text(encoding="utf-8") + (APP.parent / "utils" / "helpers.tsx").read_text(encoding="utf-8"))

    assert "messageScrollMemoryRef = useRef<Map<string, MessageScrollMemory>>(new Map())" in app
    assert "messageCacheRef = useRef<Map<string, MessageItem[]>>(new Map())" in app
    assert "props.scrollMemory.set(memoryKey" in app
    assert "props.scrollMemory.get(memoryKey)" in app
    assert "while (cache.size > 8)" in app
    assert "remembered?.anchorKey" in app


def test_late_media_and_status_overlays_do_not_change_scroll_flow_height():
    app = (APP.read_text(encoding="utf-8") + (APP.parent / "utils" / "helpers.tsx").read_text(encoding="utf-8"))
    message_card = MESSAGE_CARD.read_text(encoding="utf-8")

    assert "aspectRatio: gallery ? { xs: galleryTileAspectRatio(compactSpan), sm: galleryTileAspectRatio(wideSpan) }" in message_card
    assert "aspectRatio: gallery || mediaDisplay === 'framed' ? '4 / 3' : 'auto'" not in message_card
    assert "objectFit: gallery ? 'cover' : 'contain'" in message_card
    assert '<Box aria-hidden="true" sx={{ position: \'sticky\'' in app
    assert "height: 0" in app and "pointerEvents: 'none'" in app
    assert "overflowAnchor: 'none'" in app
    assert "scrollbarGutter: 'stable'" in app


def test_message_refresh_merges_and_rejects_stale_dialog_commits():
    app = (APP.read_text(encoding="utf-8") + (APP.parent / "utils" / "helpers.tsx").read_text(encoding="utf-8"))
    scroll = SCROLL_MATH.read_text(encoding="utf-8")

    assert "activeMessagePeerRef.current === selected.peer_key" in app
    assert "activeMessagePeerRef.current !== selected.peer_key" in app
    assert "mergeMessagesById(current, loaded)" in app
    assert "mergeMessagesById(current, older)" in app
    assert "export function mergeMessagesById" in scroll


def test_dialog_switch_batches_peer_and_cached_messages_before_keyed_remount():
    app = (APP.read_text(encoding="utf-8") + (APP.parent / "utils" / "helpers.tsx").read_text(encoding="utf-8"))
    conversations = (ROOT / "ui" / "src" / "ConversationListPage.tsx").read_text(encoding="utf-8")

    assert "const selectDialog = useCallback((selected: DialogItem)" in app
    assert "activeMessagePeerRef.current = selected.peer_key" in app
    assert "setMessages(messageCacheRef.current.get(selected.peer_key) || [])" in app
    assert "onSelect={selectDialog}" in app
    assert "onClick={() => onSelect(item)}" in conversations
    assert "<VirtualMessageList key={dialog.peer_key}" in app


def test_position_restore_survives_async_refresh_and_uses_measured_row_anchor():
    app = (APP.read_text(encoding="utf-8") + (APP.parent / "utils" / "helpers.tsx").read_text(encoding="utf-8"))

    assert "data-message-key={key}" in app
    assert "restoreMeasuredAnchor" in app
    assert "let completed = false" in app
    assert "positioned.current = true" in app
    assert "if (!completed)" in app
    assert "positioned.current = false" in app
