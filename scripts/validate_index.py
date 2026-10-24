#!/usr/bin/env python3
"""Validates index.yaml: schema, and for every entry that its commit and path exist and its tree hash matches.

Usage:  python scripts/validate_index.py [--index index.yaml] [--self-url URL ...] [--offline]

* Schema checks need only PyYAML.
* The hash check clones each entry's repository (an entry whose url equals a --self-url is read from this checkout, so
  a pull request can add a pack and its entry together once the pack commit exists on the branch).
* The tree hash is Calcifer's own (`calcifer.app.external_packs.tree_hash`) when Calcifer is installed; otherwise the
  vendored copy below, which implements the same algorithm. CI installs Calcifer so the canonical one is used.
* --offline skips the clone and hash checks (schema only).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,29}$")
GIT_URL_RE = re.compile(r"^(?:https|ssh)://[^\s\x00]+$")
SUBDIR_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*(?:/[A-Za-z0-9_][A-Za-z0-9._-]*)*$")
FIELDS = {
    "name",
    "description",
    "url",
    "path",
    "commit",
    "sha256",
    "min_calcifer",
    "contract",
    "maintainer",
    "tier",
    "tags",
    "homepage",
}
CACHE_DIRS = ("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache")


# ---- tree hash (same algorithm as calcifer.app.external_packs.tree_hash)


def _vendored_tree_hash(path: Path) -> str:
    digests: dict[str, str] = {}
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = file.relative_to(path)
        if ".git" in rel.parts or any(part in CACHE_DIRS for part in rel.parts) or rel.suffix == ".pyc":
            continue
        digests[rel.as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    h = hashlib.sha256()
    for rel, digest in digests.items():
        if rel == "pack.yaml":
            continue
        h.update(rel.encode())
        h.update(digest.encode())
    meta = yaml.safe_load((path / "pack.yaml").read_text(encoding="utf-8")) or {}
    meta.pop("source", None)
    h.update(yaml.safe_dump(meta, sort_keys=True).encode())
    return h.hexdigest()


def tree_hash(path: Path) -> tuple[str, str]:
    """(hash, which implementation computed it)."""
    try:
        from calcifer.app.external_packs import tree_hash as canonical
    except ImportError:
        return _vendored_tree_hash(path), "vendored"
    return canonical(path), "calcifer"


# ---- schema


def _check_entry(index: int, e: Any) -> list[str]:
    who = f"entry #{index + 1}" + (f" ({e.get('name')})" if isinstance(e, dict) and e.get("name") else "")
    if not isinstance(e, dict):
        return [f"{who}: must be a mapping"]
    problems: list[str] = []
    if missing := sorted(FIELDS - e.keys()):
        problems.append(f"{who}: missing {', '.join(missing)}")
    if extra := sorted(set(e) - FIELDS):
        problems.append(f"{who}: unknown fields {', '.join(extra)}")

    def need(field: str, ok: bool, why: str) -> None:
        if field in e and not ok:
            problems.append(f"{who}: {field} {why}")

    def text(field: str, limit: int) -> bool:
        v = e.get(field)
        return isinstance(v, str) and 0 < len(v) <= limit

    def match(field: str, pattern: re.Pattern[str]) -> bool:
        v = e.get(field)
        return isinstance(v, str) and bool(pattern.fullmatch(v))

    need("name", match("name", NAME_RE), "must match [a-z][a-z0-9_-]{1,30}")
    need("description", text("description", 300), "must be a string of 1-300 characters")
    need("url", match("url", GIT_URL_RE), "must be an https:// or ssh:// git URL")
    path = e.get("path")
    need(
        "path",
        path is None or (match("path", SUBDIR_RE) and ".." not in str(path).split("/")),
        "must be null or a relative folder without ..",
    )
    need("commit", match("commit", COMMIT_RE), "must be a full 40-character lowercase sha")
    need("sha256", match("sha256", SHA_RE), "must be 64 lowercase hex characters")
    need("min_calcifer", e.get("min_calcifer") is None or match("min_calcifer", VERSION_RE), "must be null or X.Y.Z")
    contract = e.get("contract")
    need("contract", isinstance(contract, int) and not isinstance(contract, bool) and contract >= 1, "must be an integer >= 1")
    need("maintainer", text("maintainer", 80), "must be a string of 1-80 characters")
    need("tier", e.get("tier") in ("official", "community"), "must be official or community")
    tags = e.get("tags")
    need(
        "tags",
        isinstance(tags, list) and len(tags) <= 12 and all(isinstance(t, str) and TAG_RE.fullmatch(t) for t in tags),
        "must be a list of at most 12 lowercase words",
    )
    home = e.get("homepage")
    need("homepage", home is None or (isinstance(home, str) and home.startswith("https://") and len(home) <= 300), "must be null or an https:// URL")
    if e.get("tier") == "official" and not (isinstance(path, str) and path.startswith("packs/")):
        problems.append(f"{who}: official packs live under packs/")
    return problems


def schema_problems(entries: Any) -> list[str]:
    if not isinstance(entries, list):
        return ["`packs:` must be a list"]
    problems: list[str] = []
    names = [e["name"] for e in entries if isinstance(e, dict) and isinstance(e.get("name"), str)]
    if names != sorted(names):
        problems.append("entries must be sorted by name")
    if len(set(names)) != len(names):
        problems.append("duplicate names: " + ", ".join(sorted({n for n in names if names.count(n) > 1})))
    for i, e in enumerate(entries):
        problems += _check_entry(i, e)
    return problems


# ---- repository checks


def _norm(url: str) -> str:
    return re.sub(r"(\.git)?/?$", "", url.strip().lower())


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=300, check=False)


def entry_problems(entry: dict[str, Any], self_urls: list[str], root: Path) -> list[str]:
    who = entry["name"]
    source = str(root) if _norm(entry["url"]) in {_norm(u) for u in self_urls} else entry["url"]
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "repo"
        cloned = _git("clone", "--quiet", "--no-checkout", "--", source, str(target))
        if cloned.returncode:
            return [f"{who}: cannot clone {entry['url']}: {cloned.stderr.strip()[-160:]}"]
        checked = _git("checkout", "--quiet", "--detach", entry["commit"], "--", cwd=target)
        if checked.returncode:
            return [f"{who}: commit {entry['commit']} does not exist in {entry['url']}"]
        folder = target / entry["path"] if entry["path"] else target
        if not folder.is_dir() or not (folder / "pack.yaml").is_file():
            return [f"{who}: no pack.yaml at path {entry['path'] or '.'} in commit {entry['commit'][:12]}"]
        if folder.is_symlink() or any(p.is_symlink() for p in folder.rglob("*")):
            return [f"{who}: the pack folder contains symlinks"]
        shutil.rmtree(target / ".git", ignore_errors=True)
        problems: list[str] = []
        meta = yaml.safe_load((folder / "pack.yaml").read_text(encoding="utf-8")) or {}
        if meta.get("name") != entry["name"]:
            problems.append(f"{who}: pack.yaml names the pack {meta.get('name')!r}")
        if (meta.get("min_calcifer") or None) != entry["min_calcifer"]:
            problems.append(f"{who}: min_calcifer differs from pack.yaml ({meta.get('min_calcifer')!r})")
        if int(meta.get("contract", 1)) != entry["contract"]:
            problems.append(f"{who}: contract differs from pack.yaml ({meta.get('contract', 1)!r})")
        actual, impl = tree_hash(folder)
        if actual != entry["sha256"]:
            problems.append(
                f"{who}: sha256 is {entry['sha256'][:16]}... but the pack at that commit hashes to {actual} ({impl})"
            )
        return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", default="index.yaml")
    ap.add_argument("--self-url", action="append", default=[], help="URL that means 'this repository'")
    ap.add_argument("--offline", action="store_true", help="schema only: no clones, no hashes")
    args = ap.parse_args()
    index = Path(args.index)
    try:
        raw = yaml.safe_load(index.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as err:
        print(f"FAIL: cannot read {index}: {err}")
        return 1
    entries = raw.get("packs") if isinstance(raw, dict) else None
    problems = schema_problems(entries)
    if not problems and not args.offline:
        root = index.resolve().parent
        for entry in entries or []:
            problems += entry_problems(entry, args.self_url, root)
    for p in problems:
        print(f"FAIL: {p}")
    if problems:
        return 1
    count = len(entries or [])
    print(f"OK: {count} entr{'y' if count == 1 else 'ies'} valid" + (" (schema only)" if args.offline else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
