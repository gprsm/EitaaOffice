"""Error mapping for Bale Bot API."""

from ...errors import ProviderExtensionError

def map_bale_error(status_code: int) -> str:
    """Map HTTP status codes to our error taxonomy."""
    if status_code == 401:
        return "auth"
    elif status_code == 429:
        return "transient"
    elif status_code >= 500:
        return "uncertain"
    elif 400 <= status_code < 500:
        return "permanent"
    return "uncertain"
