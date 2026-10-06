"""The registry's human-readable site: the catalogue, a page per pack, the guide.

build_index.py calls build() once every pack has been checked, so the site
only ever shows verified packs.  The pages are plain HTML from web/ with
``{{ placeholders }}`` filled here; web/assets/ is copied as it is.  The site
looks and works like the app's own Library: a rail of packs by course beside
the open pack, whose entries hang off the notes' own numbering.

Nothing here needs a network or a dependency beyond the standard library.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")

# Where "Open in Lemmata" goes: the app's install link (LEMMATA_APP for a
# department's own copy of the app).
APP = os.environ.get("LEMMATA_APP", "https://lemmata.sous.systems/app/")
SITE = "https://lemmata.sous.systems/"


def fill(text: str, values: dict[str, str], where: str) -> str:
    def one(match: re.Match) -> str:
        if match.group(1) not in values:
            raise KeyError(f"{where}: no value for {{{{ {match.group(1)} }}}}")
        return values[match.group(1)]

    out = PLACEHOLDER.sub(one, text)
    if "{{" in out:
        raise ValueError(f"{where}: a placeholder was left unfilled")
    return out


def slug_path(name: str) -> str:
    """packs/<scope>/<slug>/: a pack's page, beside its .pack.json file."""
    return f"packs/{name}/"


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def nice_date(iso: str) -> str:
    when = datetime.fromisoformat(iso)
    return f"{when.day} {when:%B %Y}"


def license_label(spdx: str) -> str:
    return {"CC-BY-SA-4.0": "CC BY-SA 4.0", "CC-BY-4.0": "CC BY 4.0", "CC0-1.0": "CC0"}.get(spdx, spdx)


def counts(pack: dict) -> str:
    entries = len(pack["entries"])
    traps = sum(e["kind"] == "trap" for e in pack["entries"])
    return plural(entries, "entry").replace("entrys", "entries") + (f" · {plural(traps, 'trap')}" if traps else "")


def groups(packs: list[dict]) -> list[tuple[str, list[dict]]]:
    """Packs by their first course code, then the topic packs (no course)."""
    by_course: dict[str, list[dict]] = {}
    topics: list[dict] = []
    for pack in sorted(packs, key=lambda p: (p["courses"][:1], p["title"])):
        if pack["courses"]:
            by_course.setdefault(pack["courses"][0], []).append(pack)
        else:
            topics.append(pack)
    out = sorted(by_course.items())
    if topics:
        out.append(("Topics", topics))
    return out


def rail(packs: list[dict], current: str | None, root: str) -> str:
    parts = []
    for label, members in groups(packs):
        items = []
        for pack in members:
            here = ' aria-current="page"' if pack["name"] == current else ""
            items.append(
                f'<li><a class="rail-pack" href="{root}{slug_path(pack["name"])}"{here} data-pack="{escape(pack["name"])}"'
                f' data-search="{escape(search_text(pack))}">'
                f'<span class="rail-title">{escape(pack["title"])}</span>'
                f'<span class="rail-meta">{escape(counts(pack))}</span></a></li>'
            )
        parts.append(f'<li class="rail-group"><h2 class="rail-label">{escape(label)}</h2><ul>{"".join(items)}</ul></li>')
    return "\n".join(parts)


def search_text(pack: dict) -> str:
    chapters = " ".join(c["title"] for c in pack["chapters"])
    return " ".join([pack["name"], pack["title"], " ".join(pack["courses"]), pack.get("summary", ""), " ".join(pack["authors"]), chapters]).lower()


def verified_line(pack: dict, engine: str, generated: str) -> str:
    return (
        f'<p class="verified"><span class="verified-word">Verified</span> every entry gives its recorded verdict'
        f" under engine {escape(engine)}, checked {escape(nice_date(generated))}.</p>"
    )


