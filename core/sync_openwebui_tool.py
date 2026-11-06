"""Sync the canonical Hermes Workspace Tool source into Open WebUI."""

import importlib.util
import inspect
import json
import sqlite3
import sys
import time
import types
from pathlib import Path
from platform_support import openwebui_data_dir
from pydantic import TypeAdapter
from pydantic.fields import FieldInfo

ROOT = Path(__file__).resolve().parent
DB = openwebui_data_dir() / "webui.db"
SOURCE = ROOT / "openwebui_tool.py"
MODEL_INSTRUCTIONS = ROOT / "model_instructions.txt"


def json_object(value):
    """Decode a database JSON object, tolerating empty or legacy bad values."""
    try:
        decoded = json.loads(value or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}

PLAN_STEP_SCHEMA = {
    "type": "object",
    "description": "One executable Hermes task step. Put action arguments inside payload, not at the step's top level.",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["command", "write_files", "edit_files", "inspect_codebase", "search_code", "read_source", "git_review", "read_web_page", "download_web_file", "notification", "delay"],
            "description": "Action type. For a safe project inspection use inspect_codebase, search_code, or read_source.",
        },
        "payload": {
            "type": "object",
            "description": "Arguments for the action. Examples: inspect_codebase={root}; search_code={root,query}; read_source={path,start_line,end_line}; read_web_page={url}.",
        },
        "label": {"type": "string", "default": "", "description": "Short human-readable description of this step."},
        "depends_on": {"type": "array", "items": {"type": "integer", "minimum": 1}, "default": [], "description": "Earlier one-based step numbers that must finish first."},
        "estimated_seconds": {"type": "integer", "minimum": 1, "maximum": 1800, "default": 30},
    },
    "required": ["type", "payload"],
}


def generated_specs() -> list[dict]:
    """Build Open WebUI schemas from the canonical Tools class for fresh installs."""
    if importlib.util.find_spec("aiohttp") is None:
        # Schema generation never executes HTTP calls; this keeps bootstrap light.
        sys.modules.setdefault("aiohttp", types.ModuleType("aiohttp"))
    module_spec = importlib.util.spec_from_file_location("hermes_openwebui_tool", SOURCE)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("Could not load the canonical Hermes Workspace Tool")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    result = []
    for name, method in inspect.getmembers(module.Tools, inspect.iscoroutinefunction):
        if name.startswith("_"):
            continue
        properties = {}
        required = []
        for parameter_name, parameter in inspect.signature(method).parameters.items():
            if parameter_name == "self":
                continue
            annotation = parameter.annotation if parameter.annotation is not inspect.Parameter.empty else str
            schema = TypeAdapter(annotation).json_schema()
            default = parameter.default
            if isinstance(default, FieldInfo):
                if default.description:
                    schema["description"] = default.description
                if default.is_required():
                    required.append(parameter_name)
                elif default.default is not None:
                    schema["default"] = default.default
            elif default is inspect.Parameter.empty:
                required.append(parameter_name)
            else:
                schema["default"] = default
            properties[parameter_name] = schema
        description = (inspect.getdoc(method) or name.replace("_", " ")).split("\n\n", 1)[0]
        result.append({
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        })
    return result


