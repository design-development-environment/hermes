#!/usr/bin/env python3
"""Create a Hermes Workspace preset around any Open WebUI base model."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from platform_support import openwebui_data_dir


DATABASE = openwebui_data_dir() / "webui.db"
TEMPLATE_ID = "hermes-v4"
SAFE_ID = re.compile(r"^[A-Za-z0-9._:/@+-]{1,200}$")


def create_preset(preset_id: str, name: str, base_model: str, vision_provider: str, vision_model: str, description: str) -> dict:
    for label, value in (("preset ID", preset_id), ("base model", base_model), ("vision model", vision_model)):
        if not SAFE_ID.fullmatch(value):
            raise ValueError(f"Invalid {label}")
    if preset_id == TEMPLATE_ID:
        raise ValueError("The canonical Hermes Alpha preset cannot be overwritten")
    with closing(sqlite3.connect(DATABASE, timeout=10)) as db, db:
        template = db.execute(
            "SELECT user_id,params,meta FROM model WHERE id=?", (TEMPLATE_ID,)
        ).fetchone()
        if template is None:
            raise RuntimeError("Hermes Alpha template was not found")
        if db.execute("SELECT 1 FROM model WHERE id=?", (preset_id,)).fetchone():
            raise FileExistsError(f"Workspace model already exists: {preset_id}")
        params = json.loads(template[1])
        params["function_calling"] = "native"
        meta = copy.deepcopy(json.loads(template[2]))
        meta["description"] = description or f"Hermes Alpha tools on {base_model}"
        meta["toolIds"] = ["hermes_v4"]
        meta["hermesVision"] = {"provider": vision_provider, "model": vision_model}
        capabilities = meta.setdefault("capabilities", {})
        capabilities.update({"web_search": True, "builtin_tools": True})
        meta.setdefault("builtinTools", {})["web_search"] = True
        features = meta.setdefault("defaultFeatureIds", [])
        if "web_search" not in features:
            features.append("web_search")
        now = int(time.time())
        db.execute(
            "INSERT INTO model(id,user_id,base_model_id,name,params,meta,updated_at,created_at,is_active,version_id) VALUES(?,?,?,?,?,?,?,?,?,NULL)",
            (preset_id, template[0], base_model, name, json.dumps(params), json.dumps(meta), now, now, True),
        )
    return {
        "created": True,
        "id": preset_id,
        "name": name,
        "base_model": base_model,
        "vision": {"provider": vision_provider, "model": vision_model},
        "tool": "Hermes Alpha Smart Operator",
        "web_search_default": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--vision-provider", default="nvidia")
    parser.add_argument("--vision-model", default="nvidia/nemotron-3.5-super-vl-120b-a12b")
    parser.add_argument("--description", default="")
    args = parser.parse_args()
    print(json.dumps(create_preset(args.id, args.name, args.base_model, args.vision_provider, args.vision_model, args.description), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
