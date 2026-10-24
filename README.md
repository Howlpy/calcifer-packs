# calcifer-packs

The pack catalog for [Calcifer](https://github.com/Howlpy/calcifer): an `index.yaml` of third-party packs that
`calcifer pack search` and `calcifer pack install <name>` read, plus the packs the Calcifer project maintains itself.

```bash
calcifer pack search notes          # name, description, tags; tier, maintainer, compatible with your version
calcifer pack info hello_notes      # source, exact commit, hash
calcifer pack install hello_notes   # clones that commit, checks its hash against the catalog, shows what it asks for
calcifer pack update hello_notes    # follows the catalog's new commit and shows the permission and code diff
```

## How it works

- `index.yaml` lists packs. Each entry pins a repository, a folder, a **full commit sha** and the **tree hash** of the
  pack at that commit. Calcifer downloads exactly that commit and refuses anything whose hash differs.
- `packs/<name>/` holds the **official** packs, maintained and reviewed by the project (`tier: official`).
- **Community** packs stay in their authors' repositories and are added by a pull request that changes `index.yaml`
  (`tier: community`). Maintainers review the entry; they do **not** audit the pack's code. Calcifer says so, loudly,
  every time someone installs one.
- Calcifer reads this catalog from `https://raw.githubusercontent.com/Howlpy/calcifer-packs/main/index.yaml` by default
  (`catalogs:` in the workspace's `packs.yaml` changes it), caches it for a day and works offline from the cache.

## What a hash does and does not tell you

It proves that what you download is what the maintainer listed. It does **not** prove the code is safe: Python packs run
inside Calcifer with its files, environment and network. Read a pack before you install it, whatever its tier. See
[CONTRIBUTING.md](CONTRIBUTING.md) for what reviewers check.

## Repository layout

| Path | What |
| --- | --- |
| `index.yaml` | the catalog (schema documented at the top) |
| `packs/` | official packs, one folder each (`pack.yaml`, `pack.py`, `tests/`, `README.md`) |
| `scripts/validate_index.py` | schema, commit/path and tree-hash validation used by CI |
| `.github/workflows/validate.yml` | CI: validates the index and checks every official pack |

## Validate locally

```bash
pip install pyyaml
python scripts/validate_index.py --offline          # schema only
python scripts/validate_index.py                    # also clones every entry and checks commit, path and hash
calcifer pack check packs/hello_notes --run         # an official pack: manifest, imports, load and its tests
```

## License

MIT, see [LICENSE](LICENSE). Each community pack has its own license in its own repository.
