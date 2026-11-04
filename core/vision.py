#!/usr/bin/env python3
"""Capture the desktop and analyze it with a selected cloud vision model."""

from __future__ import annotations

import argparse
import base64
import json
import platform_commands as subprocess
import sys
import urllib.request
from pathlib import Path

from model_runtime import provider_api_key, resolve_vision


BASE_DIR = Path(__file__).resolve().parent
SCREENSHOT_SCRIPT = BASE_DIR / "screenshot.py"


def _prompt(question: str) -> str:
    return (
        "Analyze this Linux desktop screenshot. Only describe things visible in the image. "
        "If text is unreadable, say so. Do not invent application names or UI elements.\n\n"
        + question
    )


def _request_json(url: str, payload: dict, headers: dict, timeout: int = 180) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _analyze_openai_compatible(provider: dict, question: str, image_data: str) -> str:
    key = provider_api_key(provider)
    result = _request_json(
        f"{provider['base_url']}/chat/completions",
        {
            "model": provider["model"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _prompt(question)},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                    ],
                }
            ],
            "temperature": 0,
        },
        {"Authorization": f"Bearer {key}"},
    )
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        content = "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
    return str(content).strip()


def analyze_screen(question: str, provider: str = "", model: str = "") -> dict:
    selected = resolve_vision(provider, model)
    capture = subprocess.run(
        [sys.executable, str(SCREENSHOT_SCRIPT), "capture"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    screenshot = json.loads(capture.stdout)
    if not screenshot.get("success"):
        raise RuntimeError(screenshot.get("error", "Capture failed"))

    image_path = Path(screenshot["path"])
    if image_path.parent.resolve() != (BASE_DIR / "screenshots").resolve():
        raise RuntimeError("Unexpected screenshot location")
    image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")

    if selected["type"] == "openai_compatible":
        description = _analyze_openai_compatible(selected, question, image_data)
    else:
        raise RuntimeError(f"Unsupported vision provider type: {selected['type']}")

    if not description:
        raise RuntimeError("Vision model returned an empty description")
    return {
        "success": True,
        "provider": selected["provider"],
        "model": selected["model"],
        "description": description,
        "screenshot": screenshot["filename"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="*", default=[])
    parser.add_argument("--provider", default="")
    parser.add_argument("--model", default="")
    args = parser.parse_args()
    question = " ".join(args.question).strip() or "Describe what is currently visible on the desktop."
    try:
        print(json.dumps(analyze_screen(question, args.provider, args.model)))
        return 0
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
