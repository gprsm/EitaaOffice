"""First-run Windows activation dialog and safe command-line checks."""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

from ..errors import LicenseValidationError
from ..licensing import LicenseManager


_PERSIAN_ERRORS = {
    "license_activation_required": "این دستگاه هنوز فعال نشده است.",
    "license_code_invalid": "کد فعال‌سازی نامعتبر است.",
    "license_signature_invalid": "امضای کد فعال‌سازی معتبر نیست.",
    "license_device_mismatch": "این کد برای رایانهٔ دیگری صادر شده است.",
    "license_expired": "اعتبار این مجوز پایان یافته است.",
    "license_public_key_missing": "کلید عمومی فعال‌سازی در این نسخه تنظیم نشده است.",
    "license_store_unreadable": "فایل فعال‌سازی متعلق به دستگاه دیگری است یا آسیب دیده است.",
    "license_device_identity_unavailable": "شناسهٔ پایدار دستگاه قابل دریافت نیست.",
}


def _message(error: LicenseValidationError) -> str:
    return _PERSIAN_ERRORS.get(error.code, "فعال‌سازی تأیید نشد.")


def normalize_activation_code_input(value: object) -> str:
    """Remove copy/paste formatting without changing the signed ASCII code."""

    return "".join(
        character
        for character in str(value or "")
        if not character.isspace() and unicodedata.category(character) != "Cf"
    )


