# hello_notes

The catalog's example pack: a tiny notebook for the owner.

- `hello_notes.add` (write, asks every time) saves a short note.
- `hello_notes.list` (read) returns the latest notes.

It stores them in its own table (`ext_hello_notes_notes`, created by the migration declared in `pack.yaml`). It needs no
secrets, programs or network. Owner only: nobody else can call its tools.

```
calcifer pack install hello_notes     # from the calcifer-packs catalog
calcifer pack check . --run           # in this folder: validate and run the tests
```

Config (`packs.yaml`, optional): `maxNotes` (default 500).
