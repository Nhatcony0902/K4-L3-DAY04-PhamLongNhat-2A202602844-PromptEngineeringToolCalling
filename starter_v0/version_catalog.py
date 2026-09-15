"""Rebuild each logged artifact version from git history.

Reads artifacts/version_log.csv (version, prompt_hash, tools_hash) and finds the
committed system_prompt.md / tools.yaml whose sha256 matches each logged hash,
so the compare UI runs exactly the artifacts that produced each eval run.
"""
from __future__ import annotations

import csv
import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from versioning import ArtifactVersion

ROOT = Path(__file__).parent
VERSION_LOG = ROOT / "artifacts" / "version_log.csv"
ARTIFACT_FILES = {"prompt": "artifacts/system_prompt.md", "tools": "artifacts/tools.yaml"}


@dataclass(frozen=True)
class CatalogVersion:
    version: ArtifactVersion
    system_prompt: str
    tool_declarations: list[dict[str, Any]]
    prompt_commit: str
    tools_commit: str


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def _blobs_by_hash(relative_path: str) -> dict[str, tuple[str, bytes]]:
    """Map sha256 -> (commit, content) for every committed revision plus the working tree."""
    found: dict[str, tuple[str, bytes]] = {}
    working = ROOT / relative_path
    if working.exists():
        content = working.read_bytes()
        found[hashlib.sha256(content).hexdigest()] = ("working-tree", content)
    for commit in _git("log", "--format=%H", "--", relative_path).decode().split():
        try:
            content = _git("show", f"{commit}:./{relative_path}")
        except subprocess.CalledProcessError:
            continue
        found.setdefault(hashlib.sha256(content).hexdigest(), (commit[:7], content))
    return found


def _lookup(blobs: dict[str, tuple[str, bytes]], short_hash: str) -> tuple[str, str, bytes] | None:
    for full_hash, (commit, content) in blobs.items():
        if short_hash and full_hash.startswith(short_hash):
            return full_hash, commit, content
    return None


def load_catalog() -> tuple[list[CatalogVersion], list[str]]:
    """Return (resolved versions in log order, human-readable errors for unresolved rows)."""
    rows = list(csv.DictReader(VERSION_LOG.open(encoding="utf-8", newline="")))
    prompt_blobs = _blobs_by_hash(ARTIFACT_FILES["prompt"])
    tools_blobs = _blobs_by_hash(ARTIFACT_FILES["tools"])
    versions: list[CatalogVersion] = []
    errors: list[str] = []
    for row in rows:
        prompt = _lookup(prompt_blobs, row["prompt_hash"].strip())
        tools = _lookup(tools_blobs, row["tools_hash"].strip())
        if prompt is None or tools is None:
            missing = "system_prompt.md" if prompt is None else "tools.yaml"
            errors.append(f"{row['version']}: no committed {missing} matches the hash in version_log.csv")
            continue
        prompt_hash, prompt_commit, prompt_bytes = prompt
        tools_hash, tools_commit, tools_bytes = tools
        label = row["version"].strip()
        versions.append(CatalogVersion(
            version=ArtifactVersion(
                version=label,
                artifact_version=f"{label}+p{prompt_hash[:12]}+t{tools_hash[:12]}",
                prompt_hash=prompt_hash,
                tools_hash=tools_hash,
            ),
            system_prompt=prompt_bytes.decode("utf-8"),
            tool_declarations=yaml.safe_load(tools_bytes.decode("utf-8"))["tools"],
            prompt_commit=prompt_commit,
            tools_commit=tools_commit,
        ))
    return versions, errors
