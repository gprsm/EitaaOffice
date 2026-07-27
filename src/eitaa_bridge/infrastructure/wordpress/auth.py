from __future__ import annotations

import os
from dataclasses import dataclass

from ...config import WordPressSiteConfig
from ...errors import CredentialError


@dataclass(slots=True, frozen=True)
class WordPressCredentials:
    username: str
    application_password: str

    def validate(self) -> None:
        if not self.username.strip():
            raise CredentialError("WordPress username is missing.")
        if not self.application_password.strip():
            raise CredentialError("WordPress Application Password is missing.")

    def safe_summary(self) -> dict[str, object]:
        return {
            "username_present": bool(self.username),
            "application_password_present": bool(self.application_password),
        }


def require_wordpress_credentials(
    site: WordPressSiteConfig, credentials: WordPressCredentials
) -> WordPressCredentials:
    """Validate credentials only when an authenticated WordPress call begins."""
    try:
        credentials.validate()
    except CredentialError as exc:
        raise CredentialError(
            "WordPress credentials are missing from the configured environment variables.",
            safe_context={
                "site_key": site.site_key,
                "username_env": site.username_env,
                "application_password_env": site.application_password_env,
                **credentials.safe_summary(),
            },
        ) from exc
    return credentials


def load_wordpress_credentials(
    site: WordPressSiteConfig, *, required: bool = True
) -> WordPressCredentials:
    credentials = WordPressCredentials(
        username=os.environ.get(site.username_env, ""),
        application_password=os.environ.get(site.application_password_env, ""),
    )
    return require_wordpress_credentials(site, credentials) if required else credentials
