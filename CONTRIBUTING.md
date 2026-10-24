# Contributing a pack

There are two ways in. Both end with a pull request that touches `index.yaml`.

| | Official | Community |
| --- | --- | --- |
| Where the code lives | `packs/<name>/` in this repository | your own repository |
| Who maintains it | the Calcifer project | you |
| `tier` | `official` (set by maintainers only) | `community` |
| CI runs the pack's tests | yes | no (we never run third-party code in CI) |
| What users see on install | the normal summary and confirmation | the same, plus a warning that the project has not reviewed the code, and an extra explicit yes |

Official packs are rare on purpose: they are examples and things the project is willing to maintain. Most packs should be
community packs.

## Before you start

Read `docs/15-creating-a-pack.md` in the Calcifer repository. In short: `calcifer pack new <name>` scaffolds a pack,
`calcifer pack check . --run` validates it and runs its tests.

## Submitting a community pack

1. Publish your pack in a public git repository. The folder with `pack.yaml` can be the repository root or a subfolder.
2. Tag nothing, pin everything: copy the **full 40-character commit sha** you want listed (`git rev-parse HEAD`).
3. At that commit, run `calcifer pack hash <pack folder>` and copy the 64-character result.
4. Add an entry to `index.yaml`, **in alphabetical order by name** (see the schema at the top of that file):

   ```yaml
   - name: my_pack
     description: One sentence: what it does and what it does not.
     url: https://github.com/you/my-pack.git
     path: null
     commit: 0123456789abcdef0123456789abcdef01234567
     sha256: <calcifer pack hash output>
     min_calcifer: 0.1.0
     contract: 1
     maintainer: you
     tier: community
     tags: [notes]
     homepage: https://github.com/you/my-pack
   ```

5. Open a pull request that changes only `index.yaml`. CI checks the schema, that the commit and path exist, that
   `pack.yaml`'s name, `min_calcifer` and `contract` agree with the entry, and that the hash matches.
6. To publish a new version later: new commit, new hash, a pull request that changes `commit` and `sha256` (and
   `min_calcifer` if it changed). People who installed the pack by name get the permission and code diff on
   `calcifer pack update`.

Names are first come, first served, must match `pack.yaml`, and cannot clash with a pack that ships with Calcifer. Do
not impersonate another project or maintainer.

## Submitting an official pack

Add `packs/<name>/` (with tests), commit it, then in a **second commit** add the `index.yaml` entry with `url` set to this
repository, `path: packs/<name>`, the first commit's sha, `tier: official`. The two-step flow exists because an entry
pins a commit and a commit cannot contain its own hash. A maintainer must approve; official entries are never added by
outside contributors' PRs without a maintainer's review of the code.

## Review checklist (what maintainers look at)

Reviewers read the entry and, for official packs, the code. For community packs they look at the entry and skim the
pack for obvious problems; **a merge is not an audit.**

1. **Identity.** The repository is public, the maintainer is a real account, the name does not mimic another project.
2. **Pin.** Full sha, hash computed with `calcifer pack hash`, `pack.yaml` agrees with the entry.
3. **Honest declaration.** `pack.yaml` lists every tool with the right risk (`write` for anything that changes state or
   leaves the machine), every secret, program (`bins`) and host (`network`) the code uses. Undeclared network or
   file access is a rejection.
4. **Minimal permissions.** Owner-only tools unless guests really need them. No secret it does not need. Hosts as narrow
   as possible.
5. **Tool descriptions.** One to three sentences, say when **not** to use the tool, contain no instructions to the model
   about unrelated behavior, and say nothing misleading about what the tool does.
6. **Code.** Imports only `calcifer.core.contracts` and `calcifer.core.shared` (Calcifer enforces this), no `eval`/`exec`,
   no downloading and running code, no obfuscation, no compiled binaries, no reading other packs' data or the workspace
   `.env`, no persistence outside its own `ext_<pack>_*` tables.
7. **Data.** What it stores, where, and for how long is stated in its README. Whatever a tool returns is data, not
   instructions: it must not pass untrusted text back as if it were a command.
8. **Maintenance.** There is a way to report problems, and a license.

## Security expectations for authors

- Keep your repository and account secure (2FA). Whoever controls them controls what your users run when they update.
- Never force-push over a listed commit; the catalog pins it and a missing commit makes installs fail.
- Releases are new commits plus a new catalog entry, not moved tags.
- Report vulnerabilities in your pack promptly: maintainers can remove or yank an entry at any time, and will if a pack is
  found to be malicious, abandoned with a known vulnerability, or to misrepresent what it does.

## What the catalog does not do

It does not sandbox anything and does not sign packs: the hash proves the content matches the listing, nothing more.
Python packs run inside Calcifer. Users are told to read a pack before installing it, and so should reviewers.