def pack_head(pack: dict, engine: str, generated: str, *, level: str = "h1", link: str | None = None) -> str:
    code = "".join(f'<span class="pack-code">{escape(c)}</span>' for c in pack["courses"][:1])
    title = escape(pack["title"])
    heading = f'<a href="{link}">{title}</a>' if link else title
    meta = [f"v{escape(pack['version'])}", escape(", ".join(pack["authors"])), license_label(escape(pack["license"])), f"<code>{escape(pack['name'])}</code>"]
    return (
        f'<{level} class="pack-title">{code}{heading}</{level}>'
        f'<p class="pack-meta">{" ".join(f"<span>{m}</span>" for m in meta if m)}</p>'
        f'<p class="pack-summary">{escape(pack.get("summary", ""))}</p>'
    )


def actions(pack: dict, root: str) -> str:
    return (
        '<div class="actions">'
        f'<a class="button button--primary" href="{escape(APP)}?install={escape(pack["name"])}">Open in Lemmata</a>'
        f'<a class="button button--outline" href="{root}packs/{escape(pack["name"])}.pack.json" download>Download .pack.json</a>'
        "</div>"
    )


# The app's "mono" scheme: the keywords that form a proof's skeleton take
# Proof Blue, everything else is ink (DESIGN.md, The Two Schemes Rule).
KEYWORDS = re.compile(
    r"\b(Theorem|Lemma|Claim|Proof|QED|Let|Given|Assume|Obtain|Step|Therefore|Hence|Subproof|Case|"
    r"Define|import|exists|forall|Base case|Inductive step)\b|[∀∃]"
)
GLUE = re.compile(r"\b(such that|from|where|by)\b")


def source_html(source: str) -> str:
    """A proof's source as the app sets it: numbered lines, keywords in Proof Blue."""
    lines = []
    for line in source.rstrip().split("\n"):
        text = escape(line)
        text = GLUE.sub(lambda m: f'<span class="glue">{m.group(0)}</span>', text)
        text = KEYWORDS.sub(lambda m: f'<span class="kw">{m.group(0)}</span>', text)
        lines.append(f'<span class="src-line">{text or " "}</span>')
    return "".join(lines)


def entry_html(pack: dict, entry: dict) -> str:
    trap = entry["kind"] == "trap"
    verdict = "trap · fails, as it should" if trap else ("checks" if entry["expected"] == "VALID" else entry["expected"].lower())
    level = entry.get("level") or pack.get("level") or "off"
    if level != "off":
        verdict += f" · at {level.capitalize()}"
    explanation = f'<p class="entry-why">{escape(entry["explanation"])}</p>' if entry.get("explanation") else ""
    chevron = '<svg class="chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    return (
        f'<li class="entry{" is-trap" if trap else ""}" id="{escape(entry["id"])}" data-search="{escape((entry["ref"] + " " + entry["title"]).lower())}">'
        f'<a class="entry-key" href="#{escape(entry["id"])}">{escape(entry["ref"])}</a>'
        '<div class="entry-body">'
        f'<details class="entry-source"><summary>{chevron}<span class="entry-title">{escape(entry["title"])}</span>'
        f'<span class="entry-verdict">{escape(verdict)}</span></summary>'
        f'<pre tabindex="0" aria-label="Source of {escape(entry["ref"])}"><code>{source_html(entry["source"])}</code></pre></details>'
        f"{explanation}"
        "</div></li>"
    )


def chapters_html(pack: dict) -> str:
    out = []
    for chapter in pack["chapters"]:
        entries = [e for e in pack["entries"] if e["chapter"] == chapter["id"]]
        if not entries:
            continue
        out.append(
            f'<section class="chapter" aria-labelledby="ch-{escape(chapter["id"])}">'
            f'<h2 class="chapter-title" id="ch-{escape(chapter["id"])}"><span class="chapter-number">{escape(chapter["id"])}</span> {escape(chapter["title"])}'
            f'<span class="chapter-count">{plural(len(entries), "entry").replace("entrys", "entries")}</span></h2>'
            f'<ol class="entries">{"".join(entry_html(pack, e) for e in entries)}</ol></section>'
        )
    return "\n".join(out)


