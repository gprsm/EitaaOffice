from __future__ import annotations

import asyncio
import json
import queue
import threading
import tkinter as tk
from dataclasses import asdict, is_dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Coroutine

from .client import BaleClient
from .config import BaleConfig
from .models import Peer, PeerType


class AsyncWorker:
    def __init__(self, root: tk.Tk, on_result, on_error) -> None:
        self.root = root
        self.on_result = on_result
        self.on_error = on_error
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro: Coroutine[Any, Any, Any]) -> None:
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)

        def done(fut) -> None:
            try:
                result = fut.result()
            except BaseException as exc:
                self.root.after(0, self.on_error, exc)
            else:
                self.root.after(0, self.on_result, result)

        future.add_done_callback(done)

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)


class BaleLab(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bale Personal Client Lab v0.1.0")
        self.geometry("1180x820")
        self.minsize(920, 680)
        self.client: BaleClient | None = None
        self.client_passphrase: str | None = None
        self.worker = AsyncWorker(self, self._show_result, self._show_error)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build()

    def _build(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Vault passphrase:").pack(side="left")
        self.passphrase = ttk.Entry(top, show="•", width=30)
        self.passphrase.pack(side="left", padx=5)
        ttk.Button(top, text="Load session", command=self.load_session).pack(side="left", padx=3)
        ttk.Button(top, text="Connect", command=self.connect).pack(side="left", padx=3)
        ttk.Button(top, text="Disconnect", command=self.disconnect).pack(side="left", padx=3)
        self.status = ttk.Label(top, text="Disconnected")
        self.status.pack(side="right")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0, 5))
        self.auth_tab = ttk.Frame(notebook, padding=10)
        self.chat_tab = ttk.Frame(notebook, padding=10)
        self.rpc_tab = ttk.Frame(notebook, padding=10)
        notebook.add(self.auth_tab, text="Authentication")
        notebook.add(self.chat_tab, text="Messaging & contacts")
        notebook.add(self.rpc_tab, text="Raw RPC Lab")
        self._build_auth()
        self._build_chat()
        self._build_rpc()

        logbar = ttk.Frame(self, padding=(8, 0, 8, 5))
        logbar.pack(fill="x")
        ttk.Label(logbar, text="Log (selectable and copyable):").pack(side="left")
        ttk.Button(logbar, text="Copy all", command=self.copy_log).pack(side="right", padx=3)
        ttk.Button(logbar, text="Save log", command=self.save_log).pack(side="right", padx=3)
        ttk.Button(logbar, text="Clear", command=lambda: self.log.delete("1.0", "end")).pack(side="right", padx=3)
        self.log = tk.Text(self, height=18, wrap="none", font=("Consolas", 10))
        self.log.pack(fill="both", expand=False, padx=8, pady=(0, 8))
        scroll = ttk.Scrollbar(self.log, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)

    def _build_auth(self) -> None:
        frame = self.auth_tab
        self.phone = self._row(frame, 0, "Phone (+98...):")
        ttk.Button(frame, text="Start phone auth", command=self.auth_start).grid(row=0, column=2, padx=5)
        self.transaction = self._row(frame, 1, "Transaction hash:", width=65)
        self.code = self._row(frame, 2, "OTP code:")
        ttk.Button(frame, text="Validate code", command=self.auth_code).grid(row=2, column=2, padx=5)
        self.password = self._row(frame, 3, "Two-step password:", show="•")
        ttk.Button(frame, text="Validate password", command=self.auth_password).grid(row=3, column=2, padx=5)
        self.first_name = self._row(frame, 4, "First name:")
        self.last_name = self._row(frame, 5, "Last name:")
        ttk.Button(frame, text="Sign up", command=self.auth_signup).grid(row=5, column=2, padx=5)
        self.jwt = self._row(frame, 6, "JWT (optional import):", width=65, show="•")
        ttk.Button(frame, text="Exchange JWT", command=self.exchange_jwt).grid(row=6, column=2, padx=5)
        self.access_token = self._row(frame, 7, "access_token import:", width=65, show="•")
        ttk.Button(frame, text="Import token", command=self.import_token).grid(row=7, column=2, padx=5)
        ttk.Label(
            frame,
            text=(
                "For safety, tokens are written only to the encrypted vault and are not copied into the visible log."
            ),
        ).grid(row=8, column=0, columnspan=3, sticky="w", pady=15)

    def _build_chat(self) -> None:
        frame = self.chat_tab
        self.peer_id = self._row(frame, 0, "Peer ID:")
        ttk.Label(frame, text="Peer type:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        self.peer_type = ttk.Combobox(frame, values=["1 - Private", "2 - Group"], state="readonly", width=25)
        self.peer_type.set("1 - Private")
        self.peer_type.grid(row=1, column=1, sticky="w")
        self.peer_hash = self._row(frame, 2, "Access hash (optional):")
        self.message = self._row(frame, 3, "Text:", width=65)
        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=3, sticky="w", pady=8)
        for label, command in [
            ("Send text", self.send_text),
            ("Load history", self.history),
            ("Load dialogs", self.dialogs),
            ("Typing", self.typing),
            ("Stop typing", self.stop_typing),
            ("Get contacts", self.contacts),
        ]:
            ttk.Button(buttons, text=label, command=command).pack(side="left", padx=3)
        self.message_id = self._row(frame, 5, "Message ID:")
        self.message_date = self._row(frame, 6, "Message date:")
        ttk.Button(frame, text="Edit with text above", command=self.edit_message).grid(row=5, column=2, padx=5)
        ttk.Button(frame, text="Delete message", command=self.delete_message).grid(row=6, column=2, padx=5)
        self.contact_query = self._row(frame, 7, "Contact query / phone:", width=40)
        cbuttons = ttk.Frame(frame)
        cbuttons.grid(row=8, column=0, columnspan=3, sticky="w", pady=8)
        ttk.Button(cbuttons, text="Search", command=self.search_contact).pack(side="left", padx=3)
        ttk.Button(cbuttons, text="Add user ID", command=self.add_contact).pack(side="left", padx=3)
        ttk.Button(cbuttons, text="Remove user ID", command=self.remove_contact).pack(side="left", padx=3)

    def _build_rpc(self) -> None:
        frame = self.rpc_tab
        self.service = self._row(frame, 0, "Service:", width=55)
        self.service.insert(0, "bale.messaging.v2.Messaging")
        self.method = self._row(frame, 1, "Method:", width=40)
        self.method.insert(0, "LoadFolders")
        ttk.Label(frame, text="JSON field specification:").grid(row=2, column=0, sticky="ne", padx=5, pady=4)
        self.spec = tk.Text(frame, width=85, height=16, font=("Consolas", 10))
        self.spec.grid(row=2, column=1, columnspan=2, sticky="nsew")
        self.spec.insert("1.0", "[]")
        ttk.Button(frame, text="Execute raw RPC", command=self.raw_rpc).grid(row=3, column=1, sticky="w", pady=8)
        ttk.Button(frame, text="Open JSON", command=self.open_spec).grid(row=3, column=1, padx=140, sticky="w", pady=8)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)

    @staticmethod
    def _row(parent, row: int, label: str, *, width: int = 35, show: str | None = None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="e", padx=5, pady=4)
        entry = ttk.Entry(parent, width=width, show=show or "")
        entry.grid(row=row, column=1, sticky="w", padx=5, pady=4)
        return entry

    async def _get_client(self, phrase: str) -> BaleClient:
        if not phrase:
            raise ValueError("Vault passphrase is required")
        if self.client is None or self.client_passphrase != phrase:
            if self.client is not None:
                await self.client.close()
            self.client = BaleClient(BaleConfig(), passphrase=phrase)
            self.client_passphrase = phrase
        return self.client

    def _submit(self, operation) -> None:
        self.status.configure(text="Working…")
        phrase = self.passphrase.get()

        async def runner():
            client = await self._get_client(phrase)
            return await operation(client)

        self.worker.submit(runner())

    def load_session(self) -> None:
        async def op(client):
            session = client.load_session()
            return {"session_loaded": True, "user_id": session.user_id, "expires_at": session.expires_at}
        self._submit(op)

    def connect(self) -> None:
        async def op(client):
            if client.session is None:
                client.load_session()
            await client.connect()
            return {"connected": True, "proto": client.ws.server_proto_version, "api": client.ws.server_api_version}
        self._submit(op)

    def disconnect(self) -> None:
        async def op(client):
            await client.disconnect()
            return {"connected": False}
        self._submit(op)

    def auth_start(self) -> None:
        phone = self.phone.get()
        async def op(client):
            result = await client.auth.start_phone_auth(phone)
            self.after(0, lambda: (self.transaction.delete(0, "end"), self.transaction.insert(0, result.transaction_hash)))
            return result
        self._submit(op)

    def auth_code(self) -> None:
        transaction, code = self.transaction.get(), self.code.get()
        async def op(client):
            outcome = await client.auth_code(transaction, code)
            return {
                "session_saved": outcome.session is not None,
                "password_required": outcome.password_required,
                "signup_required": outcome.signup_required,
            }
        self._submit(op)

    def auth_password(self) -> None:
        transaction, password = self.transaction.get(), self.password.get()
        self._submit(lambda client: client.auth_password(transaction, password))

    def auth_signup(self) -> None:
        transaction = self.transaction.get()
        first_name, last_name = self.first_name.get(), self.last_name.get()
        self._submit(lambda client: client.auth_signup(transaction, first_name, last_name))

    def exchange_jwt(self) -> None:
        jwt = self.jwt.get()
        self._submit(lambda client: client.exchange_and_save_jwt(jwt))

    def import_token(self) -> None:
        access_token, jwt = self.access_token.get(), self.jwt.get() or None
        async def op(client):
            session = client.import_access_token(access_token, jwt=jwt)
            return {"session_saved": True, "user_id": session.user_id}
        self._submit(op)

    def _peer(self) -> Peer:
        ptype = int(self.peer_type.get().split()[0])
        return Peer(
            id=int(self.peer_id.get()),
            type=PeerType(ptype),
            access_hash=int(self.peer_hash.get()) if self.peer_hash.get() else None,
        )

    async def _connected(self, client: BaleClient) -> BaleClient:
        if client.session is None:
            client.load_session()
        if client.ws is None or not client.ws.connected:
            await client.connect()
        return client

    def send_text(self) -> None:
        peer, text = self._peer(), self.message.get()
        async def op(client):
            await self._connected(client)
            return await client.send_text(peer, text)
        self._submit(op)

    def history(self) -> None:
        peer = self._peer()
        async def op(client):
            await self._connected(client)
            return await client.load_history(peer, limit=30)
        self._submit(op)

    def dialogs(self) -> None:
        async def op(client):
            await self._connected(client)
            return await client.load_dialogs(limit=30)
        self._submit(op)

    def edit_message(self) -> None:
        peer, message_id, text = self._peer(), int(self.message_id.get()), self.message.get()
        async def op(client):
            await self._connected(client)
            return await client.edit_message(peer, message_id, text)
        self._submit(op)

    def delete_message(self) -> None:
        peer = self._peer()
        message_id, message_date = int(self.message_id.get()), int(self.message_date.get())
        async def op(client):
            await self._connected(client)
            return await client.delete_message(peer, [message_id], [message_date])
        self._submit(op)

    def typing(self) -> None:
        peer = self._peer()
        async def op(client):
            await self._connected(client); return await client.typing(peer)
        self._submit(op)

    def stop_typing(self) -> None:
        peer = self._peer()
        async def op(client):
            await self._connected(client); return await client.stop_typing(peer)
        self._submit(op)

    def contacts(self) -> None:
        async def op(client):
            await self._connected(client); return await client.get_contacts()
        self._submit(op)

    def search_contact(self) -> None:
        query = self.contact_query.get()
        async def op(client):
            await self._connected(client); return await client.search_contacts(query)
        self._submit(op)

    def add_contact(self) -> None:
        user_id = int(self.contact_query.get())
        async def op(client):
            await self._connected(client); return await client.add_contact(user_id)
        self._submit(op)

    def remove_contact(self) -> None:
        user_id = int(self.contact_query.get())
        async def op(client):
            await self._connected(client); return await client.remove_contact(user_id)
        self._submit(op)

    def raw_rpc(self) -> None:
        service, method = self.service.get(), self.method.get()
        spec = json.loads(self.spec.get("1.0", "end").strip() or "[]")
        async def op(client):
            await self._connected(client)
            return await client.rpc_from_spec(service, method, spec)
        self._submit(op)

    def open_spec(self) -> None:
        filename = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if filename:
            self.spec.delete("1.0", "end")
            self.spec.insert("1.0", Path(filename).read_text(encoding="utf-8"))

    def _show_result(self, value: Any) -> None:
        self.status.configure(text="Ready")
        self._append({"ok": True, "result": value})

    def _show_error(self, exc: BaseException) -> None:
        self.status.configure(text="Error")
        self._append({"ok": False, "error_type": type(exc).__name__, "error": str(exc)})

    def _append(self, value: Any) -> None:
        def convert(obj: Any) -> Any:
            if isinstance(obj, bytes):
                return {"length": len(obj), "hex": obj.hex()}
            if is_dataclass(obj):
                return {k: convert(v) for k, v in asdict(obj).items()}
            if isinstance(obj, dict):
                return {str(k): convert(v) for k, v in obj.items() if k != "access_token" and k != "jwt"}
            if isinstance(obj, (list, tuple)):
                return [convert(v) for v in obj]
            return obj
        self.log.insert("end", json.dumps(convert(value), ensure_ascii=False, indent=2, default=str) + "\n")
        self.log.see("end")

    def copy_log(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.log.get("1.0", "end-1c"))

    def save_log(self) -> None:
        filename = filedialog.asksaveasfilename(defaultextension=".txt")
        if filename:
            Path(filename).write_text(self.log.get("1.0", "end-1c"), encoding="utf-8")

    def _close(self) -> None:
        async def shutdown():
            if self.client is not None:
                await self.client.close()
        try:
            future = asyncio.run_coroutine_threadsafe(shutdown(), self.worker.loop)
            future.result(timeout=3)
        except Exception:
            pass
        self.worker.stop()
        self.destroy()


def main() -> None:
    app = BaleLab()
    app.mainloop()


if __name__ == "__main__":
    main()
