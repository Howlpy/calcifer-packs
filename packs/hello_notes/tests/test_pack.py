"""Loads the pack the way Calcifer does (its limits, its scoped database) and calls both tools."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Any

from calcifer.app.external_packs import ExternalPack, load_manifest, read_meta
from calcifer.core.contracts import EndpointTrust, PackServices, Principal, Role, ToolContext
from calcifer.core.shared import CancelToken

ROOT = Path(__file__).resolve().parents[1]


class SqliteDb:
    """Just enough of the core's database handle for the pack's three calls."""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    def execute(self, sql: str, params: Any = ()) -> int:
        return self.conn.execute(sql, params).rowcount

    def fetch_one(self, sql: str, params: Any = ()) -> dict[str, Any] | None:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def fetch_all(self, sql: str, params: Any = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]


class Clock:
    def __init__(self) -> None:
        self.n = 0

    def iso(self) -> str:
        self.n += 1
        return f"2026-01-01T00:00:{self.n:02d}Z"


def tools(config: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = read_meta(ROOT)
    inner = SqliteDb()
    for migration in meta.migrations:
        inner.execute(migration.sql)
    manifest = load_manifest(ExternalPack(meta, ROOT))
    # the loader wraps `db` in the pack's scoped handle (only `ext_hello_notes_*` tables, one statement at a time)
    services = PackServices(
        log=logging.getLogger("t"),
        events=None,  # type: ignore[arg-type]
        clock=Clock(),  # type: ignore[arg-type]
        workspace_dir=ROOT,
        data_dir=ROOT,
        db=inner,  # type: ignore[arg-type]
    )
    reg = asyncio.run(manifest.register(manifest.config_model.model_validate(config or {}), services))
    return {t.name: t for t in reg.tools}


def call(tool: Any, args: dict[str, Any]) -> Any:
    ctx = ToolContext(
        "run",
        "c1",
        None,
        Principal("owner", Role.OWNER, EndpointTrust.OWNER_VERIFIED),
        "owner_message",
        CancelToken(),
        logging.getLogger("t"),
    )
    return asyncio.run(tool.handler(tool.parse(args), ctx))


def test_it_declares_exactly_two_owner_only_tools() -> None:
    declared = {t.name: t.risk for t in read_meta(ROOT).tools}
    assert declared == {"hello_notes.add": "write", "hello_notes.list": "read"}
    assert set(tools()) == set(declared)


def test_notes_are_saved_and_listed_newest_first() -> None:
    t = tools()
    assert call(t["hello_notes.add"], {"text": "  buy milk "}).content == {"saved": True}
    call(t["hello_notes.add"], {"text": "call Ana"})
    notes = call(t["hello_notes.list"], {"limit": 5}).content["notes"]
    assert [n["text"] for n in notes] == ["call Ana", "buy milk"]


def test_the_notebook_has_a_limit() -> None:
    t = tools({"maxNotes": 1})
    call(t["hello_notes.add"], {"text": "one"})
    full = call(t["hello_notes.add"], {"text": "two"})
    assert full.is_error and "full" in str(full.content)
