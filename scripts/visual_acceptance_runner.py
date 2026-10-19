"""Visual Acceptance Runner for Program Catalog & Consolidated Indexing (F-128, V-294)

Captures:
1. 13_desktop_clean_message_with_two_tier_indicators:
   Shows the cultural liaisons chat timeline, confirming that conflicting 3rd layer
   NLP chips (year/month/camp) are eliminated, and only the clean 2-tier Indicators bar
   (Macro bold + pencil, Micro colored tags + pencil, and split button) is present.
2. 14_desktop_reporting_registration_catalog_step1:
   Step 1 in ReportingRegistrationPanel showing dynamic program codes from reporting_program_catalog.
3. 15_desktop_program_catalog_management_tab:
   Tab 2 ('کاتالوگ و سرفصل‌های برنامه‌ها') in JudicialUnitsManagementModal displaying official programs
   and active/archive soft-deprecation switches.
4. 16_desktop_add_edit_program_dialog:
   Add/Edit operational program dialog with multi-year validity and soft-deprecation controls.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import httpx
import websockets

from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.coordinator import CoordinatorAppAuth, AppAuthPolicy

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUTPUT_DIR = ROOT / ".rtl-acceptance" / "visual-audit-2026-10-19"
ARTIFACTS_DIR = Path(r"C:\Users\mohse\.gemini\antigravity\brain\4f838800-0d66-4edd-9a19-e3ff8d4c9497")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


class CDPClient:
    def __init__(self, ws: websockets.WebSocketClientProtocol):
        self.ws = ws
        self._next_id = 1

    async def send(self, method: str, params: dict | None = None) -> dict:
        call_id = self._next_id
        self._next_id += 1
        msg = {"id": call_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(msg))
        while True:
            raw = await self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == call_id:
                if "error" in data:
                    raise RuntimeError(f"CDP error {method}: {data['error']}")
                return data.get("result", {})

    async def eval(self, expression: str) -> any:
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        val = res.get("result", {}).get("value")
        return val

    async def wait_for_selector(self, selector: str, timeout: float = 20.0) -> bool:
        start = time.time()
        js = f'Boolean(document.querySelector({json.dumps(selector)}))'
        while time.time() - start < timeout:
            val = await self.eval(js)
            if val:
                return True
            await asyncio.sleep(0.3)
        return False

    async def wait_for_condition(self, js_expr: str, timeout: float = 20.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            val = await self.eval(f'Boolean({js_expr})')
            if val:
                return True
            await asyncio.sleep(0.3)
        return False

    async def set_viewport(self, width: int, height: int, mobile: bool = False, scale: float = 1.0):
        await self.send("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": scale,
            "mobile": mobile,
        })
        await self.send("Emulation.setVisibleSize", {"width": width, "height": height})

    async def capture_screenshot(self, name: str) -> Path:
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        data = base64.b64decode(res["data"])
        out_path = OUTPUT_DIR / f"{name}.png"
        out_path.write_bytes(data)

        artifact_path = ARTIFACTS_DIR / f"{name}.png"
        try:
            artifact_path.write_bytes(data)
        except Exception as e:
            print(f"Warning saving artifact: {e}")

        print(f"  -> [Saved Screenshot] {name}.png ({len(data):,} bytes)")
        return out_path


def issue_admin_session() -> tuple[str, str]:
    config = BridgeConfigLoader.load(ROOT / "bridge.json")
    policy_cfg = config.features.app_user_auth
    policy = AppAuthPolicy(
        idle_timeout_minutes=policy_cfg.idle_timeout_minutes,
        absolute_timeout_hours=policy_cfg.absolute_timeout_hours,
        max_failed_attempts=policy_cfg.max_failed_attempts,
        lockout_minutes=policy_cfg.lockout_minutes,
    )
    auth = CoordinatorAppAuth(ROOT / "data" / "coordinator" / "coordinator.sqlite3", policy=policy)
    with auth._connect() as conn:
        issued = auth._issue_session(
            conn,
            app_user_id="ceff0c45-adf9-4163-a843-8aecf5b4f77a",
            display_name="آخوندیان",
            global_role="admin",
            client_kind="browser",
            now=datetime.now(timezone.utc),
        )
        conn.commit()
    return issued.token, issued.csrf_token


def ensure_server():
    try:
        r = httpx.get("http://127.0.0.1:8765/api/v1/health", timeout=1.5)
        if r.status_code == 200:
            print("Background server is active on 8765.")
            return
    except Exception:
        pass
    print("Starting Background server on port 8765...")
    subprocess.run([
        str(ROOT / ".venv" / "Scripts" / "python.exe"),
        "scripts/background_server.py",
        "start"
    ], cwd=str(ROOT), check=True)


async def main():
    ensure_server()
    print("=== Step 1: Issuing Admin Session ===")
    token, csrf = issue_admin_session()

    temp_profile = Path(os.environ["TEMP"]) / "edge_catalog_audit_profile"
    if temp_profile.exists():
        shutil.rmtree(temp_profile, ignore_errors=True)

    print("=== Step 2: Launching Headless Edge with CDP ===")
    proc = subprocess.Popen([
        EDGE_PATH,
        "--headless=new",
        "--remote-debugging-port=9222",
        f"--user-data-dir={temp_profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--hide-scrollbars=false",
        "about:blank",
    ])
    time.sleep(2.5)

    try:
        targets = httpx.get("http://127.0.0.1:9222/json", timeout=5.0).json()
        page_target = [t for t in targets if t.get("type") == "page"][0]
        ws_url = page_target["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=25_000_000) as ws:
            cdp = CDPClient(ws)
            await cdp.send("Page.enable")
            await cdp.send("Runtime.enable")
            await cdp.send("Network.enable")

            # Set session cookie
            await cdp.send("Network.setCookie", {
                "name": "eitaa_bridge_app_session",
                "value": token,
                "url": "http://127.0.0.1:8765/",
            })

            # -------------------------------------------------------------
            # SCREENSHOT 13: Clean 2-tier Indicators bar on Message Card
            # -------------------------------------------------------------
            print("\n--- 1. Capturing Message Card with Clean Two-Tier Indicators ---")
            await cdp.set_viewport(1440, 900, mobile=False, scale=1.0)
            await cdp.send("Page.navigate", {"url": "http://127.0.0.1:8765/"})
            await asyncio.sleep(5.0)

            # Wait for sidebar list items to render
            await cdp.wait_for_selector('.MuiListItemButton-root', timeout=20.0)

            # Select cultural liaisons dialog ("رابطان فرهنگی")
            selected_dialog = await cdp.eval("""(() => {
                const listItems = Array.from(document.querySelectorAll('.MuiListItemButton-root'));
                const target = listItems.find(el => el.textContent.includes('رابطان فرهنگی') || el.textContent.includes('رابطین')) || listItems[0];
                if (target) {
                    target.click();
                    return target.textContent.trim().slice(0, 60);
                }
                return null;
            })()""")
            print(f"Selected conversation: {selected_dialog}")
            await cdp.wait_for_selector('.MuiCard-root', timeout=15.0)
            await asyncio.sleep(3.0)

            # Scroll to prayer message card if present, otherwise center top message card
            await cdp.eval("""(() => {
                const cards = Array.from(document.querySelectorAll('.MuiCard-root'));
                const prayerCard = cards.find(c => c.textContent.includes('نماز') || c.textContent.includes('اقامه')) || cards[0];
                if (prayerCard) {
                    prayerCard.scrollIntoView({ behavior: 'instant', block: 'center' });
                }
            })()""")
            await asyncio.sleep(1.5)
            await cdp.capture_screenshot("13_desktop_clean_message_with_two_tier_indicators")

            # -------------------------------------------------------------
            # SCREENSHOT 14: Reporting Registration Step 1 (Dynamic Catalog)
            # -------------------------------------------------------------
            print("\n--- 2. Opening Reporting Registration Panel Step 1 ---")
            reg_button_found = await cdp.eval("""(() => {
                const allButtons = Array.from(document.querySelectorAll('button'));
                const btn = allButtons.find(b => b.textContent.includes('ثبت در گزارش'));
                if (btn) {
                    btn.scrollIntoView({ behavior: 'instant', block: 'center' });
                    btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
                    btn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
                    btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    btn.click();
                    return 'clicked';
                }
                const articles = Array.from(document.querySelectorAll('article'));
                for (const art of articles) {
                    const b = Array.from(art.querySelectorAll('button')).find(x => x.textContent.includes('ثبت در گزارش'));
                    if (b) {
                        art.scrollIntoView({ behavior: 'instant', block: 'center' });
                        b.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
                        b.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
                        b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                        b.click();
                        return 'clicked_after_scroll';
                    }
                }
                return 'not_found';
            })()""")
            print(f"Registration button click result: {reg_button_found}")
            await cdp.wait_for_selector('[role="dialog"]', timeout=15.0)
            await asyncio.sleep(2.0)

            # Advance to Step 1: جزئیات برنامه و سرفصل‌ها
            print("Advancing to Step 1 (برنامه و فکت‌ها)...")
            await cdp.eval("""(() => {
                const buttons = Array.from(document.querySelectorAll('[role="dialog"] button'));
                const nextBtn = buttons.find(b => b.textContent.includes('مرحلهٔ بعد') || b.textContent.includes('بعدی'));
                if (nextBtn) {
                    nextBtn.click();
                }
            })()""")
            await asyncio.sleep(2.0)
            await cdp.capture_screenshot("14_desktop_reporting_registration_catalog_step1")

            # -------------------------------------------------------------
            # SCREENSHOT 15: Management Modal Tab 2 (Program Catalog Table)
            # -------------------------------------------------------------
            print("\n--- 3. Opening Judicial Units & Liaisons Modal -> Tab 2 Program Catalog ---")
            # Navigate back to Step 0 where "مدیریت حوزه‌ها و رابطین" button is located
            await cdp.eval("""(() => {
                const buttons = Array.from(document.querySelectorAll('[role="dialog"] button'));
                const prevBtn = buttons.find(b => b.textContent.includes('مرحلهٔ قبل') || b.textContent.includes('قبلی') || b.textContent.includes('مرحله قبل'));
                if (prevBtn) {
                    prevBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    prevBtn.click();
                }
            })()""")
            await asyncio.sleep(1.0)

            # Click "مدیریت حوزه‌ها و رابطین"
            await cdp.eval("""(() => {
                const mgmtBtn = Array.from(document.querySelectorAll('[role="dialog"] button')).find(b => b.textContent.includes('مدیریت حوزه‌ها و رابطین'));
                if (mgmtBtn) mgmtBtn.click();
            })()""")
            await cdp.wait_for_selector('[role="dialog"] [role="tablist"]', timeout=10.0)
            await asyncio.sleep(1.0)

            # Switch to Tab 2: کاتالوگ و سرفصل‌های برنامه‌ها
            print("Switching to Tab 2: کاتالوگ و سرفصل‌های برنامه‌ها...")
            await cdp.eval("""(() => {
                const tabs = Array.from(document.querySelectorAll('[role="tablist"] [role="tab"]'));
                const progTab = tabs.find(t => t.textContent.includes('کاتالوگ') || t.textContent.includes('سرفصل')) || tabs[2];
                if (progTab) progTab.click();
            })()""")

            # Wait for data to load
            print("Waiting for catalog table data to finish loading...")
            for _ in range(20):
                await asyncio.sleep(0.5)
                has_rows = await cdp.eval("""Boolean(
                    document.querySelectorAll('[role="dialog"] table tbody tr').length > 0 &&
                    !document.querySelector('[role="dialog"] .MuiCircularProgress-root')
                )""")
                if has_rows:
                    break

            await asyncio.sleep(1.5)
            await cdp.capture_screenshot("15_desktop_program_catalog_management_tab")

            # -------------------------------------------------------------
            # SCREENSHOT 16: Add / Edit Program Dialog
            # -------------------------------------------------------------
            print("\n--- 4. Clicking 'تعریف برنامه جدید' Dialog ---")
            await cdp.eval("""(() => {
                const buttons = Array.from(document.querySelectorAll('[role="dialog"] button'));
                const addBtn = buttons.find(b => b.textContent.includes('تعریف برنامه جدید'));
                if (addBtn) addBtn.click();
            })()""")
            await asyncio.sleep(1.5)
            await cdp.capture_screenshot("16_desktop_add_edit_program_dialog")

            print("\n=== All Visual Acceptance Screenshots Successfully Captured ===")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
