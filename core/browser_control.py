#!/usr/bin/env python3
"""Hermes V5.3 browser navigation and structured Chrome control."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from cdp_client import CDPConnection, CDPError, call_page, debugger_json, evaluate, page_target, page_targets
from computer_control import writable_path
from platform_support import find_browser, graphical_environment, require_x11_automation, xdg_user_directory


router = APIRouter(prefix="/browser", tags=["Hermes V5.3 browser operator"])
MAX_PAGE_BYTES = 2_000_000
MAX_DOWNLOAD_BYTES = 50_000_000
MANAGED_BROWSER_ROOT = Path.home() / ".local/share/hermes/managed-browser"
MANAGED_PROFILE = MANAGED_BROWSER_ROOT / "profile"
DOWNLOADS_DIR = xdg_user_directory("DOWNLOAD")
PICTURES_DIR = xdg_user_directory("PICTURES")
RISKY_BUTTON_WORDS = re.compile(
    r"\b(send|submit|publish|post|buy|purchase|pay|order|delete|remove|confirm|sign[ -]?in|log[ -]?in)\b",
    re.IGNORECASE,
)


def valid_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "A complete HTTP or HTTPS URL is required")
    return value


class PageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.skip = 0
        self.text = []
        self.links = []
        self.title = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(urljoin(self.base_url, href))

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.skip:
            return
        cleaned = " ".join(data.split())
        if cleaned:
            self.text.append(cleaned)
            if self.in_title:
                self.title.append(cleaned)


class BrowserTabsRequest(BaseModel):
    browser: str = Field(default="chrome", pattern="^(chrome|firefox)$")
    urls: list[str] = Field(min_length=1, max_length=20)


class BrowserNavigateRequest(BaseModel):
    window_id: str = Field(pattern=r"^0x[0-9a-fA-F]+$")
    url: str = Field(min_length=8, max_length=4000)


class WebPageRequest(BaseModel):
    url: str = Field(min_length=8, max_length=4000)


class DownloadRequest(WebPageRequest):
    filename: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,150}$")


class ManagedBrowserRequest(BaseModel):
    urls: list[str] = Field(default_factory=list, max_length=20)


class ManagedPageRequest(BaseModel):
    page_id: str = Field(pattern=r"^[A-Fa-f0-9-]{8,100}$")


class ManagedPageAction(ManagedPageRequest):
    action: str = Field(pattern=r"^(navigate|click|type|select|check|uncheck|submit|back|forward|reload)$")
    target: int | None = Field(default=None, ge=1, le=500)
    value: str = Field(default="", max_length=20_000)
    url: str = Field(default="", max_length=4000)
    confirmed: bool = False


class ManagedUploadRequest(ManagedPageRequest):
    target: int = Field(ge=1, le=500)
    path: str = Field(min_length=1, max_length=2000)
    confirmed: bool = False


class ManagedWaitRequest(ManagedPageRequest):
    text: str = Field(min_length=1, max_length=500)
    timeout_seconds: int = Field(default=20, ge=1, le=120)


class ManagedScreenshotRequest(ManagedPageRequest):
    filename: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,140}\.png$")


def browser_version():
    try:
        return debugger_json("/json/version")
    except Exception:
        return None


def create_managed_page(url: str):
    version = browser_version()
    if not version:
        raise HTTPException(503, "Managed Chrome session is not running")
    try:
        with CDPConnection(version["webSocketDebuggerUrl"]) as connection:
            return connection.call("Target.createTarget", {"url": valid_url(url)})
    except (KeyError, CDPError, OSError) as exc:
        raise HTTPException(502, f"Could not create browser page: {exc}")


def start_or_reuse_managed_browser(urls: list[str]):
    checked = [valid_url(url) for url in urls]
    if browser_version():
        created = [create_managed_page(url).get("targetId") for url in checked]
        return {"success": True, "reused": True, "created_pages": created, "pages": public_pages()}

    if not find_browser():
        raise HTTPException(404, "No Chromium-compatible browser is installed")
    MANAGED_PROFILE.mkdir(parents=True, exist_ok=True)
    os.chmod(MANAGED_BROWSER_ROOT, 0o700)
    os.chmod(MANAGED_PROFILE, 0o700)
    started = subprocess.run(
        ["systemctl", "--user", "start", "hermes-managed-browser.service"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if started.returncode:
        raise HTTPException(502, started.stderr.strip() or "Could not start the managed browser service")
    for _ in range(30):
        if browser_version():
            created = [create_managed_page(url).get("targetId") for url in checked]
            return {"success": True, "reused": False, "created_pages": created, "pages": public_pages()}
        time.sleep(0.5)
    raise HTTPException(504, "Managed Chrome did not become ready")


def public_pages():
    try:
        return [
            {"page_id": target.get("id"), "title": target.get("title", ""), "url": target.get("url", "")}
            for target in page_targets()
            if not target.get("url", "").startswith(("chrome-extension://", "devtools://"))
        ]
    except Exception as exc:
        raise HTTPException(503, f"Managed Chrome is unavailable: {type(exc).__name__}")


SNAPSHOT_SCRIPT = r"""
(() => {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
  };
  const candidates = [...document.querySelectorAll(
    'a,button,input,textarea,select,[role="button"],[role="link"],[contenteditable="true"]'
  )].filter(visible).slice(0, 500);
  const elements = candidates.map((element, index) => {
    const target = index + 1;
    element.setAttribute('data-hermes-target', String(target));
    const labels = element.labels ? [...element.labels].map(label => label.innerText).join(' ') : '';
    return {
      target,
      tag: element.tagName.toLowerCase(),
      type: element.getAttribute('type') || '',
      role: element.getAttribute('role') || '',
      text: (element.innerText || element.value || '').trim().slice(0, 300),
      name: element.getAttribute('name') || '',
      label: (element.getAttribute('aria-label') || labels || element.getAttribute('placeholder') || '').trim().slice(0, 300),
      href: element.href || '',
      checked: Boolean(element.checked),
      disabled: Boolean(element.disabled)
    };
  });
  return {
    title: document.title,
    url: location.href,
    text: (document.body ? document.body.innerText : '').slice(0, 60000),
    elements,
    text_truncated: Boolean(document.body && document.body.innerText.length > 60000)
  };
})()
"""


def managed_snapshot(page_id: str):
    try:
        page_target(page_id)
        result = evaluate(page_id, SNAPSHOT_SCRIPT, timeout=30)
        if not isinstance(result, dict):
            raise CDPError("Page did not return a snapshot")
        result["page_id"] = page_id
        return result
    except CDPError as exc:
        raise HTTPException(404, str(exc))


@router.post("/tabs", operation_id="open_browser_tabs")
def open_browser_tabs(request: BrowserTabsRequest):
    urls = [valid_url(url) for url in request.urls]
    executable = find_browser("firefox" if request.browser == "firefox" else "chromium")
    if not executable:
        raise HTTPException(404, f"No compatible {request.browser} browser is installed")
    command = [executable, "--new-tab", *urls] if request.browser == "chrome" else [executable, *urls]
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, env=graphical_environment())
    return {"success": True, "browser": request.browser, "urls": urls, "process_id": process.pid}


@router.post("/navigate", operation_id="navigate_browser_window")
def navigate_browser_window(request: BrowserNavigateRequest):
    url = valid_url(request.url)
    try:
        environment = require_x11_automation()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    windows = subprocess.run(["wmctrl", "-lx"], capture_output=True, text=True, check=True, timeout=5, env=environment).stdout
    matching = [line for line in windows.splitlines() if line.casefold().startswith(request.window_id.casefold() + " ")]
    if not matching or not any(name in matching[0].casefold() for name in ("chrome", "firefox")):
        raise HTTPException(404, "Browser window ID was not found")
    decimal_id = str(int(request.window_id, 16))
    subprocess.run(["xdotool", "windowactivate", decimal_id], check=True, timeout=5, env=environment)
    subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+l"], check=True, timeout=5, env=environment)
    subprocess.run(["xdotool", "type", "--clearmodifiers", "--", url], check=True, timeout=10, env=environment)
    subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], check=True, timeout=5, env=environment)
    return {"success": True, "window_id": request.window_id, "url": url}


@router.post("/read", operation_id="read_web_page")
def read_web_page(request: WebPageRequest):
    url = valid_url(request.url)
    web_request = urllib.request.Request(url, headers={"User-Agent": "Hermes/5.3 local assistant"})
    try:
        with urllib.request.urlopen(web_request, timeout=20) as response:
            content_type = response.headers.get_content_type()
            body = response.read(MAX_PAGE_BYTES + 1)
            final_url = response.geturl()
            charset = response.headers.get_content_charset() or "utf-8"
    except Exception as exc:
        raise HTTPException(502, f"Page request failed: {type(exc).__name__}")
    if len(body) > MAX_PAGE_BYTES:
        raise HTTPException(413, "Page exceeds the 2 MB reading limit")
    if content_type not in {"text/html", "text/plain", "application/xhtml+xml", "application/json"}:
        raise HTTPException(415, f"Unsupported page type: {content_type}")
    text = body.decode(charset, errors="replace")
    if content_type in {"text/html", "application/xhtml+xml"}:
        parser = PageParser(final_url)
        parser.feed(text)
        visible = "\n".join(parser.text)
        title = " ".join(parser.title)
        links = list(dict.fromkeys(parser.links))[:100]
    else:
        visible, title, links = text, "", []
    return {"url": final_url, "title": title, "text": visible[:60_000], "links": links, "text_truncated": len(visible) > 60_000}


@router.post("/download", operation_id="download_web_file")
def download_web_file(request: DownloadRequest):
    url = valid_url(request.url)
    destination = (DOWNLOADS_DIR / request.filename).resolve()
    if destination.parent != DOWNLOADS_DIR:
        raise HTTPException(400, "Invalid download filename")
    if destination.exists():
        raise HTTPException(409, "Download file already exists")
    web_request = urllib.request.Request(url, headers={"User-Agent": "Hermes/5.3 local assistant"})
    temporary = destination.with_name(f".{destination.name}.hermes-{os.getpid()}.part")
    try:
        with urllib.request.urlopen(web_request, timeout=30) as response, temporary.open("xb") as output:
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise HTTPException(413, "Download exceeds the 50 MB limit")
                output.write(chunk)
        os.replace(temporary, destination)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Download failed: {type(exc).__name__}")
    finally:
        temporary.unlink(missing_ok=True)
    return {"success": True, "path": str(destination), "bytes": destination.stat().st_size}


@router.post("/managed/start", operation_id="start_managed_browser")
def start_managed_browser(request: ManagedBrowserRequest):
    """Start or reuse the dedicated visible Chrome session controlled by Hermes."""
    return start_or_reuse_managed_browser(request.urls)


@router.get("/managed/pages", operation_id="list_managed_browser_pages")
def list_managed_browser_pages():
    return {"success": True, "pages": public_pages()}


@router.post("/managed/snapshot", operation_id="snapshot_browser_page")
def snapshot_browser_page(request: ManagedPageRequest):
    """Return visible page text and numbered interactive elements."""
    return managed_snapshot(request.page_id)


@router.post("/managed/action", operation_id="interact_with_browser_page")
def interact_with_browser_page(request: ManagedPageAction):
    """Interact with a numbered element from the latest browser snapshot."""
    try:
        if request.action == "navigate":
            if not request.url:
                raise HTTPException(400, "navigate requires a complete URL")
            call_page(request.page_id, "Page.navigate", {"url": valid_url(request.url)})
        elif request.action in {"back", "forward", "reload"}:
            expression = {
                "back": "history.back(); true",
                "forward": "history.forward(); true",
                "reload": "location.reload(); true",
            }[request.action]
            evaluate(request.page_id, expression)
        else:
            if request.target is None:
                raise HTTPException(400, f"{request.action} requires a target number from snapshot_browser_page")
            snapshot = managed_snapshot(request.page_id)
            element = next((item for item in snapshot["elements"] if item["target"] == request.target), None)
            if not element:
                raise HTTPException(404, "Browser target is stale or no longer visible; take a new snapshot")
            descriptor = " ".join(str(element.get(key, "")) for key in ("text", "label", "type", "role"))
            consequential = request.action == "submit" or bool(RISKY_BUTTON_WORDS.search(descriptor))
            if consequential and not request.confirmed:
                raise HTTPException(403, "This browser action may submit, publish, purchase, delete, or sign in; explicit confirmation is required")
            target = json.dumps(str(request.target))
            value = json.dumps(request.value)
            action = json.dumps(request.action)
            script = f"""
            (() => {{
              const element = document.querySelector('[data-hermes-target="' + {target} + '"]');
              if (!element) throw new Error('Browser target is stale; take a new snapshot');
              const action = {action};
              const value = {value};
              element.scrollIntoView({{block: 'center', inline: 'center'}});
              if (action === 'click') {{ element.click(); return true; }}
              if (action === 'submit') {{
                const form = element.form || element.closest('form');
                if (!form) throw new Error('Target is not inside a form');
                if (form.requestSubmit) form.requestSubmit(); else form.submit();
                return true;
              }}
              if (action === 'check' || action === 'uncheck') {{
                element.checked = action === 'check';
                element.dispatchEvent(new Event('input', {{bubbles: true}}));
                element.dispatchEvent(new Event('change', {{bubbles: true}}));
                return true;
              }}
              if (action === 'select') {{
                element.value = value;
                element.dispatchEvent(new Event('input', {{bubbles: true}}));
                element.dispatchEvent(new Event('change', {{bubbles: true}}));
                return true;
              }}
              if (action === 'type') {{
                element.focus();
                if (element.isContentEditable) element.textContent = value;
                else {{
                  const prototype = element.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                  const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
                  if (setter) setter.call(element, value); else element.value = value;
                }}
                element.dispatchEvent(new Event('input', {{bubbles: true}}));
                element.dispatchEvent(new Event('change', {{bubbles: true}}));
                return true;
              }}
              throw new Error('Unsupported browser action');
            }})()
            """
            evaluate(request.page_id, script)
        time.sleep(0.7)
        try:
            state = managed_snapshot(request.page_id)
            return {"success": True, "action": request.action, "page": {"page_id": request.page_id, "title": state["title"], "url": state["url"]}}
        except HTTPException:
            return {"success": True, "action": request.action, "page_closed_or_navigating": True}
    except CDPError as exc:
        raise HTTPException(502, str(exc))


@router.post("/managed/upload", operation_id="upload_file_to_browser_page")
def upload_file_to_browser_page(request: ManagedUploadRequest):
    if not request.confirmed:
        raise HTTPException(403, "Uploading a local file requires explicit confirmation")
    path = writable_path(request.path)
    if not path.is_file():
        raise HTTPException(400, "Upload path is not a regular file")
    try:
        target = page_target(request.page_id)
        with CDPConnection(target["webSocketDebuggerUrl"], timeout=30) as connection:
            document = connection.call("DOM.getDocument", {"depth": -1, "pierce": True})
            node = connection.call("DOM.querySelector", {
                "nodeId": document["root"]["nodeId"],
                "selector": f'[data-hermes-target="{request.target}"]',
            })
            if not node.get("nodeId"):
                raise HTTPException(404, "Upload target is stale; take a new browser snapshot")
            connection.call("DOM.setFileInputFiles", {"files": [str(path)], "nodeId": node["nodeId"]})
        return {"success": True, "page_id": request.page_id, "target": request.target, "filename": path.name}
    except CDPError as exc:
        raise HTTPException(502, str(exc))


@router.post("/managed/wait", operation_id="wait_for_browser_text")
def wait_for_browser_text(request: ManagedWaitRequest):
    deadline = time.monotonic() + request.timeout_seconds
    last_url = ""
    while time.monotonic() < deadline:
        snapshot = managed_snapshot(request.page_id)
        last_url = snapshot["url"]
        if request.text.casefold() in snapshot["text"].casefold():
            return {"success": True, "found": True, "text": request.text, "url": last_url}
        time.sleep(1)
    return {"success": False, "found": False, "text": request.text, "url": last_url, "timed_out": True}


@router.post("/managed/screenshot", operation_id="capture_browser_page")
def capture_browser_page(request: ManagedScreenshotRequest):
    destination = (PICTURES_DIR / "Hermes" / request.filename).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise HTTPException(409, "Screenshot file already exists")
    try:
        result = call_page(request.page_id, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, timeout=30)
        data = base64.b64decode(result["data"], validate=True)
    except (CDPError, KeyError, ValueError) as exc:
        raise HTTPException(502, f"Browser screenshot failed: {exc}")
    destination.write_bytes(data)
    os.chmod(destination, 0o600)
    return {"success": True, "path": str(destination), "bytes": len(data)}


@router.post("/managed/close", operation_id="close_managed_browser_page")
def close_managed_browser_page(request: ManagedPageRequest):
    try:
        version = browser_version()
        if not version:
            raise CDPError("Managed Chrome is unavailable")
        with CDPConnection(version["webSocketDebuggerUrl"]) as connection:
            result = connection.call("Target.closeTarget", {"targetId": request.page_id})
        if not result.get("success"):
            raise CDPError("Chrome did not close the requested page")
    except (CDPError, KeyError, OSError) as exc:
        raise HTTPException(404, f"Could not close browser page: {exc}")
    time.sleep(0.2)
    try:
        remaining = public_pages()
    except HTTPException:
        remaining = []
    idle_urls = {"", "about:blank", "chrome://newtab/", "chrome://new-tab-page/"}
    browser_stopped = False
    if all(page.get("url", "") in idle_urls for page in remaining):
        stopped = subprocess.run(
            ["systemctl", "--user", "stop", "hermes-managed-browser.service"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        browser_stopped = stopped.returncode == 0
    return {"success": True, "page_id": request.page_id, "result": result, "browser_stopped": browser_stopped}
