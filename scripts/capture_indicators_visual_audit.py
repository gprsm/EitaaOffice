"""Visual Acceptance Runner for Macro & Micro Indicators and Message Splitting Control Bar
Captures live screenshots of:
- Control bar under Eitaa message cards:
  * "تفکیک پیام" button on integrated/grouped messages.
  * Macro indicator (bold with pencil icon).
  * Micro indicators (different color, non-bold, trailing pencil icon).
- Popovers for selecting macro indicators and editing/typing micro indicators.
- Split message dialog.
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
OUTPUT_DIR = ROOT / ".rtl-acceptance" / "visual-audit-indicators"
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


async def run_visual_audit():
    print("=== Step 1: Issuing Fresh Live Admin Session ===")
    token, csrf = issue_admin_session()
    print(f"Session token generated successfully: {token[:12]}...")

    temp_profile = Path(os.environ["TEMP"]) / "edge_visual_audit_indicators_profile"
    if temp_profile.exists():
        shutil.rmtree(temp_profile, ignore_errors=True)

    print("=== Step 2: Starting Edge Headless with CDP ===")
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

            # Set session cookie for local bridge origin
            await cdp.send("Network.setCookie", {
                "name": "eitaa_bridge_app_session",
                "value": token,
                "url": "http://127.0.0.1:8765/",
            })

            # =========================================================
            # SCENARIO 1: Desktop Workspace & Message Card with Control Bar (1440x900)
            # =========================================================
            print("\n--- 1. Desktop: Workspace & Chat Timeline with Indicator Bars ---")
            await cdp.set_viewport(1440, 900, mobile=False, scale=1.0)
            await cdp.send("Page.navigate", {"url": "http://127.0.0.1:8765/"})

            await asyncio.sleep(4.0)

            # Wait for workspace layout
            rendered = await cdp.wait_for_selector('aside, [aria-label="فهرست گفتگوها"]', timeout=20.0)
            print(f"Workspace loaded: {rendered}")
            await asyncio.sleep(1.0)

            # Select the Cultural Liaison conversation ("رابطان فرهنگی دادگستری استان مازندران")
            selected_dialog = await cdp.eval("""(() => {
                const buttons = Array.from(document.querySelectorAll('.MuiListItemButton-root, div[role="button"]'));
                for (const b of buttons) {
                    if (b.innerText && b.innerText.includes('رابطان فرهنگی')) {
                        b.scrollIntoView({ block: 'center' });
                        b.click();
                        return b.innerText.slice(0, 50);
                    }
                }
                // Fallback to 4th item if text didn't match directly
                if (buttons.length >= 4) {
                    buttons[3].click();
                    return 'clicked_item_index_3: ' + buttons[3].innerText.slice(0, 50);
                }
                return null;
            })()""")
            print(f"Selected conversation: {selected_dialog}")
            await asyncio.sleep(4.0)

            # Wait for messages cards
            cards_count = await cdp.eval("document.querySelectorAll('.MuiCard-root, article').length")
            print(f"Cards count loaded in DOM: {cards_count}")

            # Check if indicator bar text is found in DOM
            indicator_info = await cdp.eval("""(() => {
                const text = document.body.innerText;
                const hasMacro = text.includes('شاخصه کلی');
                const hasMicro = text.includes('شاخصه‌های جزئی');
                const hasSplit = text.includes('تفکیک پیام');
                const bars = Array.from(document.querySelectorAll('*')).filter(el => 
                    el.textContent && el.textContent.includes('شاخصه کلی')
                );
                const splitButtons = Array.from(document.querySelectorAll('button')).filter(b => 
                    b.textContent && b.textContent.includes('تفکیک پیام')
                );
                return {
                    hasMacro,
                    hasMicro,
                    hasSplit,
                    bars_count: bars.length,
                    split_buttons_count: splitButtons.length
                };
            })()""")
            print(f"Indicator info in DOM: {indicator_info}")

            # Scroll down to a nice message card
            await cdp.eval("""(() => {
                const card = document.querySelector('article, .MuiCard-root');
                if (card) card.scrollIntoView({ behavior: 'instant', block: 'center' });
            })()""")
            await asyncio.sleep(1.0)

            await cdp.capture_screenshot("08_desktop_chat_timeline_with_indicators")

            # =========================================================
            # SCENARIO 2: Click Macro Indicator Pencil / Select Popover
            # =========================================================
            print("\n--- 2. Clicking Macro Indicator to open Popover ---")
            macro_clicked = await cdp.eval("""(() => {
                const pencilBtn = document.querySelector('button[aria-label="اصلاح شاخصه کلی"]');
                if (pencilBtn) {
                    pencilBtn.scrollIntoView({ behavior: 'instant', block: 'center' });
                    pencilBtn.click();
                    return 'clicked';
                }
                const macroSpan = Array.from(document.querySelectorAll('span')).find(s => s.textContent && s.textContent.includes('شاخصه کلی'));
                if (macroSpan) {
                    macroSpan.scrollIntoView({ behavior: 'instant', block: 'center' });
                    macroSpan.click();
                    return 'clicked_span';
                }
                return 'not_found';
            })()""")
            print(f"Macro button clicked: {macro_clicked}")
            await asyncio.sleep(1.5)
            await cdp.capture_screenshot("09_desktop_macro_indicator_select_popover")

            # Close popover cleanly by clicking 'انصراف'
            await cdp.eval("""(() => {
                const cancelBtn = Array.from(document.querySelectorAll('.MuiDialogActions-root button')).find(b => b.textContent && b.textContent.includes('انصراف')) ||
                                 document.querySelector('.MuiDialog-root button[aria-label="بستن"]');
                if (cancelBtn) cancelBtn.click();
            })()""")
            await asyncio.sleep(1.5)

            # =========================================================
            # SCENARIO 3: Micro Indicators Edit & Management Modal Save
            # =========================================================
            print("\n--- 3. Clicking Micro Indicator to open Popover ---")
            micro_clicked = await cdp.eval("""(() => {
                const pencilBtn = document.querySelector('button[aria-label="اصلاح شاخصه‌های جزئی"]');
                if (pencilBtn) {
                    pencilBtn.scrollIntoView({ behavior: 'instant', block: 'center' });
                    pencilBtn.click();
                    return 'clicked';
                }
                return 'not_found';
            })()""")
            print(f"Micro edit button clicked: {micro_clicked}")
            await asyncio.sleep(1.5)

            # Click "مدیریت عناوین شاخصه‌های جزئی..." in the popover
            mgmt_clicked = await cdp.eval("""(() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const mgmtBtn = buttons.find(b => b.textContent && b.textContent.includes('مدیریت عناوین شاخصه‌های جزئی'));
                if (mgmtBtn) {
                    mgmtBtn.click();
                    return 'clicked';
                }
                return 'not_found';
            })()""")
            print(f"Management modal clicked: {mgmt_clicked}")
            await asyncio.sleep(2.0)

            # In the Management Modal, type a new micro indicator title and click "افزودن"
            test_title = f"پویش استانی نماز {datetime.now().strftime('%H%M%S')}"
            add_result = await cdp.eval(f"""(() => {{
                const input = document.querySelector('input[placeholder*="عنوان شاخصه جزئی"]');
                if (!input) return 'input_not_found';
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeInputValueSetter.call(input, {json.dumps(test_title)});
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                
                const addBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.trim() === 'افزودن');
                if (!addBtn) return 'btn_not_found';
                addBtn.click();
                return 'added';
            }})()""")
            print(f"Added new micro indicator: {add_result}")
            # Wait for addition to complete and list to refresh
            await asyncio.sleep(3.5)

            # Verify no security error ("درخواست امنیتی معتبر نیست") and title appears in list
            verification = await cdp.eval(f"""(() => {{
                const text = document.body.innerText;
                const hasError = text.includes('درخواست امنیتی معتبر نیست');
                const hasItem = text.includes({json.dumps(test_title)});
                const errorBox = document.querySelector('.MuiAlert-message, [role="alert"]')?.textContent || null;
                return {{
                    hasError,
                    hasItem,
                    errorBox,
                }};
            }})()""")
            print(f"Micro indicator save verification: {verification}")
            await cdp.capture_screenshot("11_desktop_micro_indicators_management_modal")

            if verification.get("hasError"):
                raise RuntimeError("CSRF / Security Error detected when saving micro indicator!")

            # Close management modal cleanly using the DialogActions close button
            await cdp.eval("""(() => {
                const actionsBtns = Array.from(document.querySelectorAll('.MuiDialogActions-root button'));
                const closeBtn = actionsBtns.find(b => b.textContent && b.textContent.trim() === 'بستن');
                if (closeBtn) closeBtn.click();
            })()""")
            await asyncio.sleep(2.0)

            # Ensure modal is gone, or press Escape
            await cdp.eval("""(() => {
                const openDialogs = document.querySelectorAll('.MuiDialog-root');
                if (openDialogs.length > 0) {
                    const backdrop = document.querySelector('.MuiBackdrop-root');
                    if (backdrop) backdrop.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
                }
            })()""")
            await asyncio.sleep(1.0)

            # =========================================================
            # SCENARIO 4: Re-open Popover & Assign Micro Indicator to Message Card
            # =========================================================
            print("\n--- 4. Assigning Micro Indicator to Message Card ---")
            await cdp.eval("""(() => {
                const pencilBtn = document.querySelector('button[aria-label="اصلاح شاخصه‌های جزئی"]');
                if (pencilBtn) {
                    pencilBtn.scrollIntoView({ behavior: 'instant', block: 'center' });
                    pencilBtn.click();
                }
            })()""")
            await asyncio.sleep(2.0)

            # Pick a chip from the popover (e.g. 'زیارت عاشورا' or click first chip)
            assign_chip = await cdp.eval("""(() => {
                const chips = Array.from(document.querySelectorAll('.MuiDialog-root .MuiChip-root'));
                const chip = chips.find(c => c.textContent && c.textContent.includes('زیارت عاشورا')) || chips[0];
                if (chip) {
                    chip.click();
                    return 'clicked_chip: ' + chip.textContent;
                }
                return 'no_chip_found';
            })()""")
            print(f"Assigned chip action: {assign_chip}")
            await asyncio.sleep(1.0)

            # Click "ذخیره شاخصه‌ها" in the popover
            save_msg = await cdp.eval("""(() => {
                const buttons = Array.from(document.querySelectorAll('.MuiDialog-root button'));
                const saveBtn = buttons.find(b => b.textContent && b.textContent.includes('ذخیره شاخصه‌ها'));
                if (saveBtn) {
                    saveBtn.click();
                    return 'clicked_save';
                }
                return 'not_found';
            })()""")
            print(f"Save message indicators clicked: {save_msg}")
            await asyncio.sleep(2.5)

            # Scroll card into view
            await cdp.eval("""(() => {
                const card = document.querySelector('article, .MuiCard-root');
                if (card) card.scrollIntoView({ behavior: 'instant', block: 'center' });
            })()""")
            await asyncio.sleep(1.0)

            await cdp.capture_screenshot("12_desktop_message_with_saved_micro_indicator")

            # =========================================================
            # SCENARIO 5: Click Split Message Button
            # =========================================================
            print("\n--- 5. Testing 'تفکیک پیام' dialog ---")
            split_clicked = await cdp.eval("""(() => {
                const splitBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('تفکیک پیام'));
                if (splitBtn) {
                    splitBtn.scrollIntoView({ behavior: 'instant', block: 'center' });
                    splitBtn.click();
                    return 'clicked';
                }
                return 'no_grouped_message_split_btn';
            })()""")
            print(f"Split button click result: {split_clicked}")
            if split_clicked == 'clicked':
                await asyncio.sleep(1.5)
                await cdp.capture_screenshot("10_desktop_split_message_dialog")

            print("\n=== Visual Audit Completed Successfully ===")

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3.0)
        except Exception:
            pass
        if temp_profile.exists():
            shutil.rmtree(temp_profile, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(run_visual_audit())
