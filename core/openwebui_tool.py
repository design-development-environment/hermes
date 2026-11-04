"""
title: Hermes Alpha Smart Operator
author: Hermes
version: alpha
description: Portable Ubuntu-family Linux operator with smart intent routing,
             replaceable vision, verified browser/code/file workflows, memory,
             planning, and background tasks.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

import aiohttp
from pydantic import Field


def _token_path() -> Path:
    configured = os.environ.get("HERMES_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser() / "tool-token"
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / "Hermes/config/tool-token"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Hermes/config/tool-token"
    return Path.home() / ".config/hermes/tool-token"


class Tools:
    def __init__(self):
        self.base_url = "http://127.0.0.1:8765"
        self.default_timeout = 30
        self.vision_timeout = 220

    def _authorization_headers(self) -> dict:
        token = _token_path().read_text().strip()
        return {"Authorization": f"Bearer {token}"}

    # ============================================================
    # INTERNAL HTTP CLIENT
    # ============================================================

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        payload: Optional[dict] = None,
        timeout: int = 30,
    ) -> str:
        """
        Communicate with the local Hermes FastAPI Action Bridge.
        """

        url = f"{self.base_url}{endpoint}"

        try:
            client_timeout = aiohttp.ClientTimeout(total=timeout)

            async with aiohttp.ClientSession(timeout=client_timeout) as session:

                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=payload,
                    headers=self._authorization_headers(),
                ) as response:

                    body = await response.text()

                    if response.status >= 400:
                        return json.dumps(
                            {
                                "success": False,
                                "status": response.status,
                                "error": body,
                            }
                        )

                    try:
                        return json.dumps(json.loads(body))

                    except json.JSONDecodeError:
                        return json.dumps(
                            {
                                "success": True,
                                "result": body,
                            }
                        )

        except aiohttp.ClientConnectorError:
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        "Hermes Action Bridge is unavailable. "
                        "Check that app.py is running on port 8765."
                    ),
                }
            )

        except asyncio.TimeoutError:
            return json.dumps(
                {
                    "success": False,
                    "error": (f"Request timed out after {timeout} seconds."),
                }
            )

        except Exception as exc:
            return json.dumps(
                {
                    "success": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    # ============================================================
    # 1. HEALTH CHECK
    # ============================================================

    async def health_check(self) -> str:
        """
        Check whether the Hermes Action Bridge is available.
        """

        return await self._request(
            method="GET",
            endpoint="/health",
        )

    async def get_platform_compatibility(self) -> str:
        """Report Linux, CPU, display, browser, and available Hermes capabilities."""
        return await self._request(method="GET", endpoint="/platform/status")

    async def get_graphical_appliance_readiness(self) -> str:
        """Check the i3/8 GB Mint Cinnamon appliance profile, drivers, and desktop utilities."""
        return await self._request(method="GET", endpoint="/graphical/readiness")

    async def get_desktop_monitor_layout(self) -> str:
        """List connected monitors, resolutions, positions, and the primary display."""
        return await self._request(method="GET", endpoint="/graphical/monitors")

    async def read_desktop_clipboard(self, confirmed: bool = False) -> str:
        """Read clipboard text after explicit confirmation because it may contain secrets."""
        return await self._request(method="POST", endpoint="/graphical/clipboard/read", payload={"confirmed": confirmed})

    async def write_desktop_clipboard(self, text: str) -> str:
        """Replace the desktop clipboard with text."""
        return await self._request(method="POST", endpoint="/graphical/clipboard/write", payload={"text": text})

    async def get_desktop_audio_status(self) -> str:
        """Read speaker volume, mute state, and default audio devices."""
        return await self._request(method="GET", endpoint="/graphical/audio")

    async def set_desktop_audio_volume(self, percent: int) -> str:
        """Set default speaker volume between 0 and 150 percent."""
        return await self._request(method="POST", endpoint="/graphical/audio/volume", payload={"percent": percent})

    async def set_desktop_audio_mute(self, muted: bool) -> str:
        """Mute or unmute the default desktop speakers."""
        return await self._request(method="POST", endpoint="/graphical/audio/mute", payload={"muted": muted})

    async def list_desktop_media_players(self) -> str:
        """List applications exposing standard Linux media controls."""
        return await self._request(method="GET", endpoint="/graphical/media")

    async def control_desktop_media(self, action: str, player: str = "") -> str:
        """Play, pause, navigate, or stop a desktop media player."""
        return await self._request(method="POST", endpoint="/graphical/media", payload={"action": action, "player": player})

    async def list_desktop_workspaces(self) -> str:
        """List Cinnamon workspaces and the currently active workspace."""
        return await self._request(method="GET", endpoint="/graphical/workspaces")

    async def switch_desktop_workspace(self, workspace: int) -> str:
        """Switch to an exact Cinnamon workspace number."""
        return await self._request(method="POST", endpoint="/graphical/workspaces/switch", payload={"workspace": workspace})

    async def move_window_to_desktop_workspace(self, window_id: str, workspace: int, follow: bool = False) -> str:
        """Move an exact listed window to another workspace."""
        return await self._request(method="POST", endpoint="/graphical/workspaces/move-window", payload={"window_id": window_id, "workspace": workspace, "follow": follow})

    async def open_cinnamon_settings_panel(self, panel: str) -> str:
        """Open an approved Cinnamon settings panel."""
        return await self._request(method="POST", endpoint="/graphical/settings", payload={"panel": panel})

    async def lock_desktop_session(self, confirmed: bool = False) -> str:
        """Lock the desktop after explicit confirmation; GUI control pauses until unlock."""
        return await self._request(method="POST", endpoint="/graphical/lock", payload={"confirmed": confirmed})

    async def get_desktop_network_status(self) -> str:
        """Read NetworkManager state and device connections without exposing credentials."""
        return await self._request(method="GET", endpoint="/graphical/network")

    async def get_appliance_power_policy(self) -> str:
        """Check whether Cinnamon may suspend the always-on appliance while on AC power."""
        return await self._request(method="GET", endpoint="/graphical/power-policy")

    async def enable_appliance_keep_awake(self, confirmed: bool = False) -> str:
        """Disable automatic AC suspend after explicit confirmation while preserving manual locking."""
        return await self._request(method="POST", endpoint="/graphical/power-policy/keep-awake", payload={"confirmed": confirmed})

    # ============================================================
    # 2. LIST DESKTOP WINDOWS
    # ============================================================

    async def list_desktop_windows(self) -> str:
        """
        List currently open desktop windows.

        Use this tool to identify applications and window
        titles before interacting with the desktop.
        """

        return await self._request(
            method="GET",
            endpoint="/desktop/windows",
        )

    # ============================================================
    # 3. FOCUS WINDOW BY TITLE
    # ============================================================

    async def focus_desktop_window(
        self,
        title: str = Field(
            ...,
            description="Full or partial title of the window to focus.",
        ),
    ) -> str:
        """
        Focus an existing desktop window by title.

        Args:
            title: Window title or partial title.
        """

        return await self._request(
            method="POST",
            endpoint="/desktop/focus",
            payload={
                "title": title,
            },
        )

    # ============================================================
    # 4. FOCUS WINDOW BY CLASS
    # ============================================================

    async def focus_window_by_class(
        self,
        class_name: str = Field(
            ...,
            description="X11 window class; this exact global action requires X11.",
        ),
    ) -> str:
        """
        Focus a desktop window using its X11 application class.

        Check platform compatibility first on Wayland or headless machines.

        Args:
            class_name: Application window class.
        """

        return await self._request(
            method="POST",
            endpoint="/desktop/focus-class",
            payload={
                "class_name": class_name,
            },
        )

    # ============================================================
    # 5. LAUNCH APPLICATION
    # ============================================================

    async def launch_desktop_application(
        self,
        application: str = Field(
            ...,
            description=(
                "Approved application executable name, such as "
                "xed, nemo, firefox, google-chrome, "
                "or gnome-calculator."
            ),
        ),
    ) -> str:
        """
        Launch an application from the Action Bridge allowlist.

        Use gnome-calculator rather than calculator.

        Args:
            application: Approved executable name.
        """

        return await self._request(
            method="POST",
            endpoint="/desktop/launch",
            payload={
                "application": application,
            },
        )

    # ============================================================
    # 6. TYPE INTO APPLICATION
    # ============================================================

    async def type_into_application(
        self,
        class_name: str = Field(
            ...,
            description="X11 window class; this exact global action requires X11.",
        ),
        text: str = Field(
            ...,
            description="Text to type into the application.",
        ),
    ) -> str:
        """
        Focus an application and type text into it.

        Args:
            class_name: Target application window class.
            text: Text to enter.
        """

        return await self._request(
            method="POST",
            endpoint="/desktop/type-to-class",
            payload={
                "class_name": class_name,
                "text": text,
            },
        )

    # ============================================================
    # 7. SEND KEYBOARD SHORTCUT
    # ============================================================

    async def send_application_shortcut(
        self,
        class_name: str = Field(
            ...,
            description="X11 class of the target application; this exact global action requires X11.",
        ),
        shortcut: str = Field(
            ...,
            description=("Keyboard shortcut allowed by the Action Bridge."),
        ),
    ) -> str:
        """
        Send an approved keyboard shortcut to an application.

        The Action Bridge enforces its shortcut allowlist.

        Args:
            class_name: Target application class.
            shortcut: Keyboard shortcut.
        """

        return await self._request(
            method="POST",
            endpoint="/desktop/shortcut",
            payload={
                "class_name": class_name,
                "shortcut": shortcut,
            },
        )

    # ============================================================
    # 8. GET MOUSE POSITION
    # ============================================================

    async def get_mouse_position(self) -> str:
        """
        Get the current mouse cursor coordinates.
        """

        return await self._request(
            method="GET",
            endpoint="/desktop/mouse/position",
        )

    # ============================================================
    # 9. MOVE MOUSE
    # ============================================================

    async def move_mouse(
        self,
        x: int = Field(
            ...,
            description="Horizontal screen coordinate.",
        ),
        y: int = Field(
            ...,
            description="Vertical screen coordinate.",
        ),
    ) -> str:
        """
        Move the mouse cursor to an absolute screen position.

        Args:
            x: Horizontal coordinate.
            y: Vertical coordinate.
        """

        return await self._request(
            method="POST",
            endpoint="/desktop/mouse/move",
            payload={
                "x": x,
                "y": y,
            },
        )

    # ============================================================
    # 10. CLICK MOUSE
    # ============================================================

    async def click_mouse(
        self,
        x: int = Field(
            ...,
            description="Horizontal coordinate to click.",
        ),
        y: int = Field(
            ...,
            description="Vertical coordinate to click.",
        ),
        button: int = 1,
        clicks: int = 1,
    ) -> str:
        """
        Click at specified screen coordinates.

        Mouse buttons:
            1 = Left
            2 = Middle
            3 = Right

        Click count:
            1 = Single click
            2 = Double click

        Use button=1 and clicks=2 for a double left-click.

        Ask for confirmation before actions that could
        delete files, submit payments, or make irreversible changes.

        Args:
            x: Horizontal coordinate.
            y: Vertical coordinate.
            button: Mouse button.
            clicks: Number of clicks.
        """

        if button not in (1, 3):
            return json.dumps(
                {
                    "success": False,
                    "error": "Button must be 1 or 3.",
                }
            )

        if clicks not in (1, 2):
            return json.dumps(
                {
                    "success": False,
                    "error": "Clicks must be 1 or 2.",
                }
            )

        return await self._request(
            method="POST",
            endpoint="/desktop/mouse/click",
            payload={
                "x": x,
                "y": y,
                "button": button,
                "clicks": clicks,
            },
        )

    # ============================================================
    # 11. SCROLL MOUSE
    # ============================================================

    async def scroll_mouse(
        self,
        x: int = Field(
            ...,
            description="Horizontal coordinate for scrolling.",
        ),
        y: int = Field(
            ...,
            description="Vertical coordinate for scrolling.",
        ),
        direction: str = Field(
            ...,
            description="Scroll direction: up or down.",
        ),
        steps: int = 3,
    ) -> str:
        """
        Scroll the mouse wheel at the specified location.

        Args:
            x: Horizontal coordinate.
            y: Vertical coordinate.
            direction: up or down.
            steps: Number of scroll steps.
        """

        direction = direction.strip().lower()

        if direction not in ("up", "down"):
            return json.dumps(
                {
                    "success": False,
                    "error": "Direction must be up or down.",
                }
            )

        if not 1 <= steps <= 10:
            return json.dumps(
                {
                    "success": False,
                    "error": "Steps must be between 1 and 10.",
                }
            )

        return await self._request(
            method="POST",
            endpoint="/desktop/mouse/scroll",
            payload={
                "x": x,
                "y": y,
                "direction": direction,
                "steps": steps,
            },
        )

    # ============================================================
    # 12. LIST DIRECTORY
    # ============================================================

    async def list_directory(
        self,
        path: str = "~",
    ) -> str:
        """
        List files and folders in a local directory.

        Args:
            path: Directory to inspect. Defaults to home.
        """

        return await self._request(
            method="GET",
            endpoint="/files/list",
            params={
                "path": path,
            },
        )

    # ============================================================
    # 13. SEARCH FILE NAMES
    # ============================================================

    async def search_file_names(
        self,
        root: str = Field(
            ...,
            description="Root directory in which to search.",
        ),
        query: str = Field(
            ...,
            description="File or folder name search term.",
        ),
        limit: int = 50,
    ) -> str:
        """
        Search for files and folders by name.

        Args:
            root: Starting directory.
            query: Search term.
            limit: Maximum number of results.
        """

        if not 1 <= limit <= 100:
            return json.dumps(
                {
                    "success": False,
                    "error": "Limit must be between 1 and 100.",
                }
            )

        return await self._request(
            method="GET",
            endpoint="/files/search",
            params={
                "root": root,
                "query": query,
                "limit": limit,
            },
        )

    # ============================================================
    # 14. READ TEXT FILE
    # ============================================================

    async def read_text_file(
        self,
        path: str = Field(
            ...,
            description="Path to a local text file.",
        ),
    ) -> str:
        """
        Read a local text file.

        Args:
            path: Absolute or home-relative file path.
        """

        return await self._request(
            method="GET",
            endpoint="/files/read",
            params={
                "path": path,
            },
        )

    # ============================================================
    # 15. CAPTURE SCREENSHOT
    # ============================================================

    async def capture_desktop_screenshot(self) -> str:
        """
        Capture the current Linux desktop.

        The screenshot is saved locally.

        Returns screenshot metadata including filename,
        path, timestamp, and size.

        This tool does not analyze image contents.

        For visual understanding, call analyze_desktop_screen.
        """

        return await self._request(
            method="POST",
            endpoint="/desktop/screenshot",
            timeout=40,
        )

    # ============================================================
    # 16. ANALYZE DESKTOP SCREEN
    # ============================================================

    async def analyze_desktop_screen(
        self,
        question: str = ("Describe what is currently visible on my desktop."),
        provider: str = "",
        model: str = "",
        __model__: Optional[dict] = None,
    ) -> str:
        """
        Analyze the current Linux desktop with the vision provider selected by
        the active Workspace preset or an explicit provider/model override.

        Workflow:
            1. Capture a fresh desktop screenshot.
            2. Resolve the preset/default vision provider and model.
            3. Analyze through the preset's configured local or cloud provider.
            4. Return the model's description.

        Use when:
            - User asks what is visible on the screen.
            - User asks Hermes to inspect an application.
            - User asks about visible interface elements.
            - User wants visual verification after an action.
            - User asks about a visible webpage.

        Important:
            Vision models can misidentify text, buttons, or applications.
            Cloud vision transmits the captured screenshot to that provider.

            For reliable verification, combine this tool
            with list_desktop_windows.

            Do not invent screen coordinates or claim
            success without tool verification.

        The provider and model are normally left blank. Hermes reads the
        `hermesVision` metadata from the active Workspace model preset.
        """

        if not question.strip():
            question = "Describe what is currently visible on my desktop."

        if len(question) > 500:
            return json.dumps(
                {
                    "success": False,
                    "error": ("Vision question exceeds 500 characters."),
                }
            )

        preset = (((__model__ or {}).get("info") or {}).get("meta") or {}).get("hermesVision") or {}
        selected_provider = provider.strip() or str(preset.get("provider", "")).strip()
        selected_model = model.strip() or str(preset.get("model", "")).strip()
        return await self._request(
            method="POST",
            endpoint="/desktop/vision/analyze",
            payload={
                "question": question,
                "provider": selected_provider,
                "model": selected_model,
            },
            timeout=self.vision_timeout,
        )

    async def get_model_runtime_status(self) -> str:
        """List the default vision selection and provider readiness without exposing API keys."""
        return await self._request(method="GET", endpoint="/models/runtime")

    async def configure_vision_model(
        self,
        provider: str,
        model: str,
        base_url: str = "",
        enabled: bool = False,
        confirmed: bool = False,
    ) -> str:
        """Change the default vision provider/model only after explicit user confirmation. API keys must be configured outside chat."""
        return await self._request(
            method="POST",
            endpoint="/models/vision",
            payload={
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "enabled": enabled,
                "confirmed": confirmed,
            },
        )

    # ============================================================
    # 17. AUTOMATION — LAUNCH AND VERIFY
    # ============================================================

    async def automation_launch_and_verify(
        self,
        application: str = Field(
            ...,
            description=(
                "Approved application executable name. "
                "Examples: xed, nemo, firefox, "
                "google-chrome, gnome-calculator."
            ),
        ),
    ) -> str:
        """
        Launch an approved desktop application and verify
        that a matching application window exists.

        This is a coordinated multi-step automation workflow.

        Workflow:
            1. Check existing windows.
            2. Launch the requested application.
            3. Wait for a matching application window.
            4. Return verification results.

        Prefer this tool over launch_desktop_application
        when the user requests opening an application
        and verifying that it launched.

        Important:
            A successful result means a matching window
            was detected. It does not necessarily prove
            that the window is focused or ready for input.

        Args:
            application: Approved executable name.
        """

        return await self._request(
            method="POST",
            endpoint="/automation/launch-verify",
            payload={
                "application": application,
            },
            timeout=40,
        )

    async def create_document(
        self,
        filename: str = Field(..., description="New .txt filename in the Hermes documents folder."),
        text: str = Field(..., description="Complete text to save in the new document."),
    ) -> str:
        """Create a new text document and verify the saved result. Existing files are never overwritten."""
        try:
            token = _token_path().read_text().strip()
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    "http://127.0.0.1:8766/tools/create-document",
                    json={"filename": filename, "text": text},
                    headers={"Authorization": f"Bearer {token}"},
                ) as response:
                    data = await response.json()
                    if response.status >= 400:
                        return json.dumps({"success": False, "status": response.status, "detail": data.get("detail", data)})
                    return json.dumps(data)
        except Exception as exc:
            return json.dumps({"success": False, "error": f"Document service unavailable: {type(exc).__name__}"})

    async def list_installed_applications(self, query: str = "") -> str:
        """List installed graphical applications and their launch IDs."""
        return await self._request("GET", "/computer/applications", params={"query": query})

    async def launch_multiple_applications(
        self,
        applications: list[str] = Field(..., description="One to ten application IDs returned by list_installed_applications."),
    ) -> str:
        """Open several installed graphical applications in one action."""
        return await self._request("POST", "/computer/applications/launch", payload={"applications": applications})

    async def open_file_folder_or_url(
        self,
        target: str = Field(..., description="File path, folder path, or HTTP/HTTPS URL to open."),
    ) -> str:
        """Open a local file or folder in its normal application, or open a web URL."""
        return await self._request("POST", "/computer/open", payload={"target": target})

    async def write_text_file(
        self,
        path: str = Field(..., description="Destination path in Desktop, Documents, Downloads, Pictures, Music, Videos, or hermes-v4."),
        content: str = Field(..., description="Complete UTF-8 text or source code to write."),
        overwrite: bool = False,
    ) -> str:
        """Create source code or text files atomically. Existing files require explicit overwrite approval."""
        return await self._request("POST", "/computer/files/write", payload={"path": path, "content": content, "overwrite": overwrite})

    async def append_text_file(
        self,
        path: str = Field(..., description="Existing or new text file path in an approved writable folder."),
        content: str = Field(..., description="Text to append."),
    ) -> str:
        """Append text to a file without replacing its existing content."""
        return await self._request("POST", "/computer/files/append", payload={"path": path, "content": content})

    async def create_folder(
        self,
        path: str = Field(..., description="Folder path to create in an approved writable location."),
    ) -> str:
        """Create a folder and any missing parent folders."""
        return await self._request("POST", "/computer/files/folder", payload={"path": path})

    async def copy_file_or_folder(
        self,
        source: str,
        destination: str,
        overwrite: bool = False,
    ) -> str:
        """Copy a file or folder. Existing destinations require explicit overwrite approval."""
        return await self._request("POST", "/computer/files/copy", payload={"source": source, "destination": destination, "overwrite": overwrite})

    async def move_file_or_folder(
        self,
        source: str,
        destination: str,
        overwrite: bool = False,
    ) -> str:
        """Move or rename a file or folder. Existing destinations require explicit overwrite approval."""
        return await self._request("POST", "/computer/files/move", payload={"source": source, "destination": destination, "overwrite": overwrite})

    async def move_file_or_folder_to_trash(
        self,
        path: str = Field(..., description="File or folder to move to the desktop Trash."),
    ) -> str:
        """Move a file or folder to recoverable Trash. Ask the user before using this tool."""
        return await self._request("POST", "/computer/files/trash", payload={"path": path})

    async def run_development_command(
        self,
        program: str = Field(..., description="Approved program such as git, python3, node, npm, pnpm, pytest, make, rg, or ls."),
        arguments: Optional[list[str]] = None,
        cwd: str = "~/hermes-v4",
        timeout_seconds: int = 30,
    ) -> str:
        """Run a coding, build, test, Git, or inspection command in a filesystem sandbox."""
        return await self._request(
            "POST", "/computer/terminal/run",
            payload={"program": program, "arguments": arguments or [], "cwd": cwd, "timeout_seconds": timeout_seconds},
            timeout=timeout_seconds + 10,
        )

    async def get_computer_status(self) -> str:
        """Get hostname, OS, uptime, disk space, and Hermes writable folders."""
        return await self._request("GET", "/computer/system/status")

    async def list_running_processes(self, query: str = "", limit: int = 50) -> str:
        """List running processes, optionally filtered by a name or search term."""
        return await self._request("GET", "/computer/system/processes", params={"query": query, "limit": limit})

    async def show_desktop_notification(self, title: str, message: str) -> str:
        """Display a notification on the Linux desktop."""
        return await self._request("POST", "/computer/notify", params={"title": title, "message": message})

    async def close_desktop_window(
        self,
        window_id: str = Field(..., description="Exact hexadecimal window ID returned by list_desktop_windows."),
    ) -> str:
        """Ask an exact desktop window to close. List windows first and confirm consequential unsaved work."""
        return await self._request("POST", "/computer/windows/close", payload={"window_id": window_id})

    async def send_key_sequence_to_application(
        self,
        class_name: str = Field(..., description="Unique application class from list_desktop_windows."),
        keys: list[str] = Field(..., description="Key combinations such as ctrl+l, ctrl+t, F5, Return, or Escape."),
    ) -> str:
        """Focus an application and send one or more keyboard combinations in order."""
        return await self._request("POST", "/computer/keyboard/sequence", payload={"class_name": class_name, "keys": keys})

    async def drag_mouse(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button: int = 1,
    ) -> str:
        """Drag the mouse between two on-screen coordinates."""
        return await self._request("POST", "/computer/mouse/drag", payload={
            "start_x": start_x, "start_y": start_y, "end_x": end_x, "end_y": end_y, "button": button,
        })

    async def manage_desktop_window(
        self, window_id: str, action: str, x: int | None = None,
        y: int | None = None, width: int | None = None, height: int | None = None,
    ) -> str:
        """Maximize, restore, minimize, move, or resize an exact desktop window."""
        return await self._request("POST", "/computer/windows/layout", payload={
            "window_id": window_id, "action": action, "x": x, "y": y, "width": width, "height": height,
        })

    async def type_into_exact_window(self, window_id: str, text: str, replace_selection: bool = False) -> str:
        """Focus an exact window ID and type single-line or multiline text into it."""
        return await self._request("POST", "/computer/windows/type", payload={
            "window_id": window_id, "text": text, "replace_selection": replace_selection,
        })

    async def inspect_codebase(self, root: str, max_files: int = 500, max_depth: int = 5) -> str:
        """Inspect a project tree, languages, important files, and Git status before changing code."""
        return await self._request("POST", "/code/inspect", params={"max_files": max_files, "max_depth": max_depth}, payload={"root": root})

    async def search_code(
        self, root: str, query: str, glob: str = "", regex: bool = False, limit: int = 100,
    ) -> str:
        """Search source code by literal text or regular expression, optionally within a file glob."""
        return await self._request("POST", "/code/search", payload={
            "root": root, "query": query, "glob": glob or None, "regex": regex, "limit": limit,
        })

    async def read_source_range(self, path: str, start_line: int = 1, end_line: int = 300) -> str:
        """Read an exact numbered range of up to 1000 lines from a source file."""
        return await self._request("POST", "/code/read", payload={"path": path, "start_line": start_line, "end_line": end_line})

    async def write_multiple_files(self, root: str, files: list[dict]) -> str:
        """Create or explicitly overwrite up to 30 source files in one validated batch."""
        return await self._request("POST", "/code/write-batch", payload={"root": root, "files": files})

    async def edit_multiple_files(self, root: str, edits: list[dict]) -> str:
        """Apply validated exact multiline replacements across several source files. No files change if validation fails."""
        return await self._request("POST", "/code/edit-batch", payload={"root": root, "edits": edits})

    async def review_git_changes(self, root: str) -> str:
        """Review Git status plus staged and unstaged diffs for a codebase."""
        return await self._request("POST", "/code/git-review", payload={"root": root})

    async def create_git_commit(
        self, root: str, message: str, paths: Optional[list[str]] = None, confirmed: bool = False,
    ) -> str:
        """Create a local Git commit only after the user explicitly requested and confirmed it. This never pushes."""
        return await self._request("POST", "/code/git-commit", payload={
            "root": root, "message": message, "paths": paths or [], "confirmed": confirmed,
        }, timeout=70)

    async def open_codebase_in_editor(self, root: str) -> str:
        """Open a codebase folder in a new Visual Studio Code window."""
        return await self._request("POST", "/code/open-editor", payload={"root": root})

    async def open_browser_tabs(self, urls: list[str], browser: str = "chrome") -> str:
        """Open up to 20 HTTP or HTTPS URLs as browser tabs."""
        return await self._request("POST", "/browser/tabs", payload={"browser": browser, "urls": urls})

    async def navigate_browser_window(self, window_id: str, url: str) -> str:
        """Navigate an exact Chrome or Firefox window to a URL."""
        return await self._request("POST", "/browser/navigate", payload={"window_id": window_id, "url": url})

    async def read_web_page(self, url: str) -> str:
        """Fetch a public webpage and return its title, visible text, and links."""
        return await self._request("POST", "/browser/read", payload={"url": url}, timeout=30)

    async def download_web_file(self, url: str, filename: str) -> str:
        """Download a file up to 50 MB into Downloads without overwriting an existing file."""
        return await self._request("POST", "/browser/download", payload={"url": url, "filename": filename}, timeout=45)

    # ============================================================
    # HERMES V5.2 — STRUCTURED MANAGED BROWSER
    # ============================================================

    async def start_managed_browser(self, urls: Optional[list[str]] = None) -> str:
        """Start or reuse Hermes's dedicated visible Chrome session and optionally open pages."""
        return await self._request("POST", "/browser/managed/start", payload={"urls": urls or []}, timeout=30)

    async def list_managed_browser_pages(self) -> str:
        """List page IDs, titles, and URLs in the managed Chrome session."""
        return await self._request("GET", "/browser/managed/pages")

    async def snapshot_browser_page(self, page_id: str) -> str:
        """Read visible page text and numbered interactive fields, links, and buttons."""
        return await self._request("POST", "/browser/managed/snapshot", payload={"page_id": page_id}, timeout=40)

    async def interact_with_browser_page(
        self,
        page_id: str,
        action: str,
        target: Optional[int] = None,
        value: str = "",
        url: str = "",
        confirmed: bool = False,
    ) -> str:
        """Navigate, click, type, select, check, submit, go back/forward, or reload a managed page. Consequential actions require confirmation."""
        return await self._request("POST", "/browser/managed/action", payload={
            "page_id": page_id, "action": action, "target": target, "value": value,
            "url": url, "confirmed": confirmed,
        }, timeout=45)

    async def upload_file_to_browser_page(self, page_id: str, target: int, path: str, confirmed: bool = False) -> str:
        """Upload an approved local file to a numbered file input. Explicit confirmation is mandatory."""
        return await self._request("POST", "/browser/managed/upload", payload={
            "page_id": page_id, "target": target, "path": path, "confirmed": confirmed,
        }, timeout=45)

    async def wait_for_browser_text(self, page_id: str, text: str, timeout_seconds: int = 20) -> str:
        """Wait until expected text appears on a managed page."""
        return await self._request("POST", "/browser/managed/wait", payload={
            "page_id": page_id, "text": text, "timeout_seconds": timeout_seconds,
        }, timeout=timeout_seconds + 10)

    async def capture_browser_page(self, page_id: str, filename: str) -> str:
        """Save a PNG screenshot of a managed browser page in Pictures/Hermes."""
        return await self._request("POST", "/browser/managed/screenshot", payload={"page_id": page_id, "filename": filename}, timeout=45)

    async def close_managed_browser_page(self, page_id: str) -> str:
        """Close one exact page in the managed Chrome session."""
        return await self._request("POST", "/browser/managed/close", payload={"page_id": page_id})

    # ============================================================
    # HERMES V5.3 — PERSISTENT BACKGROUND WORK
    # ============================================================

    async def create_background_workflow(
        self,
        name: str,
        steps: list[dict],
        scheduled_for: Optional[str] = None,
        notify: bool = True,
        max_attempts: int = 1,
    ) -> str:
        """Queue a checkpointed coding or web workflow that survives bridge restarts."""
        return await self._request("POST", "/tasks/create", payload={
            "name": name, "steps": steps, "scheduled_for": scheduled_for,
            "notify": notify, "max_attempts": max_attempts,
        })

    async def list_background_tasks(self, status: str = "", limit: int = 20) -> str:
        """List recent persistent tasks, optionally filtered by status."""
        return await self._request("GET", "/tasks", params={"status": status, "limit": limit})

    async def get_background_task(self, task_id: str) -> str:
        """Get a task's current checkpoint, results, and error details."""
        return await self._request("GET", f"/tasks/{task_id}")

    async def control_background_task(self, task_id: str, action: str) -> str:
        """Pause, resume, cancel, or retry a persistent task."""
        return await self._request("POST", "/tasks/control", payload={"task_id": task_id, "action": action})

    async def get_hermes_health_report(self) -> str:
        """Get one health report for services, endpoints, tasks, disk, backups, and Tailscale."""
        return await self._request("GET", "/maintenance/status")

    async def create_hermes_backup(self) -> str:
        """Create an owner-only local backup of Open WebUI, tasks, and Hermes configuration."""
        return await self._request("POST", "/maintenance/backup", timeout=180)

    async def list_hermes_backups(self) -> str:
        """List retained local Hermes backups."""
        return await self._request("GET", "/maintenance/backups")

    # ============================================================
    # HERMES V6 — MEMORY AND PLANNING
    # ============================================================

    async def remember_fact(
        self,
        content: str,
        category: str = "general",
        tags: Optional[list[str]] = None,
        source: str = "user",
        importance: int = 3,
    ) -> str:
        """Store a user-approved preference or fact without storing credentials or secrets."""
        return await self._request("POST", "/memory/remember", payload={
            "content": content, "category": category, "tags": tags or [],
            "source": source, "importance": importance,
        })

    async def recall_memories(self, query: str, limit: int = 10) -> str:
        """Search Hermes memory for relevant non-archived facts and preferences."""
        return await self._request("POST", "/memory/recall", payload={"query": query, "limit": limit})

    async def list_memories(self, category: str = "", include_archived: bool = False, limit: int = 50) -> str:
        """List stored memories, optionally including archived entries."""
        return await self._request("GET", "/memory", params={"category": category, "include_archived": include_archived, "limit": limit})

    async def forget_memory(self, memory_id: str, confirmed: bool = False) -> str:
        """Archive one memory; explicit confirmation is required because this changes personal data."""
        return await self._request("POST", "/memory/forget", payload={"memory_id": memory_id, "confirmed": confirmed})

    async def get_memory_briefing(self, query: str, limit: int = 10) -> str:
        """Return concise relevant memory for a task before deciding or acting."""
        return await self._request("POST", "/memory/briefing", payload={"query": query, "limit": limit})

    async def find_duplicate_memories(self, limit: int = 50) -> str:
        """Find exact duplicate active memories for review; this never deletes or changes anything."""
        return await self._request("GET", "/memory/duplicates", params={"limit": limit})

    async def draft_execution_plan(self, goal: str, steps: list[dict], constraints: str = "") -> str:
        """Draft a plan from steps shaped as {type, payload, label, depends_on, estimated_seconds}; create these internal steps yourself instead of asking the user for them."""
        return await self._request("POST", "/plans/draft", payload={"goal": goal, "steps": steps, "constraints": constraints})

    async def get_execution_plan(self, plan_id: str) -> str:
        """Read a plan, its risk classification, and linked task status."""
        return await self._request("GET", f"/plans/{plan_id}")

    async def list_execution_plans(self, limit: int = 20) -> str:
        """List recent Hermes plans."""
        return await self._request("GET", "/plans", params={"limit": limit})

    async def approve_execution_plan(self, plan_id: str, confirmed: bool = False, notify: bool = True, max_attempts: int = 1) -> str:
        """Approve and queue a drafted plan only after explicit user confirmation."""
        return await self._request("POST", "/plans/approve", payload={
            "plan_id": plan_id, "confirmed": confirmed, "notify": notify, "max_attempts": max_attempts,
        })

    async def revise_execution_plan(self, plan_id: str, steps: list[dict], constraints: str = "") -> str:
        """Create a corrected draft from an earlier failed or outdated plan; it cannot execute until separately approved."""
        return await self._request("POST", "/plans/revise", payload={"plan_id": plan_id, "steps": steps, "constraints": constraints})

    async def get_security_dashboard(self) -> str:
        """Show Hermes safety mode, task counts, audit summary, and backup-encryption readiness."""
        return await self._request("GET", "/governance/dashboard")

    async def set_hermes_safety_mode(self, mode: str, confirmed: bool = False) -> str:
        """Set normal, read_only, or stopped safety mode. Explicit confirmation is mandatory."""
        return await self._request("POST", "/governance/safety-mode", payload={"mode": mode, "confirmed": confirmed})

    async def emergency_stop_hermes(self, confirmed: bool = False) -> str:
        """Immediately block new privileged actions and cancel active background tasks after explicit confirmation."""
        return await self._request("POST", "/governance/emergency-stop", params={"confirmed": confirmed})

    async def get_integration_status(self) -> str:
        """Show whether authorized Open WebUI MCP/tool-server connections are configured without exposing secrets."""
        return await self._request("GET", "/governance/integrations")

    async def get_backup_encryption_status(self) -> str:
        """Check whether GPG-encrypted backup copies are ready; never asks for or stores a passphrase."""
        return await self._request("GET", "/maintenance/backup-encryption")

    async def create_encrypted_hermes_backup(self) -> str:
        """Create an encrypted backup only when a trusted GPG recipient is already configured by the owner."""
        return await self._request("POST", "/maintenance/backup-encrypted", timeout=240)

    # ============================================================
    # HERMES V8 — PERSISTENT PERSONAL AGENT
    # ============================================================

    async def create_personal_goal(
        self, title: str, description: str = "", priority: int = 3,
        target_date: Optional[str] = None, milestones: Optional[list[dict]] = None,
    ) -> str:
        """Create a persistent goal Hermes can track across conversations and restarts."""
        return await self._request("POST", "/agent/goals", payload={
            "title": title, "description": description, "priority": priority,
            "target_date": target_date, "milestones": milestones or [],
        })

    async def list_personal_goals(self, status: str = "active", limit: int = 50) -> str:
        """List persistent goals by active, paused, completed, archived, or all status."""
        return await self._request("GET", "/agent/goals", params={"status": status, "limit": limit})

    async def get_personal_goal(self, goal_id: str) -> str:
        """Get one goal, its milestones, and its linked mission plan."""
        return await self._request("GET", f"/agent/goals/{goal_id}")

    async def update_personal_goal(
        self, goal_id: str, progress: Optional[int] = None, status: Optional[str] = None,
        target_date: Optional[str] = None, milestones: Optional[list[dict]] = None, note: str = "",
    ) -> str:
        """Update progress, status, target date, milestones, or a timeline note for a goal."""
        payload = {"goal_id": goal_id, "note": note}
        if progress is not None:
            payload["progress"] = progress
        if status is not None:
            payload["status"] = status
        if target_date is not None:
            payload["target_date"] = target_date
        if milestones is not None:
            payload["milestones"] = milestones
        return await self._request("POST", "/agent/goals/update", payload=payload)

    async def archive_personal_goal(self, goal_id: str, confirmed: bool = False) -> str:
        """Archive one goal after explicit owner confirmation."""
        return await self._request("POST", "/agent/goals/archive", payload={"goal_id": goal_id, "confirmed": confirmed})

    async def draft_personal_mission(
        self, title: str, outcome: str, workstreams: list[dict], constraints: str = "",
        priority: int = 4, target_date: Optional[str] = None,
    ) -> str:
        """Draft a persistent multi-workstream mission; each workstream names a specialist role and executable steps."""
        return await self._request("POST", "/agent/missions", payload={
            "title": title, "outcome": outcome, "workstreams": workstreams,
            "constraints": constraints, "priority": priority, "target_date": target_date,
        })

    async def approve_personal_mission(
        self, goal_id: str, confirmed: bool = False, notify: bool = True, max_attempts: int = 1,
    ) -> str:
        """Explicitly approve and queue a previously drafted personal mission."""
        return await self._request("POST", "/agent/missions/approve", payload={
            "goal_id": goal_id, "confirmed": confirmed, "notify": notify, "max_attempts": max_attempts,
        })

    async def request_owner_approval(
        self, title: str, summary: str, category: str = "general",
        details: Optional[dict] = None, expires_minutes: int = 60,
    ) -> str:
        """Create a visible owner decision request; approval records a decision and never auto-executes the action."""
        return await self._request("POST", "/agent/approvals", payload={
            "category": category, "title": title, "summary": summary,
            "details": details or {}, "expires_minutes": expires_minutes,
        })

    async def list_owner_approvals(self, status: str = "pending", limit: int = 50) -> str:
        """List owner approval requests and their current state."""
        return await self._request("GET", "/agent/approvals", params={"status": status, "limit": limit})

    async def resolve_owner_approval(self, approval_id: str, decision: str, confirmed: bool = False) -> str:
        """Approve or reject a request after confirmation; this does not execute its proposed action."""
        return await self._request("POST", "/agent/approvals/resolve", payload={
            "approval_id": approval_id, "decision": decision, "confirmed": confirmed,
        })

    async def create_agent_routine(
        self, name: str, steps: list[dict], description: str = "",
        schedule_type: str = "on_demand", schedule: Optional[dict] = None, notify: bool = True,
    ) -> str:
        """Create a disabled recurring-routine draft; it cannot run until separately enabled."""
        return await self._request("POST", "/agent/routines", payload={
            "name": name, "description": description, "schedule_type": schedule_type,
            "schedule": schedule or {}, "steps": steps, "notify": notify,
        })

    async def list_agent_routines(self, status: str = "", limit: int = 50) -> str:
        """List persistent on-demand, interval, daily, and weekly routines."""
        return await self._request("GET", "/agent/routines", params={"status": status, "limit": limit})

    async def control_agent_routine(self, routine_id: str, action: str, confirmed: bool = False) -> str:
        """Enable, pause, archive, or run a routine now after explicit owner confirmation."""
        return await self._request("POST", "/agent/routines/control", payload={
            "routine_id": routine_id, "action": action, "confirmed": confirmed,
        })

    async def save_operator_preference(self, key: str, value: str, category: str = "general") -> str:
        """Save an explicit non-secret preference in the owner's personal operating manual."""
        return await self._request("POST", "/agent/manual", payload={"key": key, "value": value, "category": category})

    async def get_operator_manual(self, category: str = "") -> str:
        """Read preferences the owner explicitly asked Hermes to remember."""
        return await self._request("GET", "/agent/manual", params={"category": category})

    async def delete_operator_preference(self, key: str, confirmed: bool = False) -> str:
        """Delete a personal operating preference after explicit confirmation."""
        return await self._request("POST", "/agent/manual/delete", payload={"key": key, "confirmed": confirmed})

    async def list_agent_skills(self) -> str:
        """List Hermes core, optional, and integration skills and connection requirements."""
        return await self._request("GET", "/agent/skills")

    async def set_agent_skill_enabled(self, skill_id: str, enabled: bool, confirmed: bool = False) -> str:
        """Enable or disable a non-core skill after explicit confirmation."""
        return await self._request("POST", "/agent/skills", payload={
            "skill_id": skill_id, "enabled": enabled, "confirmed": confirmed,
        })

    async def get_current_workspace_context(
        self, include_recent_files: bool = True, save_snapshot: bool = False,
    ) -> str:
        """Inspect open windows, managed pages, and recent file metadata on explicit request; does not capture screen pixels or file contents."""
        return await self._request("GET", "/agent/context", params={
            "include_recent_files": include_recent_files, "save_snapshot": save_snapshot,
        })

    async def get_proactive_briefing(self) -> str:
        """Show pending decisions, deadlines, stale goals, and failed tasks without taking automatic action."""
        return await self._request("GET", "/agent/briefing")

    async def get_personal_timeline(self, limit: int = 50) -> str:
        """Read the metadata-only timeline of goals, missions, approvals, routines, and preferences."""
        return await self._request("GET", "/agent/timeline", params={"limit": limit})

    async def get_personal_command_center(self) -> str:
        """Get one dashboard of goals, tasks, approvals, routines, safety state, and suggestions."""
        return await self._request("GET", "/agent/command-center")