def main():
    content = SOURCE.read_text(encoding="utf-8")
    compile(content, str(SOURCE), "exec")
    with sqlite3.connect(DB, timeout=10) as db:
        owner = db.execute("SELECT id FROM user ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END, created_at LIMIT 1").fetchone()
        if owner is None:
            raise RuntimeError("Open WebUI has no owner yet; create the first account, then run this sync again")
        # Rebuild schemas from the canonical source on every sync.  Reusing an
        # older database copy made newly added Hermes capabilities invisible.
        specs = generated_specs()
        specs = [item for item in specs if item.get("name") != "get_live_voice_status"]

        def put(spec):
            nonlocal specs
            specs = [item for item in specs if item.get("name") != spec["name"]]
            specs.append(spec)

        put({
                "name": "create_document",
                "description": "Create a new .txt document in the Hermes documents folder, verify its content, and never overwrite an existing file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "New .txt filename in the Hermes documents folder."},
                        "text": {"type": "string", "description": "Complete text to save in the new document."},
                    },
                    "required": ["filename", "text"],
                },
        })
        put({
            "name": "analyze_desktop_screen",
            "description": "Capture and analyze the current desktop using the active Workspace preset's vision provider/model. Explicit overrides are optional; cloud vision sends the screenshot to that provider.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "default": "Describe what is currently visible on my desktop."},
                    "provider": {"type": "string", "default": "", "description": "Optional provider override; normally leave blank to use the Workspace preset."},
                    "model": {"type": "string", "default": "", "description": "Optional model override; normally leave blank to use the Workspace preset."},
                },
                "required": [],
            },
        })
        additions = [
            ("get_platform_compatibility", "Report Linux distribution, CPU architecture, display session, browser, and available Hermes capabilities.", {}, []),
            ("get_graphical_appliance_readiness", "Check the intended i3-3220, 8 GB, Mint Cinnamon/X11 appliance profile, drivers, and required desktop utilities.", {}, []),
            ("get_desktop_monitor_layout", "List connected monitors, resolutions, positions, and the primary display.", {}, []),
            ("read_desktop_clipboard", "Read clipboard text only after explicit confirmation because the clipboard may contain secrets.", {"confirmed": {"type": "boolean", "default": False}}, []),
            ("write_desktop_clipboard", "Replace the desktop clipboard with supplied text.", {"text": {"type": "string"}}, ["text"]),
            ("get_desktop_audio_status", "Read speaker volume, mute state, and default audio devices.", {}, []),
            ("set_desktop_audio_volume", "Set default speaker volume from 0 to 150 percent.", {"percent": {"type": "integer", "minimum": 0, "maximum": 150}}, ["percent"]),
            ("set_desktop_audio_mute", "Mute or unmute the default speakers.", {"muted": {"type": "boolean"}}, ["muted"]),
            ("list_desktop_media_players", "List applications exposing standard Linux media controls.", {}, []),
            ("control_desktop_media", "Control play, pause, track navigation, or stop through MPRIS.", {"action": {"type": "string", "enum": ["play", "pause", "play-pause", "next", "previous", "stop"]}, "player": {"type": "string", "default": ""}}, ["action"]),
            ("list_desktop_workspaces", "List Cinnamon workspaces and identify the active workspace.", {}, []),
            ("switch_desktop_workspace", "Switch to an exact Cinnamon workspace number.", {"workspace": {"type": "integer", "minimum": 0, "maximum": 63}}, ["workspace"]),
            ("move_window_to_desktop_workspace", "Move an exact listed window to another workspace.", {"window_id": {"type": "string"}, "workspace": {"type": "integer", "minimum": 0, "maximum": 63}, "follow": {"type": "boolean", "default": False}}, ["window_id", "workspace"]),
            ("open_cinnamon_settings_panel", "Open an approved Cinnamon settings panel.", {"panel": {"type": "string", "enum": ["display", "sound", "keyboard", "mouse", "power", "network", "themes", "backgrounds", "fonts", "windows", "workspaces", "apps", "info"]}}, ["panel"]),
            ("lock_desktop_session", "Lock the desktop after explicit confirmation; global GUI control pauses until it is unlocked.", {"confirmed": {"type": "boolean", "default": False}}, []),
            ("get_desktop_network_status", "Read NetworkManager state and device connections without exposing credentials.", {}, []),
            ("get_appliance_power_policy", "Check whether Cinnamon may automatically suspend the always-on appliance while on AC power.", {}, []),
            ("enable_appliance_keep_awake", "Disable automatic AC suspend after explicit confirmation while preserving manual lock and shutdown.", {"confirmed": {"type": "boolean", "default": False}}, []),
            ("list_installed_applications", "List installed graphical applications and their launch IDs.", {"query": {"type": "string", "default": ""}}, []),
            ("launch_multiple_applications", "Open several installed graphical applications.", {"applications": {"type": "array", "items": {"type": "string"}}}, ["applications"]),
            ("open_file_folder_or_url", "Open a file, folder, or HTTP/HTTPS URL.", {"target": {"type": "string"}}, ["target"]),
            ("write_text_file", "Create source code or text atomically. Existing files require explicit overwrite approval.", {"path": {"type": "string"}, "content": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}}, ["path", "content"]),
            ("append_text_file", "Append text to a file.", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
            ("create_folder", "Create a folder and missing parent folders.", {"path": {"type": "string"}}, ["path"]),
            ("copy_file_or_folder", "Copy a file or folder.", {"source": {"type": "string"}, "destination": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}}, ["source", "destination"]),
            ("move_file_or_folder", "Move or rename a file or folder.", {"source": {"type": "string"}, "destination": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}}, ["source", "destination"]),
            ("move_file_or_folder_to_trash", "Move a file or folder to recoverable Trash. Ask the user first.", {"path": {"type": "string"}}, ["path"]),
            ("run_development_command", "Run a coding, build, test, Git, or inspection command in a filesystem sandbox.", {"program": {"type": "string"}, "arguments": {"type": "array", "items": {"type": "string"}, "default": []}, "cwd": {"type": "string", "default": "~/hermes-v4"}, "timeout_seconds": {"type": "integer", "default": 30, "minimum": 1, "maximum": 180}}, ["program"]),
            ("get_computer_status", "Get OS, uptime, disk space, and writable folders.", {}, []),
            ("list_running_processes", "List running processes, optionally filtered.", {"query": {"type": "string", "default": ""}, "limit": {"type": "integer", "default": 50}}, []),
            ("show_desktop_notification", "Display a notification on the Linux desktop.", {"title": {"type": "string"}, "message": {"type": "string"}}, ["title", "message"]),
            ("close_desktop_window", "Close an exact desktop window after listing windows first.", {"window_id": {"type": "string"}}, ["window_id"]),
            ("send_key_sequence_to_application", "Focus an application and send key combinations in order.", {"class_name": {"type": "string"}, "keys": {"type": "array", "items": {"type": "string"}}}, ["class_name", "keys"]),
            ("drag_mouse", "Drag the mouse between two screen coordinates.", {"start_x": {"type": "integer"}, "start_y": {"type": "integer"}, "end_x": {"type": "integer"}, "end_y": {"type": "integer"}, "button": {"type": "integer", "default": 1}}, ["start_x", "start_y", "end_x", "end_y"]),
            ("manage_desktop_window", "Maximize, restore, minimize, move, or resize an exact window.", {"window_id": {"type": "string"}, "action": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}, "width": {"type": "integer"}, "height": {"type": "integer"}}, ["window_id", "action"]),
            ("type_into_exact_window", "Focus an exact window and type single-line or multiline text.", {"window_id": {"type": "string"}, "text": {"type": "string"}, "replace_selection": {"type": "boolean", "default": False}}, ["window_id", "text"]),
            ("inspect_codebase", "Inspect a project tree, languages, important files, and Git status.", {"root": {"type": "string"}, "max_files": {"type": "integer", "default": 500}, "max_depth": {"type": "integer", "default": 5}}, ["root"]),
            ("search_code", "Search source code by literal text or regular expression.", {"root": {"type": "string"}, "query": {"type": "string"}, "glob": {"type": "string", "default": ""}, "regex": {"type": "boolean", "default": False}, "limit": {"type": "integer", "default": 100}}, ["root", "query"]),
            ("read_source_range", "Read an exact numbered range from a source file.", {"path": {"type": "string"}, "start_line": {"type": "integer", "default": 1}, "end_line": {"type": "integer", "default": 300}}, ["path"]),
            ("write_multiple_files", "Create or explicitly overwrite up to 30 source files in one batch.", {"root": {"type": "string"}, "files": {"type": "array", "items": {"type": "object"}}}, ["root", "files"]),
            ("edit_multiple_files", "Apply validated exact multiline replacements across source files.", {"root": {"type": "string"}, "edits": {"type": "array", "items": {"type": "object"}}}, ["root", "edits"]),
            ("review_git_changes", "Review Git status plus staged and unstaged diffs.", {"root": {"type": "string"}}, ["root"]),
            ("create_git_commit", "Create a local commit only after explicit user confirmation.", {"root": {"type": "string"}, "message": {"type": "string"}, "paths": {"type": "array", "items": {"type": "string"}, "default": []}, "confirmed": {"type": "boolean", "default": False}}, ["root", "message"]),
            ("open_codebase_in_editor", "Open a codebase in Visual Studio Code.", {"root": {"type": "string"}}, ["root"]),
            ("open_browser_tabs", "Open HTTP or HTTPS URLs as browser tabs.", {"urls": {"type": "array", "items": {"type": "string"}}, "browser": {"type": "string", "default": "chrome"}}, ["urls"]),
            ("navigate_browser_window", "Navigate an exact Chrome or Firefox window to a URL.", {"window_id": {"type": "string"}, "url": {"type": "string"}}, ["window_id", "url"]),
            ("read_web_page", "Fetch a webpage and return title, visible text, and links.", {"url": {"type": "string"}}, ["url"]),
            ("download_web_file", "Download a file up to 50 MB into Downloads without overwriting.", {"url": {"type": "string"}, "filename": {"type": "string"}}, ["url", "filename"]),
            ("start_managed_browser", "Start or reuse the dedicated visible Chrome session and optionally open pages.", {"urls": {"type": "array", "items": {"type": "string"}, "default": []}}, []),
            ("list_managed_browser_pages", "List page IDs, titles, and URLs in managed Chrome.", {}, []),
            ("snapshot_browser_page", "Read visible page text and numbered interactive elements.", {"page_id": {"type": "string"}}, ["page_id"]),
            ("interact_with_browser_page", "Navigate, click, type, select, check, submit, or navigate history on a managed page.", {"page_id": {"type": "string"}, "action": {"type": "string"}, "target": {"type": "integer"}, "value": {"type": "string", "default": ""}, "url": {"type": "string", "default": ""}, "confirmed": {"type": "boolean", "default": False}}, ["page_id", "action"]),
            ("upload_file_to_browser_page", "Upload an approved local file to a numbered input after explicit confirmation.", {"page_id": {"type": "string"}, "target": {"type": "integer"}, "path": {"type": "string"}, "confirmed": {"type": "boolean", "default": False}}, ["page_id", "target", "path"]),
            ("wait_for_browser_text", "Wait for expected text to appear on a managed page.", {"page_id": {"type": "string"}, "text": {"type": "string"}, "timeout_seconds": {"type": "integer", "default": 20}}, ["page_id", "text"]),
            ("capture_browser_page", "Save a managed browser page screenshot in Pictures/Hermes.", {"page_id": {"type": "string"}, "filename": {"type": "string"}}, ["page_id", "filename"]),
            ("close_managed_browser_page", "Close one exact managed browser page.", {"page_id": {"type": "string"}}, ["page_id"]),
            ("create_background_workflow", "Queue a checkpointed coding or web workflow that survives restarts.", {"name": {"type": "string"}, "steps": {"type": "array", "items": {"type": "object"}}, "scheduled_for": {"type": "string"}, "notify": {"type": "boolean", "default": True}, "max_attempts": {"type": "integer", "default": 1}}, ["name", "steps"]),
            ("list_background_tasks", "List recent persistent tasks, optionally filtered by status.", {"status": {"type": "string", "default": ""}, "limit": {"type": "integer", "default": 20}}, []),
            ("get_background_task", "Get a background task checkpoint, results, and errors.", {"task_id": {"type": "string"}}, ["task_id"]),
            ("control_background_task", "Pause, resume, cancel, or retry a persistent task.", {"task_id": {"type": "string"}, "action": {"type": "string"}}, ["task_id", "action"]),
            ("get_hermes_health_report", "Get health for services, endpoints, tasks, disk, backups, and Tailscale.", {}, []),
            ("create_hermes_backup", "Create an owner-only local Hermes backup.", {}, []),
            ("list_hermes_backups", "List retained local Hermes backups.", {}, []),
            ("remember_fact", "Store a user-approved preference or fact without storing credentials or secrets.", {"content": {"type": "string"}, "category": {"type": "string", "default": "general"}, "tags": {"type": "array", "items": {"type": "string"}, "default": []}, "source": {"type": "string", "default": "user"}, "importance": {"type": "integer", "default": 3, "minimum": 1, "maximum": 5}}, ["content"]),
            ("recall_memories", "Search Hermes memory for relevant non-archived facts and preferences.", {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, ["query"]),
            ("list_memories", "List stored memories, optionally including archived entries.", {"category": {"type": "string", "default": ""}, "include_archived": {"type": "boolean", "default": False}, "limit": {"type": "integer", "default": 50}}, []),
            ("forget_memory", "Archive one memory after explicit confirmation.", {"memory_id": {"type": "string"}, "confirmed": {"type": "boolean", "default": False}}, ["memory_id"]),
            ("get_memory_briefing", "Return concise relevant memory before a task.", {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, ["query"]),
            ("find_duplicate_memories", "Find exact duplicate active memories without modifying them.", {"limit": {"type": "integer", "default": 50}}, []),
            ("draft_execution_plan", "Draft a dependency-aware execution plan. You must create the ordered steps yourself using the exact type/payload schema; do not ask the user to supply internal step objects.", {"goal": {"type": "string", "description": "Clear outcome requested by the user."}, "steps": {"type": "array", "minItems": 1, "maxItems": 30, "items": PLAN_STEP_SCHEMA}, "constraints": {"type": "string", "default": "", "description": "Optional safety, scope, or timing limits. Use an empty string when none were provided."}}, ["goal", "steps"]),
            ("get_execution_plan", "Read a plan, its risks, and linked task status.", {"plan_id": {"type": "string"}}, ["plan_id"]),
            ("list_execution_plans", "List recent Hermes plans.", {"limit": {"type": "integer", "default": 20}}, []),
            ("approve_execution_plan", "Approve and queue a drafted plan after explicit user confirmation.", {"plan_id": {"type": "string"}, "confirmed": {"type": "boolean", "default": False}, "notify": {"type": "boolean", "default": True}, "max_attempts": {"type": "integer", "default": 1}}, ["plan_id"]),
            ("revise_execution_plan", "Create a corrected draft from an earlier plan; it still requires separate approval to run.", {"plan_id": {"type": "string"}, "steps": {"type": "array", "items": PLAN_STEP_SCHEMA}, "constraints": {"type": "string", "default": ""}}, ["plan_id", "steps"]),
            ("get_security_dashboard", "Show safety mode, task counts, audit summary, and backup-encryption readiness.", {}, []),
            ("set_hermes_safety_mode", "Set normal, read_only, or stopped mode only after explicit confirmation.", {"mode": {"type": "string", "enum": ["normal", "read_only", "stopped"]}, "confirmed": {"type": "boolean", "default": False}}, ["mode"]),
            ("emergency_stop_hermes", "Block new privileged actions and cancel active background work after explicit confirmation.", {"confirmed": {"type": "boolean", "default": False}}, []),
            ("get_integration_status", "Show authorized Open WebUI MCP/tool-server connection readiness without exposing secrets.", {}, []),
            ("get_backup_encryption_status", "Check encrypted backup readiness without exposing keys or passphrases.", {}, []),
            ("create_encrypted_hermes_backup", "Create encrypted backup copy only if the owner configured a GPG recipient.", {}, []),
            ("get_model_runtime_status", "List the default vision selection and provider readiness without exposing API keys.", {}, []),
            ("configure_vision_model", "Change the default cloud vision provider/model after explicit user confirmation. API keys must be configured outside chat.", {"provider": {"type": "string", "enum": ["openai_compatible", "nvidia"]}, "model": {"type": "string"}, "base_url": {"type": "string", "default": ""}, "enabled": {"type": "boolean", "default": False}, "confirmed": {"type": "boolean", "default": False}}, ["provider", "model"]),
        ]
        for name, description, properties, required in additions:
            put({"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required}})
        tool_meta = {
            "i18n": {},
            "description": "Hermes Alpha desktop, browser, code, memory, planning, web, and replaceable-vision tools.",
            "manifest": {
                "title": "Hermes Alpha Smart Operator",
                "author": "Hermes",
                "version": "alpha",
            "description": "Canonical cloud-model Hermes Workspace Tool with local computer control.",
            },
            "has_user_valves": False,
        }
        now = int(time.time())
        db.execute(
            "INSERT INTO tool(id,user_id,name,content,specs,meta,valves,updated_at,created_at,version_id) VALUES(?,?,?,?,?,?,NULL,?,?,NULL) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name,content=excluded.content,specs=excluded.specs,meta=excluded.meta,updated_at=excluded.updated_at",
            ("hermes_v4", owner[0], "Hermes Alpha Smart Operator", content, json.dumps(specs), json.dumps(tool_meta), now, now),
        )
        row = db.execute("SELECT user_id,params,meta,created_at FROM model WHERE id=?", ("hermes-v4",)).fetchone()
        if row is None:
            base_meta = {
                "description": "Hermes cloud assistant with local computer tools.",
                "capabilities": {"web_search": True, "builtin_tools": True},
                "toolIds": ["hermes_v4"],
            }
            db.execute(
                "INSERT INTO model(id,user_id,base_model_id,name,params,meta,updated_at,created_at,is_active,version_id) VALUES(?,?,?,?,?,?,?,?,1,NULL)",
                ("hermes-v4", owner[0], "nvidia/nemotron-3-ultra-550b-a55b", "Hermes Alpha", json.dumps({"function_calling": "native"}), json.dumps(base_meta), now, now),
            )
            row = db.execute("SELECT user_id,params,meta,created_at FROM model WHERE id=?", ("hermes-v4",)).fetchone()
        owner_id, params_json, meta_json, created_at = row
        params = json_object(params_json)
        params["system"] = MODEL_INSTRUCTIONS.read_text(encoding="utf-8").strip()
        meta = json_object(meta_json)
        # Preserve Open WebUI's standard visual design. Remove legacy appearance
        # fields previously written by Hermes while keeping functional metadata.
        meta.pop("profile_image_url", None)
        meta.pop("suggestion_prompts", None)
        capabilities = meta.setdefault("capabilities", {})
        capabilities["web_search"] = True
        capabilities["builtin_tools"] = True
        meta.setdefault("builtinTools", {})["web_search"] = True
        default_features = meta.setdefault("defaultFeatureIds", [])
        if "web_search" not in default_features:
            default_features.append("web_search")
        meta["hermesVision"] = {"provider": "nvidia", "model": "nvidia/nemotron-3.5-super-vl-120b-a12b"}
        meta["toolIds"] = ["hermes_v4"]
        profiles = [
            ("hermes-v4", "Hermes Alpha", "nvidia/nemotron-3-ultra-550b-a55b", "Maximum reasoning and capability; Super VL handles vision."),
            ("hermes-cloud-preview", "Hermes Beta", "nvidia/nemotron-3.5-super-vl-120b-a12b", "Balanced multimodal cloud model for everyday work."),
            ("hermes-gamma", "Hermes Gamma", "nvidia/nemotron-3.5-lightning-30b-a3b", "Fast lightweight cloud model; Super VL handles vision."),
        ]
        for model_id, name, base_model, description in profiles:
            profile_meta = json.loads(json.dumps(meta))
            profile_meta["description"] = description
            profile_params = json.loads(json.dumps(params))
            if model_id == "hermes-gamma":
                profile_params["chat_template_kwargs"] = {"enable_thinking": False}
            else:
                profile_params.pop("chat_template_kwargs", None)
            db.execute(
                "INSERT INTO model(id,user_id,base_model_id,name,params,meta,updated_at,created_at,is_active,version_id) "
                "VALUES(?,?,?,?,?,?,strftime('%s','now'),?,1,NULL) "
                "ON CONFLICT(id) DO UPDATE SET base_model_id=excluded.base_model_id,name=excluded.name,params=excluded.params,meta=excluded.meta,updated_at=excluded.updated_at,is_active=1",
                (model_id, owner_id, base_model, name, json.dumps(profile_params), json.dumps(profile_meta), created_at),
            )
        config_updates = {
            "web.search.enable": True,
            "web.search.engine": "duckduckgo",
            "web.search.ddgs_backend": "auto",
            "web.search.result_count": 5,
            "models.default_metadata": {
                "capabilities": {"web_search": True, "builtin_tools": True},
                "builtinTools": {"web_search": True},
                "defaultFeatureIds": ["web_search"],
            },
            "models.default_params": {"function_calling": "native"},
            "ollama.enable": False,
            "ollama.base_urls": [],
            "ollama.api_configs": {},
            "rag.embedding_engine": "openai",
            "rag.embedding_model": "nvidia/nemotron-3-embed-1b",
            "rag.openai.api_base_url": "https://integrate.api.nvidia.com/v1",
            "audio.stt.engine": "deepgram",
            "audio.stt.model": "nova-3",
            "audio.tts.engine": "elevenlabs",
        }
        connection_rows = dict(db.execute(
            "SELECT key,value FROM config WHERE key IN ('openai.api_base_urls','openai.api_keys')"
        ).fetchall())
        try:
            connection_urls = json.loads(connection_rows.get("openai.api_base_urls", "[]"))
            connection_keys = json.loads(connection_rows.get("openai.api_keys", "[]"))
            for index, url in enumerate(connection_urls):
                if str(url).rstrip("/") == "https://integrate.api.nvidia.com/v1" and index < len(connection_keys) and connection_keys[index]:
                    config_updates["rag.openai.api_key"] = connection_keys[index]
                    break
        except (json.JSONDecodeError, TypeError):
            pass
        for key, value in config_updates.items():
            db.execute(
                "INSERT INTO config(key,value,updated_at) VALUES(?,?,strftime('%s','now')) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, json.dumps(value)),
            )
        # Old releases customized these interface keys. Deleting only those
        # values lets Open WebUI apply its own defaults without touching chats,
        # provider connections, tools, models, accounts, or secrets.
        db.executemany("DELETE FROM config WHERE key=?", [
            (key,) for key in (
                "ui.default_models", "ui.model_order_list",
                "ui.default_pinned_models", "ui.prompt_suggestions",
                "ui.default_interface_settings", "ui.enable_community_sharing",
                "ui.enable_message_rating",
            )
        ])
    print(f"Hermes Workspace Tool synced: {len(specs)} functions")


if __name__ == "__main__":
    main()
