from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from ..config import BridgeConfig
from ..domain import DoctorReport
from ..errors import BridgeError
from ..infrastructure.diagnostics import BridgeDiagnosticManager
from ..infrastructure.eitaa import CoreBinding
from ..infrastructure.wordpress import WordPressClient, load_wordpress_credentials
from ..version import __version__


class BridgeDoctor:
    def __init__(self, config: BridgeConfig, diagnostics: BridgeDiagnosticManager) -> None:
        self.config = config
        self.diagnostics = diagnostics

    def run(self, *, online: bool = False, site_key: str | None = None, open_core: bool = True) -> DoctorReport:
        site = self.config.site(site_key)
        report = DoctorReport(version=__version__, site_key=site.site_key)
        report.add("python_version", sys.version_info >= (3, 11), platform.python_version())
        report.add("python_3_13", sys.version_info[:2] == (3, 13), "recommended and validated" if sys.version_info[:2] == (3, 13) else "Python >=3.11 supported; 3.13 recommended")
        report.add("configuration", True, "schema 1 valid")
        report.add("https", site.normalized_base_url.startswith("https://") or site.allow_insecure_http, "secure URL policy valid")

        binding = CoreBinding(self.config.core, self.diagnostics)
        try:
            compatibility = binding.assert_compatible()
            report.add("core_version", True, f"{compatibility.product_version} / {compatibility.package_version}")
            report.add("core_public_facade", True, "required services present")
            report.add("core_schema", compatibility.database_schema == 9, f"schema {compatibility.database_schema}")
        except BridgeError as exc:
            report.add("core_compatibility", False, exc.code)

        session_exists = self.config.core.session_file.is_file()
        report.add("core_session_file", session_exists, "present" if session_exists else "missing")
        database_parent_ok = self._writable_parent(self.config.core.database_file)
        report.add("core_database_parent", database_parent_ok, "writable" if database_parent_ok else "not writable")
        diagnostics_ok = self._writable_directory(self.config.diagnostics.root)
        report.add("bridge_diagnostics", diagnostics_ok, "writable" if diagnostics_ok else "not writable")
        composition_state_ok = self._writable_parent(self.config.composition_state_file)
        report.add(
            "composition_state_parent", composition_state_ok,
            "writable" if composition_state_ok else "not writable",
        )
        try:
            from .api import BridgeApplicationApi
            api_ok = BridgeApplicationApi.API_VERSION == "v1"
        except Exception:
            api_ok = False
        report.add("application_api", api_ok, "local JSON API v1 available" if api_ok else "API import failed")
        ui_root = self.config.source_file.parent / "ui"
        ui_manifest_ok = (ui_root / "package.json").is_file()
        ui_build_ok = (ui_root / "dist" / "index.html").is_file()
        report.add("desktop_ui_manifest", ui_manifest_ok, "Electron UI manifest present" if ui_manifest_ok else "ui/package.json missing")
        report.add("desktop_ui_build", ui_build_ok, "production UI build present" if ui_build_ok else "run setup_ui.bat")
        report.add("publish_confirmation", True, "publish requires explicit confirmation")

        username_present = bool(os.environ.get(site.username_env, ""))
        app_password_present = bool(os.environ.get(site.application_password_env, ""))
        report.add("wordpress_username", username_present, "present" if username_present else "missing")
        report.add("wordpress_application_password", app_password_present, "present" if app_password_present else "missing")

        if open_core and session_exists:
            core = None
            try:
                core = binding.open()
                health = core.doctor()
                report.add("core_doctor", health.ok, f"{sum(1 for item in health.checks if item.ok)}/{len(health.checks)} checks passed")
                capabilities = core.capabilities()
                required = (
                    bool(capabilities.get("publication_workflow"))
                    and capabilities.get("database_schema") == 9
                    and capabilities.get("grouped_media") is True
                    and bool((capabilities.get("discovery") or {}).get("complete_pagination"))
                    and bool((capabilities.get("discovery") or {}).get("dialog_type_classification"))
                    and bool(capabilities.get("mark_read"))
                )
                report.add("core_capabilities", required, "publication workflow, grouped media, complete dialogs, server read-state, and schema 9")
            except Exception as exc:
                report.add("core_open", False, type(exc).__name__)
            finally:
                if core is not None:
                    core.close()

        if online and username_present and app_password_present:
            client = None
            try:
                credentials = load_wordpress_credentials(site)
                client = WordPressClient(site, credentials, diagnostics=self.diagnostics)
                connection = client.test_connection()
                report.add("wordpress_online", True, "authenticated REST connection succeeded")
                report.add("wordpress_edit_posts", connection.can_edit_posts, "permission present" if connection.can_edit_posts else "permission missing")
                report.add("wordpress_upload_files", connection.can_upload_files, "permission present" if connection.can_upload_files else "permission missing")
                report.add("wordpress_publish_posts", connection.can_publish_posts, "permission present" if connection.can_publish_posts else "permission missing")
            except BridgeError as exc:
                report.add("wordpress_online", False, exc.code)
            finally:
                if client is not None:
                    client.close()
        elif online:
            report.add("wordpress_online", False, "credentials missing")

        report.diagnostic_file = self.diagnostics.emit("doctor", "doctor_completed", fields=report.safe_summary())
        return report

    @staticmethod
    def _writable_directory(path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
            marker = path / ".bridge_write_test"
            marker.write_text("ok", encoding="ascii")
            marker.unlink()
            return True
        except OSError:
            return False

    @classmethod
    def _writable_parent(cls, path: Path) -> bool:
        return cls._writable_directory(path.parent)
