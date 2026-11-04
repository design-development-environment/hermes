#!/usr/bin/env python3
"""Hermes V5.3 codebase inspection and multi-file editing tools."""

from __future__ import annotations

import os
import fnmatch
import re
import shutil
import platform_commands as subprocess
from collections import Counter, defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from computer_control import MAX_TEXT_BYTES, writable_path


router = APIRouter(prefix="/code", tags=["Hermes V5.3 codebase operator"])
IGNORED_DIRS = {
    ".git", ".idea", ".next", ".pytest_cache", ".venv", ".vscode",
    "__pycache__", "build", "coverage", "dist", "node_modules", "target",
}
MAX_BATCH_BYTES = 3_000_000


def project_root(value: str) -> Path:
    root = writable_path(value)
    if not root.is_dir():
        raise HTTPException(400, "Codebase root is not a folder")
    return root


def source_path(value: str, root: Path | None = None, *, may_not_exist=False) -> Path:
    raw = Path(value).expanduser()
    if root is not None and not raw.is_absolute():
        raw = root / raw
    path = writable_path(str(raw), may_not_exist=may_not_exist)
    if root and path != root and root not in path.parents:
        raise HTTPException(403, "File is outside the selected codebase")
    return path


def atomic_text_write(path: Path, content: str):
    temporary = path.with_name(f".{path.name}.hermes-{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_git(root: Path, *args: str, timeout=20):
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True,
        timeout=timeout, check=False,
    )


class CodebaseRequest(BaseModel):
    root: str = Field(min_length=1, max_length=2000)


class SearchCodeRequest(CodebaseRequest):
    query: str = Field(min_length=1, max_length=500)
    glob: str | None = Field(default=None, max_length=200)
    regex: bool = False
    limit: int = Field(default=100, ge=1, le=500)


class ReadRangeRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2000)
    start_line: int = Field(default=1, ge=1)
    end_line: int = Field(default=300, ge=1)


class FileWrite(BaseModel):
    path: str = Field(min_length=1, max_length=2000)
    content: str = Field(max_length=2_000_000)
    overwrite: bool = False


class BatchWriteRequest(CodebaseRequest):
    files: list[FileWrite] = Field(min_length=1, max_length=30)


class TextEdit(BaseModel):
    path: str = Field(min_length=1, max_length=2000)
    old_text: str = Field(min_length=1, max_length=500_000)
    new_text: str = Field(max_length=500_000)
    expected_occurrences: int = Field(default=1, ge=1, le=100)


class BatchEditRequest(CodebaseRequest):
    edits: list[TextEdit] = Field(min_length=1, max_length=50)


class GitCommitRequest(CodebaseRequest):
    message: str = Field(min_length=1, max_length=300)
    paths: list[str] = Field(default_factory=list, max_length=100)
    confirmed: bool = False