def _run_dialog(manager: LicenseManager) -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        print(manager.request_code())
        return 2

    try:
        request_code = manager.request_code()
    except LicenseValidationError as exc:
        messagebox.showerror("فعال‌سازی Eitaa Bridge", _message(exc))
        return 2

    result = {"code": 2}
    window = tk.Tk()
    window.title("فعال‌سازی نسخه اختصاصی Eitaa Bridge")
    window.geometry("760x610")
    window.minsize(680, 540)
    try:
        window.iconbitmap(str(manager.root / "assets" / "EitaaBridge.ico"))
    except (OSError, tk.TclError):
        pass

    frame = tk.Frame(window, padx=20, pady=16)
    frame.pack(fill="both", expand=True)
    tk.Label(
        frame,
        text="نسخه اختصاصی Eitaa Bridge",
        font=("Segoe UI", 15, "bold"),
        anchor="e",
    ).pack(fill="x", pady=(0, 10))
    tk.Label(
        frame,
        text="فعال‌سازی فقط یک‌بار برای همین حساب ویندوز و همین رایانه انجام می‌شود.",
        font=("Segoe UI", 10),
        anchor="e",
    ).pack(fill="x", pady=(0, 14))
    tk.Label(
        frame,
        text="۱) کد درخواست زیر را کپی و برای صادرکننده ارسال کنید:",
        anchor="e",
    ).pack(fill="x")
    request_box = tk.Text(frame, height=7, wrap="char", undo=False, font=("Consolas", 9))
    request_box.insert("1.0", request_code)
    request_box.configure(background="#f3f6f9", cursor="arrow")
    request_box.pack(fill="x", pady=(6, 4))

    status_text = tk.StringVar(value="")

    def copy_text(widget: object, fallback: str = "") -> None:
        try:
            selected = widget.get("sel.first", "sel.last")
        except tk.TclError:
            selected = fallback or widget.get("1.0", "end-1c")
        window.clipboard_clear()
        window.clipboard_append(selected)
        window.update_idletasks()

    def select_all(widget: object) -> str:
        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "1.0")
        widget.see("insert")
        return "break"

    def copy_request() -> None:
        copy_text(request_box, request_code)
        status_text.set("کد درخواست در کلیپ‌بورد کپی شد.")

    def readonly_shortcut(event: object) -> str:
        control = bool(getattr(event, "state", 0) & 0x4)
        keycode = int(getattr(event, "keycode", 0) or 0)
        keysym = str(getattr(event, "keysym", "")).lower()
        if control and (keycode == 67 or keysym == "c"):
            copy_request()
        elif control and (keycode == 65 or keysym == "a"):
            return select_all(request_box)
        return "break"

    request_box.bind("<KeyPress>", readonly_shortcut)
    request_box.bind("<Control-Insert>", lambda _event: (copy_request(), "break")[1])

    request_menu = tk.Menu(window, tearoff=False)
    request_menu.add_command(label="کپی", command=copy_request)
    request_menu.add_command(label="انتخاب همه", command=lambda: select_all(request_box))
    request_box.bind(
        "<Button-3>",
        lambda event: request_menu.tk_popup(event.x_root, event.y_root),
    )

    tk.Button(frame, text="کپی کد درخواست", command=copy_request).pack(anchor="e", pady=(0, 14))
    tk.Label(
        frame,
        text="۲) کد فعال‌سازی دریافتی را با دکمه زیر جای‌گذاری کنید:",
        anchor="e",
    ).pack(fill="x")
    activation_box = tk.Text(frame, height=8, wrap="char", undo=True, font=("Consolas", 9))
    activation_box.pack(fill="both", expand=True, pady=(6, 5))

    def paste_activation() -> str:
        try:
            clipboard_value = window.clipboard_get()
        except tk.TclError:
            status_text.set("متن قابل‌خواندن در کلیپ‌بورد پیدا نشد.")
            return "break"
        selected = normalize_activation_code_input(clipboard_value)
        if not selected:
            status_text.set("کلیپ‌بورد خالی است.")
            return "break"
        activation_box.delete("1.0", "end")
        activation_box.insert("1.0", selected)
        activation_box.focus_set()
        activation_box.mark_set("insert", "end-1c")
        status_text.set("کد فعال‌سازی جای‌گذاری شد.")
        return "break"

    def activation_shortcut(event: object) -> str | None:
        control = bool(getattr(event, "state", 0) & 0x4)
        keycode = int(getattr(event, "keycode", 0) or 0)
        keysym = str(getattr(event, "keysym", "")).lower()
        if control and (keycode == 86 or keysym == "v"):
            return paste_activation()
        if control and (keycode == 65 or keysym == "a"):
            return select_all(activation_box)
        if control and (keycode == 67 or keysym == "c"):
            copy_text(activation_box)
            return "break"
        return None

    activation_box.bind("<Control-KeyPress>", activation_shortcut)
    activation_box.bind("<Shift-Insert>", lambda _event: paste_activation())

    activation_menu = tk.Menu(window, tearoff=False)
    activation_menu.add_command(label="جای‌گذاری", command=paste_activation)
    activation_menu.add_command(label="کپی", command=lambda: copy_text(activation_box))
    activation_menu.add_command(label="انتخاب همه", command=lambda: select_all(activation_box))
    activation_box.bind(
        "<Button-3>",
        lambda event: activation_menu.tk_popup(event.x_root, event.y_root),
    )

    action_row = tk.Frame(frame)
    action_row.pack(fill="x", pady=(0, 6))
    tk.Button(action_row, text="جای‌گذاری از کلیپ‌بورد", command=paste_activation).pack(side="right")
    tk.Button(
        action_row,
        text="پاک‌کردن",
        command=lambda: activation_box.delete("1.0", "end"),
    ).pack(side="right", padx=(0, 6))
    tk.Label(frame, textvariable=status_text, anchor="e", foreground="#286332").pack(fill="x")

    def activate() -> None:
        code = normalize_activation_code_input(activation_box.get("1.0", "end"))
        try:
            manager.activate(code)
        except LicenseValidationError as exc:
            messagebox.showerror("فعال‌سازی ناموفق", _message(exc), parent=window)
            return
        result["code"] = 0
        messagebox.showinfo("فعال‌سازی موفق", "این رایانه با موفقیت فعال شد.", parent=window)
        window.destroy()

    tk.Button(frame, text="تأیید و فعال‌سازی", command=activate, padx=18, pady=7).pack(anchor="e")
    window.protocol("WM_DELETE_WINDOW", window.destroy)
    window.mainloop()
    return int(result["code"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check or complete offline Eitaa Bridge activation.")
    parser.add_argument("--root", type=Path, required=True)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--request-code", action="store_true")
    actions.add_argument("--request-code-output", type=Path)
    actions.add_argument("--status-json", action="store_true")
    actions.add_argument("--activate-file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manager = LicenseManager(args.root)
    if args.check:
        return 0 if manager.status().licensed else 2
    if args.request_code:
        try:
            print(manager.request_code())
        except LicenseValidationError as exc:
            print(f"licensing: {exc.code}", file=sys.stderr)
            return 2
        return 0
    if args.request_code_output is not None:
        try:
            if args.request_code_output.exists():
                raise OSError("request output already exists")
            request_code = manager.request_code()
            args.request_code_output.parent.mkdir(parents=True, exist_ok=True)
            args.request_code_output.write_text(request_code + "\n", encoding="utf-8")
        except (OSError, LicenseValidationError) as exc:
            code = exc.code if isinstance(exc, LicenseValidationError) else "license_request_write_failed"
            print(f"licensing: {code}", file=sys.stderr)
            return 2
        return 0
    if args.status_json:
        print(json.dumps(manager.status().safe_summary(), ensure_ascii=False, indent=2))
        return 0
    if args.activate_file is not None:
        try:
            code = args.activate_file.read_text(encoding="utf-8-sig").strip()
            verified = manager.activate(code)
        except (OSError, UnicodeDecodeError, LicenseValidationError) as exc:
            code = exc.code if isinstance(exc, LicenseValidationError) else "license_file_unreadable"
            print(f"licensing: {code}", file=sys.stderr)
            return 2
        print(json.dumps(verified.safe_summary(), ensure_ascii=False, indent=2))
        return 0
    return _run_dialog(manager)


if __name__ == "__main__":
    raise SystemExit(main())
