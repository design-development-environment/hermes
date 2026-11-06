#!/usr/bin/env python3
"""Small Hermes User client for connecting to a Host over Tailscale.

The client deliberately stores only the Host URL. Open WebUI owns account
authentication in the browser, so passwords, API keys and local-control tokens
never leave the Host.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox
from urllib.parse import urlparse

APP_NAME = "Hermes User"
CONFIG_DIR = Path.home() / ".config" / "hermes-user"
CONFIG_FILE = CONFIG_DIR / "connection.json"
TAILSCALE_DOMAIN = re.compile(r"^[a-z0-9][a-z0-9.-]*\.ts\.net$", re.IGNORECASE)


def normalise_host(value: str) -> str:
    """Accept a Tailscale HTTPS URL or tailnet hostname and reject public URLs."""
    value = value.strip()
    if not value:
        raise ValueError("Enter the Host's Tailscale address.")
    if "://" not in value:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use an HTTPS Tailscale address, for example https://hermes.tailnet.ts.net")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Enter only the Host address, without a path or query.")
    hostname = parsed.hostname.rstrip(".")
    accepted = bool(TAILSCALE_DOMAIN.fullmatch(hostname))
    try:
        address = ipaddress.ip_address(hostname)
        accepted = accepted or address in ipaddress.ip_network("100.64.0.0/10") or address in ipaddress.ip_network("fd7a:115c:a1e0::/48")
    except ValueError:
        pass
    if not accepted:
        raise ValueError("For safety, Hermes User connects only to a Tailscale .ts.net name or Tailscale IP.")
    host = hostname if ":" not in hostname else f"[{hostname}]"
    return f"https://{host}" + (f":{parsed.port}" if parsed.port else "")


def load_host() -> str:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return normalise_host(str(data.get("host", "")))
    except (OSError, ValueError, json.JSONDecodeError):
        return ""


def save_host(host: str) -> None:
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = CONFIG_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps({"host": host}, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, CONFIG_FILE)
    CONFIG_FILE.chmod(0o600)


class HermesUser(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("520x360")
        self.resizable(False, False)
        self.configure(bg="#0d0d0d")
        self.option_add("*Font", ("Inter", 11))
        self.host = tk.StringVar(value=load_host())
        shell = tk.Frame(self, bg="#0d0d0d", padx=42, pady=38)
        shell.pack(fill="both", expand=True)
        tk.Label(shell, text="HERMES", bg="#0d0d0d", fg="#f4f4f6", font=("Inter", 25, "bold")).pack(anchor="w")
        tk.Label(shell, text="Connect to your Hermes Host", bg="#0d0d0d", fg="#f4f4f6", font=("Inter", 17, "bold")).pack(anchor="w", pady=(30, 8))
        tk.Label(shell, text="Sign into Tailscale first. Then enter your Host's private Tailscale address. You will sign in using your normal Open WebUI account.", bg="#0d0d0d", fg="#a1a1a6", justify="left", wraplength=430).pack(anchor="w", pady=(0, 22))
        tk.Label(shell, text="HERMES HOST ADDRESS", bg="#0d0d0d", fg="#a1a1a6", font=("Inter", 9, "bold")).pack(anchor="w", pady=(0, 7))
        entry = tk.Entry(shell, textvariable=self.host, bg="#19191b", fg="#f4f4f6", insertbackground="#f4f4f6", relief="flat", highlightthickness=1, highlightbackground="#3a3a3c", highlightcolor="#0a84ff", font=("Inter", 11))
        entry.pack(fill="x", ipady=10)
        entry.focus_set()
        tk.Button(shell, text="Open Hermes", command=self.open_host, bg="#0a84ff", fg="white", activebackground="#2997ff", activeforeground="white", relief="flat", borderwidth=0, cursor="hand2", font=("Inter", 11, "bold"), padx=22, pady=11).pack(anchor="e", pady=(25, 12))
        tk.Label(shell, text="Hermes User stores only this address. Your chats, login session, provider keys and computer controls remain on the Host.", bg="#0d0d0d", fg="#77777c", justify="left", wraplength=430, font=("Inter", 9)).pack(anchor="w")
        self.bind("<Return>", lambda _event: self.open_host())

    def open_host(self):
        try:
            host = normalise_host(self.host.get())
            save_host(host)
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        webbrowser.open(host, new=1)


if __name__ == "__main__":
    HermesUser().mainloop()
