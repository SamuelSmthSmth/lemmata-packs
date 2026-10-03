# Contributing a pack

## 1. Make it in the app

1. Open [Lemmata](https://lemmata.sous.systems) and put your proofs in one folder (**Files** tab).
2. Click the folder's pack button (or Library → **New pack…**) and fill in the pack's details:
   - **Name:** `scope/slug`, lower case, e.g. `yourname/real-analysis`. The scope is yours: your name, a society, a department. `core/` is reserved for the packs that ship with the app.
   - **Version:** semver, starting at `1.0.0`. Raise it whenever you change the pack, so installed copies are offered the update.
   - **Course codes** are optional; a pack can be a topic.
   - For each proof, give a **reference** (the notes' own numbering, e.g. `Example 2.18`), a title and a chapter. Mark deliberate mistakes as **Trap** and say what is wrong.
3. **Export .pack.json.** The app checks every proof and records the verdict it gives, so the file is true when you export it.

`templates/example.pack.json` shows the format if you would rather write one by hand. The format is defined by `aether.packs` in the app, with a JSON Schema copy (`pack.schema.json`) in the app's `courses/`.

## 2. Open a pull request

1. Add the file at `packs/<scope>/<slug>.pack.json`, matching its `name`.
2. GitHub's **Add file → Upload files** works; no local checkout is needed.
3. CI checks the pack: it must be valid, and every entry must still give its recorded verdict under the engine the app runs today. Fix whatever it reports and push again.

## What gets merged

- Your own wording: restate results in your words and write your own proofs. Never paste lecture notes or textbook passages.
- Entries that check. A *trap* must fail, with an explanation of the mistake.
- References that follow the source's own numbering, so students can find their way back to their notes.

Everything here is licensed CC BY-SA 4.0 unless the pack says otherwise.