def build(out: Path, packs: list[dict], index: dict) -> list[str]:
    """Write the site's pages into *out* (beside index.json); return their paths."""
    shell = (WEB / "shell.html").read_text(encoding="utf-8")
    engine, generated = index["engine"], index["generated"]
    total_entries = sum(len(p["entries"]) for p in packs)
    total_traps = sum(e["kind"] == "trap" for p in packs for e in p["entries"])
    written = []

    def page(path: str, title: str, description: str, main: str, current: str | None = None) -> None:
        depth = len(path.split("/")) if path else 0
        root = "../" * depth or "./"
        values = {
            "title": escape(title),
            "description": escape(description),
            "root": root,
            "rail": rail(packs, current, root),
            "main": main,
            "app": escape(APP),
            "site": SITE,
            "contribute": escape(index["contribute"]),
            "engine": escape(engine),
            "year": generated[:4],
        }
        target = out / path / "index.html" if path else out / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fill(shell, values, path or "index"), encoding="utf-8")
        written.append(target.relative_to(out).as_posix())

    # The front page: the registry in one line, theorem matches, every pack in brief.
    briefs = "\n".join(
        f'<li class="brief" data-pack="{escape(pack["name"])}" data-search="{escape(search_text(pack))}">{pack_head(pack, engine, generated, level="h3", link="./" + slug_path(pack["name"]))}'
        f'<p class="brief-counts">{escape(counts(pack))} · {plural(len(pack["chapters"]), "chapter")}</p></li>'
        for _, members in groups(packs)
        for pack in members
    )
    front = (
        '<header class="page-head"><h1>Packs</h1>'
        "<p class=\"lede\">Course packs for Lemmata: a module's results, restated and proved in the checker's notation and numbered as in the notes, "
        "with deliberate mistakes to find. Open one to install it in the app.</p>"
        f'<p class="figures">{plural(len(packs), "pack")} · {total_entries} entries · {plural(total_traps, "trap")} · '
        f'<span class="verified-word">verified</span> under engine {escape(engine)}, {escape(nice_date(generated))}</p></header>'
        '<section class="results" aria-live="polite" hidden><h2 class="section-label">Matching entries</h2><ol class="result-list"></ol></section>'
        f'<section class="all-packs" aria-labelledby="all-title"><h2 class="section-label" id="all-title">All packs</h2><ul class="briefs">{briefs}</ul></section>'
        '<section class="publish-band" aria-labelledby="publish-title"><h2 id="publish-title">Publish a pack</h2>'
        "<p>Make a pack from your proofs in the app, then open a pull request. Every entry is checked with the engine students use before anyone can install it.</p>"
        '<a class="text-link" href="./publish/">How to publish</a></section>'
    )
    page("", "Lemmata packs", "Course packs for Lemmata, every entry verified by the checker.", front)

    for pack in packs:
        main = (
            f'<header class="page-head pack-head">{pack_head(pack, engine, generated)}'
            f"{verified_line(pack, engine, generated)}{actions(pack, '../../../')}</header>"
            f'<p class="filter-note" aria-live="polite" hidden></p>'
            f"{chapters_html(pack)}"
        )
        page(slug_path(pack["name"]).rstrip("/"), f"{pack['title']} · Lemmata packs", pack.get("summary", ""), main, current=pack["name"])

    guide = (WEB / "publish.html").read_text(encoding="utf-8")
    page("publish", "Publish a pack · Lemmata packs", "How to make a Lemmata pack and publish it to the registry.", fill(guide, {"contribute": escape(index["contribute"]), "app": escape(APP)}, "publish.html"))

    # What the search box reads: every entry, with where it lives.
    search = [
        {"pack": p["name"], "title": p["title"], "ref": e["ref"], "entry": e["title"], "kind": e["kind"], "url": f"{slug_path(p['name'])}#{e['id']}"}
        for p in packs
        for e in p["entries"]
    ]
    (out / "search.json").write_text(json.dumps(search, ensure_ascii=False) + "\n", encoding="utf-8")
    shutil.copytree(WEB / "assets", out / "assets", dirs_exist_ok=True)
    return written
