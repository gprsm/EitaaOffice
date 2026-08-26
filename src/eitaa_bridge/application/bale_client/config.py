from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class BaleConfig:
    grpc_base_url: str = "https://next-ws.bale.ai"
    ws_url: str = "wss://next-ws.bale.ai/ws/"
    origin: str = "https://web.bale.ai"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    )
    proto_version: int = 1
    api_version: int = 151_668
    auth_app_id: int = 4
    auth_api_key: str = "C28D46DC4C3A7A26564BFCC48B929086A95C93C98E789A19847BEE8627DE4E7D"
    send_code_type: int = 3
    language: str = "fa"
    client_label: str = "Bale Web"
    rpc_timeout: float = 30.0
    handshake_timeout: float = 15.0
    ping_interval: float = 10.0
    liveness_timeout: float = 35.0
    presence_interval: float = 90.0
    reconnect_max_delay: float = 30.0
    vault_path: Path = Path("data/session.vault")
    log_path: Path = Path("data/bale_client.log")


SERVICES: dict[str, str] = {
    "auth": "bale.auth.v1.Auth",
    "messaging": "bale.messaging.v2.Messaging",
    "stream": "bale.maviz.v1.MavizStream",
    "presence": "bale.presence.v1.Presence",
    "users": "bale.users.v1.Users",
    "files": "ai.bale.server.Files",
    "groups": "bale.groups.v1.Groups",
    "report": "bale.report.v1.Report",
    "configs": "bale.v1.Configs",
    "meet": "bale.meet.v1.Meet",
}
