# Lemmata packs

The public pack registry for [Lemmata](https://lemmata.sous.systems), a checker for undergraduate proofs written the way lecture notes write them.

A **pack** is a set of proofs keyed to a module's (or a topic's) own numbering: theorems, worked examples, and *traps*, which are deliberate mistakes to find. Every entry records the verdict it must give, and nothing is published until the checker confirms it.

In the app, **Library → search** finds packs here by course code, title or theorem, and **Install** adds one to your browser. Updates published here reach everyone who installed the pack.

## How it works

```
packs/<scope>/<slug>.pack.json    one file per pack (pack format 1)
tools/build_index.py              validates every pack and re-checks every entry
```

- On every pull request, CI downloads the engine the app is running today and checks each pack. Each entry runs in its own process under a time budget, and its verdict must match `expected`.
- On `main`, the same checks run, then `index.json` and the pack files are published to GitHub Pages at <https://samuelsmthsmth.github.io/lemmata-packs/>. The app reads them from there.
- A weekly run re-checks everything against the newest engine, so `index.json` always says which engine last verified it.

No server and no accounts: the repository is the registry, review is moderation, and CI is the check that a proof really holds.

## Adding a pack

See [CONTRIBUTING.md](CONTRIBUTING.md). In short:
1. Make the pack in the app: Library → **New pack…**, or a folder's pack button.
2. **Export .pack.json**.
3. Open a pull request adding it at `packs/<scope>/<slug>.pack.json`.

## Licence

Packs are licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) unless a pack's `license` field says otherwise. The tooling in `tools/` is Apache-2.0. Packs must be your own transcriptions: restate results and write your own proofs, and do not paste lecture notes.

## The site

`tools/build_index.py` also writes the site people read (via `tools/pages.py` and `web/`): a catalogue with search, a page per pack listing every entry by chapter with its source, and a publishing guide. Each pack page's **Open in Lemmata** opens the app's Library on that pack (`/app/?install=<name>`).