@router.post("/inspect", operation_id="inspect_codebase")
def inspect_codebase(request: CodebaseRequest, max_files: int = 500, max_depth: int = 5):
    root = project_root(request.root)
    max_files = max(1, min(max_files, 2000))
    max_depth = max(1, min(max_depth, 10))
    files = []
    extensions = Counter()
    skipped = 0
    for current, dirs, names in os.walk(root):
        relative = Path(current).relative_to(root)
        depth = len(relative.parts)
        dirs[:] = [] if depth >= max_depth else [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        for name in sorted(names):
            if name.startswith(".") and name not in {".gitignore"}:
                continue
            path = Path(current) / name
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                rel = str(path.relative_to(root))
                files.append(rel)
                extensions[path.suffix.lower() or "[no extension]"] += 1
                if len(files) >= max_files:
                    skipped += 1
                    break
            except OSError:
                skipped += 1
        if len(files) >= max_files:
            break
    git = run_git(root, "status", "--short", "--branch")
    important = [name for name in ("AGENTS.md", "README.md", "README", "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "requirements.txt") if (root / name).is_file()]
    return {
        "root": str(root), "files": files, "file_count_returned": len(files),
        "limit_reached": len(files) >= max_files, "skipped": skipped,
        "extensions": dict(extensions.most_common()), "important_files": important,
        "git": git.stdout[-20_000:] if git.returncode == 0 else None,
    }


@router.post("/search", operation_id="search_code")
def search_code(request: SearchCodeRequest):
    root = project_root(request.root)
    ripgrep = shutil.which("rg")
    if ripgrep:
        command = [ripgrep, "--line-number", "--column", "--no-heading", "--color", "never"]
        if not request.regex:
            command.append("--fixed-strings")
        if request.glob:
            command += ["--glob", request.glob]
        command += ["--", request.query, str(root)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        if result.returncode not in (0, 1):
            raise HTTPException(400, result.stderr[-2000:] or "Code search failed")
        lines = result.stdout.splitlines()
        return {"query": request.query, "matches": lines[:request.limit], "limit_reached": len(lines) > request.limit, "engine": "ripgrep"}

    try:
        pattern = re.compile(request.query if request.regex else re.escape(request.query))
    except re.error as error:
        raise HTTPException(400, f"Invalid regular expression: {error}")
    matches = []
    limit_reached = False
    for current, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        for name in names:
            path = Path(current) / name
            relative = str(path.relative_to(root))
            if request.glob and not fnmatch.fnmatch(relative, request.glob) and not fnmatch.fnmatch(name, request.glob):
                continue
            try:
                if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_TEXT_BYTES:
                    continue
                with path.open("r", encoding="utf-8") as handle:
                    for number, line in enumerate(handle, 1):
                        match = pattern.search(line)
                        if match:
                            matches.append(f"{path}:{number}:{match.start() + 1}:{line.rstrip()}")
                            if len(matches) > request.limit:
                                limit_reached = True
                                break
            except (OSError, UnicodeDecodeError):
                continue
            if limit_reached:
                break
        if limit_reached:
            break
    return {"query": request.query, "matches": matches[:request.limit], "limit_reached": limit_reached, "engine": "python-fallback"}


@router.post("/read", operation_id="read_source_range")
def read_source_range(request: ReadRangeRequest):
    path = source_path(request.path)
    if not path.is_file():
        raise HTTPException(400, "Path is not a regular file")
    if request.end_line < request.start_line or request.end_line - request.start_line > 999:
        raise HTTPException(400, "Read at most 1000 lines in ascending order")
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise HTTPException(413, "File exceeds the 2 MB source read limit")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        raise HTTPException(415, "File is not UTF-8 text")
    selected = lines[request.start_line - 1:request.end_line]
    numbered = [f"{number}: {line}" for number, line in enumerate(selected, request.start_line)]
    return {"path": str(path), "start_line": request.start_line, "end_line": min(request.end_line, len(lines)), "total_lines": len(lines), "content": "\n".join(numbered)}


@router.post("/write-batch", operation_id="write_multiple_files")
def write_multiple_files(request: BatchWriteRequest):
    root = project_root(request.root)
    prepared = []
    total = 0
    for item in request.files:
        path = source_path(item.path, root, may_not_exist=True)
        encoded = item.content.encode("utf-8")
        total += len(encoded)
        if total > MAX_BATCH_BYTES:
            raise HTTPException(413, "Batch exceeds the 3 MB limit")
        if path.exists() and not item.overwrite:
            raise HTTPException(409, f"File exists and overwrite was not approved: {path}")
        if path.exists() and not path.is_file():
            raise HTTPException(400, f"Target is not a regular file: {path}")
        prepared.append((path, item.content, path.exists()))
    results = []
    for path, content, existed in prepared:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_text_write(path, content)
        results.append({"path": str(path), "bytes": path.stat().st_size, "operation": "updated" if existed else "created"})
    return {"success": True, "root": str(root), "files": results, "total_bytes": total}


@router.post("/edit-batch", operation_id="edit_multiple_files")
def edit_multiple_files(request: BatchEditRequest):
    root = project_root(request.root)
    content_by_path = {}
    changes = defaultdict(int)
    for edit in request.edits:
        path = source_path(edit.path, root)
        if not path.is_file() or path.stat().st_size > MAX_TEXT_BYTES:
            raise HTTPException(400, f"Source file is missing or too large: {path}")
        if path not in content_by_path:
            try:
                content_by_path[path] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                raise HTTPException(415, f"Source file is not UTF-8: {path}")
        count = content_by_path[path].count(edit.old_text)
        if count != edit.expected_occurrences:
            raise HTTPException(409, f"Expected {edit.expected_occurrences} match(es) in {path}, found {count}; no files changed")
        content_by_path[path] = content_by_path[path].replace(edit.old_text, edit.new_text)
        changes[path] += count
    total = sum(len(text.encode("utf-8")) for text in content_by_path.values())
    if total > MAX_BATCH_BYTES:
        raise HTTPException(413, "Edited files exceed the 3 MB batch limit")
    for path, content in content_by_path.items():
        atomic_text_write(path, content)
    return {"success": True, "files": [{"path": str(path), "replacements": changes[path], "bytes": path.stat().st_size} for path in content_by_path]}


@router.post("/git-review", operation_id="review_git_changes")
def review_git_changes(request: CodebaseRequest):
    root = project_root(request.root)
    status = run_git(root, "status", "--short", "--branch")
    if status.returncode:
        raise HTTPException(400, "Folder is not a Git repository")
    diff = run_git(root, "diff", "--no-ext-diff", "--unified=3", timeout=30)
    staged = run_git(root, "diff", "--cached", "--no-ext-diff", "--unified=3", timeout=30)
    return {"root": str(root), "status": status.stdout, "unstaged_diff": diff.stdout[-60_000:], "staged_diff": staged.stdout[-60_000:], "truncated": len(diff.stdout) > 60_000 or len(staged.stdout) > 60_000}


@router.post("/git-commit", operation_id="create_git_commit")
def create_git_commit(request: GitCommitRequest):
    if not request.confirmed:
        raise HTTPException(403, "Commit confirmation is required")
    root = project_root(request.root)
    if run_git(root, "rev-parse", "--is-inside-work-tree").returncode:
        raise HTTPException(400, "Folder is not a Git repository")
    paths = request.paths or ["."]
    add = run_git(root, "add", "--", *paths)
    if add.returncode:
        raise HTTPException(400, add.stderr[-4000:] or "Git add failed")
    commit = run_git(root, "commit", "-m", request.message, timeout=60)
    return {"success": commit.returncode == 0, "stdout": commit.stdout[-10_000:], "stderr": commit.stderr[-10_000:]}


@router.post("/open-editor", operation_id="open_codebase_in_editor")
def open_codebase_in_editor(request: CodebaseRequest):
    root = project_root(request.root)
    process = subprocess.Popen(["code", "--new-window", str(root)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"success": True, "root": str(root), "editor": "Visual Studio Code", "process_id": process.pid}
