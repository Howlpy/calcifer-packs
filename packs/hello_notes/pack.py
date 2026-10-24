"""hello_notes: the catalog's example pack. Owner-only tools over one table of its own (`ext_hello_notes_notes`).

It imports only `calcifer.core.contracts` and `calcifer.core.shared`, declares everything in `pack.yaml` (tools, the
table migration) and never touches the network, files or other packs' tables.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from calcifer.core.contracts import (
    PackManifest,
    PackRegistration,
    PackRequires,
    PackServices,
    PackTrust,
    Risk,
    ToolContext,
    ToolResult,
    define_tool,
)


class Config(BaseModel):
    """What the owner can put in packs.yaml under this pack's `config:`."""

    max_notes: int = Field(500, alias="maxNotes", ge=1, le=5000)

    model_config = {"populate_by_name": True}


class AddArgs(BaseModel):
    text: str = Field(min_length=1, max_length=500, description="The note, one or two sentences")


class ListArgs(BaseModel):
    limit: int = Field(10, ge=1, le=50, description="How many of the latest notes to return")


def register(config: Config, services: PackServices) -> PackRegistration:
    db, clock = services.db, services.clock

    async def add(args: AddArgs, ctx: ToolContext) -> ToolResult:
        row = db.fetch_one("SELECT COUNT(*) AS n FROM ext_hello_notes_notes")
        if row and int(row["n"]) >= config.max_notes:
            return ToolResult("the notebook is full; ask the owner to clear some notes", is_error=True)
        db.execute(
            "INSERT INTO ext_hello_notes_notes (at, text) VALUES (?, ?)",
            (clock.iso(), args.text.strip()),
        )
        return ToolResult({"saved": True})

    async def latest(args: ListArgs, ctx: ToolContext) -> ToolResult:
        rows = db.fetch_all(
            "SELECT id, at, text FROM ext_hello_notes_notes ORDER BY id DESC LIMIT ?", (args.limit,)
        )
        return ToolResult({"notes": [{"id": r["id"], "at": r["at"], "text": r["text"]} for r in rows]})

    return PackRegistration(
        tools=[
            define_tool(
                name="hello_notes.add",
                description="Saves a short note in the owner's notebook. Use it only when the owner asks to note something down.",
                input=AddArgs,
                risk=Risk.WRITE,
                handler=add,
            ),
            define_tool(
                name="hello_notes.list",
                description="Lists the latest notes from the owner's notebook. Use it when the owner asks what they noted; it cannot search by topic.",
                input=ListArgs,
                risk=Risk.READ,
                idempotent=True,
                handler=latest,
            ),
        ]
    )


pack = PackManifest(
    name="hello_notes",
    version="0.1.0",
    description="A tiny notebook for the owner",
    trust=PackTrust.EXTERNAL,
    requires=PackRequires(core=1),
    config_model=Config,
    register=register,
)
