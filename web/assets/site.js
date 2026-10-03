// Lemmata packs: the theme toggle and the search.
//
// The search narrows the rail's packs as you type.  On a pack's page it also
// narrows the entries and lights their keys; on the front page it lists the
// matching entries across every pack (search.json), each a link to its entry.
// Every page is complete without this file.

const THEME_KEY = "aether-theme"; // shared with the app and its site

for (const button of document.querySelectorAll(".theme-toggle")) {
  button.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // The choice lasts for this page.
    }
  });
}

// "Browse" is current on the catalogue itself.
const browse = document.querySelector("[data-browse]");
if (browse && !document.querySelector(".pack-head") && !document.querySelector(".guide")) browse.setAttribute("aria-current", "page");
// …and "Publish a pack" on the guide.
if (document.querySelector(".guide")) document.querySelector('.top-links a[href$="publish/"]')?.setAttribute("aria-current", "page");

// Narrow screens: the rail folds to the search and a button.
const rail = document.querySelector(".rail");
const toggle = document.querySelector(".rail-toggle");
function openRail(open) {
  rail.classList.toggle("is-open", open);
  toggle.setAttribute("aria-expanded", String(open));
}
toggle?.addEventListener("click", () => openRail(!rail.classList.contains("is-open")));

const input = document.getElementById("search");
const root = document.body.dataset.root || "./";
const tokens = (text) => text.toLowerCase().split(/[^a-z0-9.§]+/).filter(Boolean);
const matchesAll = (haystack, words) => words.every((w) => haystack.split(/[^a-z0-9.§]+/).some((t) => t.startsWith(w)));

let index = null;
async function searchIndex() {
  if (!index) {
    try {
      index = await (await fetch(`${root}search.json`)).json();
    } catch {
      index = [];
    }
  }
  return index;
}

function narrowRail(words) {
  let any = false;
  for (const group of document.querySelectorAll(".rail-group")) {
    let shown = 0;
    for (const link of group.querySelectorAll(".rail-pack")) {
      const hit = !words.length || matchesAll(link.dataset.search, words) || (index ?? []).some((e) => e.pack === link.dataset.pack && matchesAll(`${e.ref} ${e.entry}`.toLowerCase(), words));
      link.parentElement.hidden = !hit;
      if (hit) shown += 1;
    }
    group.hidden = shown === 0;
    any ||= shown > 0;
  }
  document.querySelector(".rail-empty").hidden = any;
}

function narrowBriefs(words) {
  for (const brief of document.querySelectorAll(".brief")) {
    const pack = brief.dataset.pack;
    brief.hidden = words.length > 0 && !(matchesAll(brief.dataset.search, words) || (index ?? []).some((e) => e.pack === pack && matchesAll(`${e.ref} ${e.entry}`.toLowerCase(), words)));
  }
}

function narrowEntries(words) {
  const entries = [...document.querySelectorAll(".entry")];
  if (!entries.length) return;
  let shown = 0;
  for (const entry of entries) {
    const hit = !words.length || matchesAll(entry.dataset.search, words);
    entry.hidden = !hit;
    entry.classList.toggle("is-match", hit && words.length > 0);
    if (hit) shown += 1;
  }
  for (const chapter of document.querySelectorAll(".chapter")) {
    chapter.hidden = !chapter.querySelector(".entry:not([hidden])");
  }
  const note = document.querySelector(".filter-note");
  note.hidden = !words.length;
  note.textContent = words.length ? `${shown} of ${entries.length} entries match “${input.value.trim()}”` : "";
}

function listResults(words) {
  const box = document.querySelector(".results");
  if (!box) return;
  const list = box.querySelector(".result-list");
  if (!words.length) {
    box.hidden = true;
    list.replaceChildren();
    return;
  }
  const hits = (index ?? []).filter((e) => matchesAll(`${e.ref} ${e.entry} ${e.title} ${e.pack}`.toLowerCase(), words)).slice(0, 40);
  list.replaceChildren(
    ...hits.map((e) => {
      const li = document.createElement("li");
      li.className = "result";
      const link = document.createElement("a");
      link.href = `${root}${e.url}`;
      link.textContent = e.ref;
      const body = document.createElement("div");
      const title = document.createElement("p");
      title.className = "result-title";
      title.textContent = e.entry + (e.kind === "trap" ? " (trap)" : "");
      const where = document.createElement("p");
      where.className = "result-where";
      where.textContent = `${e.title} · ${e.pack}`;
      body.append(title, where);
      li.append(link, body);
      return li;
    }),
  );
  if (!hits.length) {
    const li = document.createElement("li");
    li.className = "result";
    li.textContent = "No entry matches. Try a course code, a theorem's name, or its number.";
    list.append(li);
  }
  box.hidden = false;
}

if (input) {
  const run = async () => {
    const words = tokens(input.value);
    if (words.length) await searchIndex();
    narrowRail(words);
    narrowBriefs(words);
    narrowEntries(words);
    if (words.length && rail) openRail(true);
    listResults(words);
  };
  input.addEventListener("input", run);
  // A search typed on one page carries to the next (?q=).
  const q = new URLSearchParams(location.search).get("q");
  if (q) {
    input.value = q;
    run();
  }
}
