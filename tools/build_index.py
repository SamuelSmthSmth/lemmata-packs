#!/usr/bin/env python
"""Check every pack in packs/ and build the registry site.

    python tools/build_index.py --engine .engine [--out site] [--budget 30] [--jobs N]

``--engine`` is a directory holding the engine as the app publishes it
(``https://lemmata.sous.systems/app/static/engine/engine.zip``, unzipped, with
``version.json`` beside it), so packs are checked by exactly the engine
students use.  For each ``packs/<scope>/<slug>.pack.json``:

1. the file must be a valid pack (``aether.packs.validate_pack``), and its
   ``name`` must match its path;
2. every entry is checked again, each in its own process under a wall-clock
   budget, and must give the verdict it records as ``expected``.

Any failure fails the build, so nothing reaches the index unverified.  The
site written to ``--out`` holds ``index.json``, a copy of every pack file at
the path the index names, and a small ``index.html`` for people.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import multiprocessing as mp
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "packs"
INDEX_FORMAT = 1


def verdict(engine: str, source: str, conn) -> None:
    """Child process: the verdict the app would show for *source* (lenient domains)."""
    sys.path.insert(0, engine)
    from aether import ParseError, ProofChecker

    try:
        reports = ProofChecker().check_source(source)
    except ParseError:
        conn.send("PARSE ERROR")
        return
    except Exception as exc:  # noqa: BLE001 - an engine crash is a failure to report
        conn.send(f"CRASH {type(exc).__name__}: {exc}"[:200])
        return
    if any(not r.is_valid for r in reports):
        conn.send("INVALID")
    elif any(r.has_warnings for r in reports):
        conn.send("WARN")
    else:
        conn.send("VALID")


def check_entries(engine: str, jobs: list[tuple[str, str, str]], budget: float, workers: int) -> dict[str, str]:
    """Run (key, source, expected) jobs, *workers* at a time; return key -> verdict."""
    ctx = mp.get_context("spawn")
    results: dict[str, str] = {}
    pending = list(jobs)
    running: list[tuple[str, mp.Process, object, float]] = []
    while pending or running:
        while pending and len(running) < workers:
            key, source, _ = pending.pop(0)
            parent, child = ctx.Pipe(duplex=False)
            proc = ctx.Process(target=verdict, args=(engine, source, child), daemon=True)
            proc.start()
            child.close()
            running.append((key, proc, parent, time.monotonic()))
        still = []
        for key, proc, parent, started in running:
            if parent.poll():
                results[key] = parent.recv()
                proc.join()
            elif not proc.is_alive():
                results[key] = f"CRASH exit {proc.exitcode}"
            elif time.monotonic() - started > budget:
                proc.terminate()
                proc.join()
                results[key] = f"TIMEOUT after {budget:g} s"
            else:
                still.append((key, proc, parent, started))
        running = still
        time.sleep(0.02)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", required=True, help="directory with the unzipped engine (aether/, ui/) and version.json")
    parser.add_argument("--out", default=str(ROOT / "site"))
    parser.add_argument("--budget", type=float, default=30.0, help="seconds per entry")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    args = parser.parse_args()

    engine = str(Path(args.engine).resolve())
    sys.path.insert(0, engine)
    from aether.packs import validate_pack

    version_file = Path(engine) / "version.json"
    engine_version = json.loads(version_file.read_text())["engine"] if version_file.exists() else "unknown"

    problems: list[str] = []
    packs: list[tuple[Path, dict, bytes]] = []
    for path in sorted(PACKS.rglob("*.pack.json")):
        rel = path.relative_to(PACKS).as_posix()
        raw = path.read_bytes()
        try:
            data = json.loads(raw)
        except ValueError as err:
            problems.append(f"{rel}: not JSON ({err})")
            continue
        pack, errors = validate_pack(data)
        if pack is None:
            problems.extend(f"{rel}: {e}" for e in errors)
            continue
        if f"{pack['name']}.pack.json" != rel:
            problems.append(f"{rel}: its name is {pack['name']!r}, so it belongs at packs/{pack['name']}.pack.json")
            continue
        packs.append((path, pack, raw))

    jobs = [
        (f"{pack['name']}/{entry['id']}", entry["source"], entry["expected"])
        for _, pack, _ in packs
        for entry in pack["entries"]
    ]
    print(f"checking {len(jobs)} entries in {len(packs)} packs with engine {engine_version} ({args.jobs} at a time)")
    started = time.monotonic()
    got = check_entries(engine, jobs, args.budget, args.jobs)
    for key, _, expected in jobs:
        if got.get(key) != expected:
            problems.append(f"{key}: records {expected}, the engine gives {got.get(key)}")
    print(f"checked in {time.monotonic() - started:.0f} s")

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for line in problems:
            print(f"  - {line}")
        return 1

    out = Path(args.out)
    index = []
    for path, pack, raw in packs:
        url = f"packs/{pack['name']}.pack.json"
        target = out / url
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        chapters = {c["id"]: c["title"] for c in pack["chapters"]}
        index.append(
            {
                "name": pack["name"],
                "version": pack["version"],
                "title": pack["title"],
                "courses": pack["courses"],
                "summary": pack["summary"],
                "authors": pack["authors"],
                "license": pack["license"],
                "entries": len(pack["entries"]),
                "traps": sum(e["kind"] == "trap" for e in pack["entries"]),
                "chapters": [c["title"] for c in pack["chapters"]],
                "search": " ".join(f"{e['ref']} {e['title']} {chapters.get(e['chapter'], '')}" for e in pack["entries"]),
                "url": url,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    # Where to contribute: the app links its "Share to the registry" steps here.
    repository = os.environ.get("GITHUB_REPOSITORY", "SamuelSmthSmth/lemmata-packs")
    document = {
        "format": INDEX_FORMAT,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine": engine_version,
        "contribute": f"https://github.com/{repository}",
        "packs": index,
    }
    (out / "index.json").write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n")
    rows = "\n".join(
        f"<li><a href=\"{html.escape(p['url'])}\"><code>{html.escape(p['name'])}</code></a> "
        f"v{html.escape(p['version'])} — {html.escape(p['title'])} ({p['entries']} entries)</li>"
        for p in index
    )
    (out / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Lemmata packs</title><body style='font:14px/1.5 system-ui;max-width:42rem;margin:2rem auto;padding:0 16px'>"
        "<h1>Lemmata packs</h1><p>The public pack registry for "
        "<a href='https://lemmata.sous.systems/'>Lemmata</a>. Every entry below was checked by engine "
        f"{html.escape(engine_version)} on {document['generated']}. The app reads <a href='index.json'>index.json</a>.</p>"
        f"<ul>{rows}</ul></body>\n"
    )
    print(f"wrote {out}/index.json: {len(index)} packs, every entry verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
