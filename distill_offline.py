#!/usr/bin/env python3
"""
distill_offline.py — the offline engine for /distill-offline.

This is the deterministic, zero-LLM-token half of the document-distiller
pipeline. The LLM does exactly ONE thing the LLM can't be replaced for:
read the doc and emit a compact JSON array of classified, deduped,
salience-scored knowledge units. Everything mechanical around that — rendering
markdown from the JSON, writing the central + source-adjacent files, computing
the diff/add scope, and an honest degraded heuristic extract — lives here and
costs no tokens.

Why this saves tokens vs the original /distill (see docs in the skill):
  - The original has the model emit BOTH json and markdown. The markdown is
    fully derivable from the json, so ~half the output tokens are spent twice.
    Here the model emits json only; `render` produces the markdown.
  - All file I/O, section ordering, salience sorting, dedup counting, the
    `## Removed` section, and source-adjacent copies are done here, not by the
    model.
  - `diff` scopes --diff/--add so the model never re-reads unchanged text.

Subcommands:
  render   compact units JSON  -> central .md/.json + source-adjacent copies
  diff     old + new files     -> added/removed hunks JSON (scopes the LLM pass)
  merge    existing + new units-> deduped-against-existing units JSON (re-emit)
  fetch    URL                 -> plain text (offline ingest; no MCP round-trip)
  extract  plain text          -> HEURISTIC candidate units (degraded, honest)
  mirror   web-text-mirror file-> stats / page list / per-page split / extract
           with per-page URL provenance (bulk also auto-splits mirror files)
  bulk     dir or mirror file   -> 3-stage offline funnel: exact-hash dedup ->
           semantic cluster (ollama) -> grouped master markdown
  index    distillation JSON    -> persistent flat-JSON vector index (ollama)
  novelty  candidate units JSON -> drop candidates already covered by indexes
  clean    local HTML/text file -> page text only (tags/CSS/JS stripped)

All modes are stdlib-only. Read the skill for how the LLM pass hands off here.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as _dt
import difflib
import html
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

DIST_DIR = Path.home() / ".claude" / "distillations"
INDEX_DIR = DIST_DIR / ".index"

# Ollama is used ONLY as an offline semantic layer (dedup + novelty filtering).
# It never reads or generates prose — embeddings only — so it adds no LLM tokens.
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://192.168.4.75:11434").rstrip("/")
# Optional multi-host round-robin for the merge stage's Stage-3 embedding —
# a single-host embed serializes every chunk behind one Ollama instance's
# `-np 1` concurrency; spreading chunks over all 3 boxes' Ollama instances
# cuts merge wall time roughly by the number of hosts.
OLLAMA_URLS = [u.strip().rstrip("/") for u in os.environ.get("OLLAMA_HOSTS", "").split(",") if u.strip()] or [OLLAMA_URL]
DEFAULT_EMBED_MODEL = os.environ.get("DISTILL_EMBED_MODEL", "mxbai-embed-large")

# Taxonomy order drives section order in the markdown. Keep in sync with SKILL.md.
TYPE_ORDER = [
    "concept",
    "fact",
    "actionable",
    "question",
    "problem",
    "statement",
    "quote",
    "idea",
]
TYPE_HEADINGS = {
    "concept": "Concepts",
    "fact": "Facts",
    "actionable": "Actionables",
    "question": "Questions",
    "problem": "Problems",
    "statement": "Statements",
    "quote": "Quotes",
    "idea": "Ideas",
}
SALIENCE_RANK = {"high": 0, "medium": 1, "low": 2}


def _today() -> str:
    return _dt.date.today().isoformat()


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", (text or "").lower()).strip()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:80] or "distillation"


# --------------------------------------------------------------------------- #
# render — the emit phase (the main token win: model never writes markdown)
# --------------------------------------------------------------------------- #

def _unit_salience(u: dict) -> int:
    return SALIENCE_RANK.get((u.get("salience") or "medium").lower(), 1)


def _render_unit_line(u: dict) -> str:
    t = u["type"]
    text = u.get("text", "").strip()
    anchor = u.get("source_anchor", "")
    sal = (u.get("salience") or "").lower()
    anchor_md = f"_{anchor}_" if anchor else ""

    if t == "quote":
        attr = u.get("attribution")
        q = f'> "{text}"'
        if attr:
            q += f" — {attr}"
        if anchor:
            q += f", {anchor_md}"
        if sal == "high":
            q += " · salience: high"
        return q

    if t == "concept":
        # Concepts: bold the leading term if the text is "Term — gloss".
        head, sep, rest = text.partition(" — ")
        body = f"**{head}** — {rest}" if sep else f"**{text}**"
        line = f"- {body}"
    elif t == "actionable":
        line = f"- [ ] {text}"
    else:
        line = f"- {text}"

    if anchor:
        line = f"{line} — {anchor_md}"
    # Salience shown for concepts (matches the original's convention) and any
    # explicitly-high unit, to keep the list scannable; omitted otherwise.
    if sal and (t == "concept" or sal == "high"):
        line += f" · salience: {sal}"
    return line


def render_markdown(data: dict) -> str:
    src = data.get("source", {})
    units = data.get("units", [])
    generated = data.get("generated") or _today()

    active = [u for u in units if u.get("status") != "removed"]
    removed = [u for u in units if u.get("status") == "removed"]
    after_dedup = len(active)
    extracted = after_dedup + sum(len(u.get("duplicates", []) or []) for u in units)

    title = src.get("title") or "Untitled document"
    ref = src.get("ref") or src.get("url") or src.get("path") or "(in-context document)"

    lines = [f"# Distilled: {title}", ""]
    lines.append(f"- Source: `{ref}`")
    lines.append(f"- Distilled: {generated}")
    lines.append(f"- Units: {extracted} extracted ({after_dedup} after dedup)")
    if data.get("anchors_note"):
        lines.append(f"- Anchors: {data['anchors_note']}")
    lines.append("")

    by_type: dict[str, list[dict]] = {t: [] for t in TYPE_ORDER}
    for u in active:
        t = u.get("type", "statement")
        if t not in by_type:
            t = "statement"  # unknown/typo'd type still renders, never dropped
        by_type[t].append(u)

    for t in TYPE_ORDER:
        group = by_type.get(t) or []
        if not group:
            continue
        group.sort(key=_unit_salience)
        lines.append(f"## {TYPE_HEADINGS[t]}")
        lines.append("")
        for u in group:
            lines.append(_render_unit_line(u))
        lines.append("")

    if removed:
        lines.append("## Removed")
        lines.append("")
        for u in removed:
            anchor = u.get("source_anchor", "")
            when = u.get("removed_on") or generated
            anchor_md = f" — _{anchor}_" if anchor else ""
            lines.append(f"- {u.get('text','').strip()}{anchor_md} · removed {when}")
        lines.append("")

    followups = data.get("followups") or []
    if followups:
        lines.append("## Suggested follow-ups (/dr)")
        lines.append("")
        for f in followups:
            concept = f.get("concept", "").strip()
            why = f.get("why", "").strip()
            lines.append(f"- `/dr {concept}` — {why}" if why else f"- `/dr {concept}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _write_pair(stem_dir: Path, slug: str, generated: str, data: dict,
                json_only: bool) -> list[str]:
    stem_dir.mkdir(parents=True, exist_ok=True)
    written = []
    json_path = stem_dir / f"{slug}-{generated}.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    written.append(str(json_path))
    if not json_only:
        md_path = stem_dir / f"{slug}-{generated}.md"
        md_path.write_text(render_markdown(data))
        written.append(str(md_path))
    return written


def cmd_render(args) -> int:
    data = _load_json_input(args.in_file)
    src = data.setdefault("source", {})
    generated = data.get("generated") or _today()
    data["generated"] = generated

    slug = args.slug or _slugify(src.get("title") or _basename_of(src))
    written = _write_pair(DIST_DIR, slug, generated, data, args.json_only)

    # Source-adjacent copy: only for file inputs, best-effort.
    adjacent = []
    if src.get("type") == "file" and src.get("ref"):
        srcp = Path(src["ref"]).expanduser()
        adj_slug = f"{srcp.stem}-distilled"
        try:
            adjacent = _write_pair(srcp.parent, adj_slug, generated, data,
                                    args.json_only)
        except OSError as e:
            print(f"WARN source-adjacent copy failed ({e}); central copy kept.",
                  file=sys.stderr)

    result = {
        "written": written,
        "source_adjacent": adjacent,
        "units_after_dedup": len([u for u in data.get("units", [])
                                  if u.get("status") != "removed"]),
    }
    print(json.dumps(result, indent=2))
    return 0


def _basename_of(src: dict) -> str:
    ref = src.get("ref") or src.get("url") or src.get("path") or ""
    if not ref:
        return "distillation"
    ref = ref.rstrip("/")
    return Path(ref).name or ref.split("/")[-1] or "distillation"


# --------------------------------------------------------------------------- #
# diff — scope --diff so the LLM never re-reads unchanged text
# --------------------------------------------------------------------------- #

def _read_text(path_or_url: str) -> str:
    p = Path(path_or_url).expanduser()
    if p.exists():
        return p.read_text(errors="replace")
    raise FileNotFoundError(path_or_url)


def _unified_hunks(old: str, new: str) -> dict:
    """Return added and removed line groups using difflib (git-independent)."""
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    added, removed = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            for j in range(j1, j2):
                added.append({"new_line": j + 1, "text": new_lines[j]})
        if tag in ("replace", "delete"):
            for i in range(i1, i2):
                removed.append({"old_line": i + 1, "text": old_lines[i]})
    return {"added": added, "removed": removed}


def cmd_diff(args) -> int:
    old = _read_text(args.old)
    new = _read_text(args.new)
    hunks = _unified_hunks(old, new)
    # Drop blank-only added/removed lines — no signal to classify.
    hunks["added"] = [h for h in hunks["added"] if h["text"].strip()]
    hunks["removed"] = [h for h in hunks["removed"] if h["text"].strip()]
    print(json.dumps(hunks, indent=2, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------- #
# merge — dedup NEW units against an EXISTING set only (for --add / --diff)
# --------------------------------------------------------------------------- #

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _next_id(units: list[dict]) -> int:
    mx = 0
    for u in units:
        m = re.match(r"u(\d+)", u.get("id", ""))
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1


def cmd_merge(args) -> int:
    if not (0.0 <= args.threshold <= 1.0):
        print(f"ERROR: --threshold must be in [0,1], got {args.threshold}", file=sys.stderr)
        return 2
    existing = _load_json_input(args.existing)
    new_units = _load_json_input(args.new_units)
    if isinstance(new_units, dict):
        new_units = new_units.get("units", [])

    base = existing.get("units", [])
    # Existing units NOT marked removed this run are the dedup targets.
    targets = [u for u in base if u.get("status") != "removed"]
    target_norms = [(u, _norm(u.get("text", ""))) for u in targets]

    # Semantic dedup (opt-in): catches reworded restatements the lexical ratio
    # misses. Falls back to lexical if ollama is unavailable.
    sem_targets = sem_cands = None
    if args.semantic and targets:
        try:
            sem_targets = _ollama_embed([u.get("text", "") for u in targets], args.model)
            sem_cands = _ollama_embed([nu.get("text", "") for nu in new_units], args.model)
        except OllamaUnavailable as e:
            print(f"WARN {e}; semantic dedup off, using lexical.", file=sys.stderr)
            sem_targets = sem_cands = None

    nid = _next_id(base)
    folded = 0
    kept = 0
    today = _today()
    for ci, nu in enumerate(new_units):
        ntext = _norm(nu.get("text", ""))
        best, best_ratio = None, 0.0
        for ti, (u, tn) in enumerate(target_norms):
            if sem_targets is not None:
                r = _cosine(sem_cands[ci], sem_targets[ti])
            else:
                sm = difflib.SequenceMatcher(a=ntext, b=tn, autojunk=False)
                # quick_ratio/real_quick_ratio are provable upper bounds on
                # ratio() — skipping under-threshold pairs cannot change results
                # and avoids O(N*M) full edit-distance on large unit sets.
                if sm.real_quick_ratio() < args.threshold:
                    continue  # can never fold; only >=threshold matches matter
                r = sm.ratio()
            if r > best_ratio:
                best, best_ratio = u, r
        if best is not None and best_ratio >= args.threshold:
            # Folded units never consume an id from the kept-unit counter —
            # consecutive folds used to log the SAME placeholder id.
            best.setdefault("duplicates", []).append(nu.get("id") or f"new-{ci:03d}")
            folded += 1
        else:
            uid = f"u{nid:03d}"
            nid += 1
            nu["id"] = uid
            nu.setdefault("canonical", uid)
            nu.setdefault("added_in", today)
            base.append(nu)
            kept += 1

    existing["units"] = base
    existing["generated"] = today
    print(json.dumps(existing, indent=2, ensure_ascii=False))
    print(f"# merged: {kept} new, {folded} folded as duplicates "
          f"(threshold {args.threshold})", file=sys.stderr)
    return 0


# --------------------------------------------------------------------------- #
# fetch — offline URL -> text (avoids an MCP/WebFetch round-trip when possible)
# --------------------------------------------------------------------------- #

class _TextExtractor(HTMLParser):
    # Tags whose *contents* are markup/style/script, never page text — dropped whole.
    _SKIP = {"script", "style", "noscript", "head", "nav", "footer", "svg",
             "template", "iframe", "object", "embed", "canvas"}
    # Tags that imply a line/paragraph break in the extracted text.
    _BREAK = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6",
              "tr", "section", "article", "header", "blockquote", "pre"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BREAK:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in self._BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        raw = html.unescape(raw)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n[ \t]+", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


_HTML_TAG_RE = re.compile(r"</?(?:div|p|span|a|body|head|table|tr|td|ul|li|script|style|img|br|h[1-6])\b[^>]*>")


def _looks_like_html(text: str, path: str | None = None) -> bool:
    """Detect HTML by extension or by content — used to auto-strip before
    distill. Content detection needs STRUCTURAL evidence (doctype/<html>, or a
    real density of tags), not a mere mention of a tag name: prose ABOUT web
    dev must never get routed through trafilatura, which silently drops text
    it can't classify as main content."""
    if path and path.lower().rsplit(".", 1)[-1] in ("html", "htm", "xhtml"):
        return True
    head = text[:4096].lower()
    if "<!doctype html" in head or "<html" in head:
        return True
    # Structural evidence: several tag instances, more than one tag TYPE, and
    # at least one closing tag. Catches small real fragments like
    # <div><p>x</p></div> while prose that merely mentions <body> or <div>
    # (1-2 bare mentions, no closers) stays prose.
    tags = _HTML_TAG_RE.findall(head)
    if len(tags) < 4:
        return False
    types = {re.sub(r"[^a-z0-9]", "", t.split()[0]) for t in tags}
    return len(types) >= 2 and any(t.startswith("</") for t in tags)


def _html_to_text(body: str) -> str:
    """Strip all tags/CSS/JS and return only the page text using trafilatura."""
    import trafilatura
    # Try high-recall extraction first
    res = trafilatura.extract(body, favor_recall=True, include_comments=True)
    if res:
        return res
    # Fallback if trafilatura finds no main content
    parser = _TextExtractor()
    parser.feed(body)
    parser.close()
    return parser.text()


def cmd_fetch(args) -> int:
    if not re.match(r"^https?://", args.url):
        print("ERROR fetch: only http(s) URLs are allowed", file=sys.stderr)
        return 2
    try:
        out = subprocess.run(
            # --proto pins curl to http(s) even on redirects (no file:// etc.)
            ["curl", "-fsSL", "--proto", "=http,https", "--max-time", str(args.timeout), args.url],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR fetch failed: {e}", file=sys.stderr)
        return 2
    body = out.stdout
    if _looks_like_html(body):
        body = _html_to_text(body)
    print(body)
    return 0


def cmd_clean(args) -> int:
    """Read a local file (or stdin) and, if it is HTML, discard every tag, CSS
    block, and script, printing only the page text. Non-HTML passes through
    unchanged so it is safe to run on any local file before distilling."""
    if args.in_file in (None, "-"):
        body = sys.stdin.read()
        path = None
    else:
        body = _read_text(args.in_file)
        path = args.in_file
    if args.force_html or _looks_like_html(body, path):
        body = _html_to_text(body)
    print(body)
    return 0


# --------------------------------------------------------------------------- #
# extract — HEURISTIC candidate units (DEGRADED; honest first-pass only)
# --------------------------------------------------------------------------- #

_ACTION_RE = re.compile(r"^\s*(?:-\s*\[\s?\]|\d+\.|[-*])?\s*"
                        r"(should|must|need to|todo|do |run |add |use |ensure|"
                        r"make sure|remember to|don'?t forget)", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def _heuristic_type(sent: str) -> str:
    s = sent.strip()
    if s.startswith(('"', "“", ">")) or (s.count('"') >= 2):
        return "quote"
    if s.endswith("?"):
        return "question"
    if _ACTION_RE.match(s):
        return "actionable"
    if re.search(r"\b(risk|fails?|cannot|broken|limitation|bug|issue|problem)\b", s, re.I):
        return "problem"
    if re.search(r"\d", s) and re.search(r"\b(is|are|was|were|has|have|costs?|takes?)\b", s, re.I):
        return "fact"
    return "statement"


def _extract_units_from_text(text: str, anchor_prefix: str = "", start_id: int = 1) -> tuple[list[dict], int]:
    """Shared heuristic extractor. anchor_prefix (e.g. a page URL) is prepended
    to the per-line anchor so multi-page inputs keep per-page provenance."""
    units = []
    nid = start_id
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or len(line) < 20:
            continue
        for sent in _SENT_SPLIT.split(line):
            sent = sent.strip()
            if len(sent) < 20:
                continue
            anchor = f"{anchor_prefix}#L{lineno}" if anchor_prefix else f"L{lineno}"
            units.append({
                "id": f"u{nid:03d}",
                "type": _heuristic_type(sent),
                "text": sent,
                "source_anchor": anchor,
                "salience": "medium",
                "canonical": f"u{nid:03d}",
            })
            nid += 1
    return units, nid


def cmd_extract(args) -> int:
    if args.in_file in (None, "-"):
        text = sys.stdin.read()
        path = None
    else:
        text = _read_text(args.in_file)
        path = args.in_file
    # Mirror check FIRST: HTML-sniffing a mirror whose pages quote HTML would
    # strip the banners and silently destroy per-page provenance.
    pages = parse_mirror(text)
    if pages:
        # web-text-mirror docset: anchor every unit to its originating page URL
        units, nid = [], 1
        for pg in pages:
            page_units, nid = _extract_units_from_text(pg["text"], anchor_prefix=pg["url"], start_id=nid)
            units.extend(page_units)
    else:
        if _looks_like_html(text, path):
            text = _html_to_text(text)  # distill only page text, never markup
        units, _ = _extract_units_from_text(text)
    result = {
        "_warning": "HEURISTIC DEGRADED EXTRACT — not a real distillation. "
                    "No semantic dedup, no cross-doc reconciliation, coarse "
                    "types. Feed to the LLM classify pass or treat as a rough "
                    "first cut only.",
        "units": units,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------- #
# mirror — web-text-mirror multi-page docset support
#
# web-text-mirror concatenates a whole docset into ONE markdown file, with each
# page bounded by a banner triple:
#
#   ================================================================== (>=10 =)
#   URL: https://example.com/docs/page.html
#   ================================================================== (>=10 =)
#   <page text ...>
#
# This section parses that fixed contract so every downstream stage (extract,
# bulk, indexing) keeps per-page URL provenance instead of treating the mirror
# as one giant anonymous blob.
# --------------------------------------------------------------------------- #

_MIRROR_BANNER_RE = re.compile(r"^={10,}\s*$")
_MIRROR_URL_RE = re.compile(r"^URL:\s*(https?://\S+)\s*$")
_MIRROR_PAGE_FILE_RE = re.compile(r"^\d+_")  # files written by split_mirror_to_dir


def parse_mirror(text: str) -> list[dict] | None:
    """Split a web-text-mirror file into pages. Returns a list of
    {url, start_line, text} dicts, or None when the text is not a mirror
    (no URL banners found). Single-page mirrors are valid."""
    lines = text.splitlines()
    page_starts = []  # (index_of_banner_line, url)
    for i in range(len(lines) - 2):
        if (_MIRROR_BANNER_RE.match(lines[i])
                and _MIRROR_BANNER_RE.match(lines[i + 2])):
            m = _MIRROR_URL_RE.match(lines[i + 1])
            if m:
                page_starts.append((i, m.group(1)))
    if not page_starts:
        return None
    pages = []
    for n, (i, url) in enumerate(page_starts):
        body_start = i + 3
        body_end = page_starts[n + 1][0] if n + 1 < len(page_starts) else len(lines)
        pages.append({
            "url": url,
            "start_line": body_start + 1,
            "text": "\n".join(lines[body_start:body_end]).strip("\n"),
        })
    return pages


def _mirror_hostname(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url)
    return m.group(1) if m else "unknown-host"


def docset_key(pages: list[dict], path) -> str:
    """Deterministic docset identity: <source hostname>__<mirror filename stem>.
    Shared index/collection names derive from this so consuming skills reuse
    one index per docset instead of re-embedding."""
    host = _mirror_hostname(pages[0]["url"]) if pages else "unknown-host"
    stem = Path(path).stem if path else "stdin"
    return f"{_slugify(host)}__{_slugify(stem)}"


def _page_slug(url: str, maxlen: int = 60) -> str:
    m = re.match(r"https?://[^/]+/?(.*)", url)
    tail = (m.group(1) if m else url).rstrip("/")
    tail = re.sub(r"\.html?$", "", tail)
    slug = _slugify(tail.replace("/", "-")) or "index"
    return slug[:maxlen]


def split_mirror_to_dir(text: str, out_dir: Path) -> int:
    """Write one .md file per mirror page into out_dir. Filenames embed the
    page's URL path so bulk's per-file source tracking keeps provenance; the
    first line repeats the full URL (clean_and_split strips URLs, so it never
    pollutes extracted units)."""
    pages = parse_mirror(text)
    if not pages:
        raise ValueError("input is not a web-text-mirror docset (no URL banners found)")
    out_dir.mkdir(parents=True, exist_ok=True)
    # Clear stale page files from a previous split (a shrunk/reordered mirror
    # would otherwise contaminate a later bulk run) — but only files THIS tool
    # wrote, tracked in a manifest. Numbered .md files are a common personal
    # note convention; never delete files we can't prove are ours.
    manifest_path = out_dir / ".mirror_split_manifest.json"
    ours = set()
    if manifest_path.exists():
        try:
            ours = set(json.loads(manifest_path.read_text()))
        except (OSError, json.JSONDecodeError):
            ours = set()
    strays = [p.name for p in out_dir.glob("*.md")
              if _MIRROR_PAGE_FILE_RE.match(p.name) and p.name not in ours]
    if strays:
        raise ValueError(
            f"{out_dir} already contains {len(strays)} numbered .md file(s) not "
            f"written by a previous split (e.g. {strays[0]!r}) — refusing to "
            "overwrite them; use an empty/dedicated --split-dir")
    for name in ours:
        stale = out_dir / name
        if stale.exists():
            stale.unlink()
    written = []
    for n, pg in enumerate(pages, start=1):
        fname = f"{n:03d}_{_page_slug(pg['url'])}.md"
        (out_dir / fname).write_text(f"URL: {pg['url']}\n\n{pg['text']}\n")
        written.append(fname)
    manifest_path.write_text(json.dumps(written, indent=0))
    return len(pages)


def cmd_mirror(args) -> int:
    if args.in_file in (None, "-"):
        text = sys.stdin.read()
        path = None
    else:
        text = _read_text(args.in_file)
        path = args.in_file
    pages = parse_mirror(text)
    if not pages:
        print("ERROR: input is not a web-text-mirror docset (no URL banners found)", file=sys.stderr)
        return 2

    if args.list:
        for pg in pages:
            print(pg["url"])
        return 0

    if args.split_dir:
        n = split_mirror_to_dir(text, Path(args.split_dir).expanduser())
        print(f"Split {n} pages into {args.split_dir}")
        return 0

    if args.extract:
        units, nid = [], 1
        for pg in pages:
            page_units, nid = _extract_units_from_text(pg["text"], anchor_prefix=pg["url"], start_id=nid)
            units.extend(page_units)
        print(json.dumps({
            "_warning": "HEURISTIC DEGRADED EXTRACT — see extract subcommand.",
            "docset": docset_key(pages, path),
            "units": units,
        }, indent=2, ensure_ascii=False))
        return 0

    # default: --stats
    hosts = sorted({_mirror_hostname(pg["url"]) for pg in pages})
    stats = {
        "docset": docset_key(pages, path),
        "pages": len(pages),
        "bytes": len(text.encode()),
        "est_tokens": len(text) // 4,
        "hosts": hosts,
    }
    print(json.dumps(stats, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# semantic layer (ollama embeddings) — offline, token-free
#
# Why this is here and what it does NOT do: distilling ONE fresh file still
# needs the whole doc in the LLM's context (every part is a candidate unit), so
# no index shrinks that first pass. The index pays off across runs: --add,
# --diff, and multi-file corpus distillation. Embed each distilled unit once;
# on later runs the `novelty` filter drops candidate material already covered by
# a prior distillation BEFORE it reaches the LLM, so the classify pass only sees
# genuinely new content. It also lets dedup catch reworded restatements that the
# lexical difflib path misses. All of this is embeddings-only: zero LLM tokens.
# --------------------------------------------------------------------------- #

class OllamaUnavailable(RuntimeError):
    pass


def _ollama_embed(texts: list[str], model: str, host: str | None = None) -> list[list[float]]:
    """Batch-embed via ollama /api/embed. Raises OllamaUnavailable on any error
    so callers can fall back to the lexical path instead of dying."""
    if not texts:
        return []
    base_url = (host or OLLAMA_URL).rstrip("/")
    payload = json.dumps({"model": model, "input": texts}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if "not found" in body.lower():
            print(f"Model '{model}' missing. Pulling now (this may take a minute)...", file=sys.stderr)
            import os
            env = os.environ.copy()
            env["OLLAMA_HOST"] = OLLAMA_URL
            try:
                subprocess.run(["ollama", "pull", model], env=env, check=True)
            except (subprocess.SubprocessError, OSError) as pull_err:
                # Typo'd model, registry unreachable, no ollama CLI, disk full —
                # keep the documented clean-error/lexical-fallback contract.
                raise OllamaUnavailable(f"ollama pull '{model}' failed: {pull_err}") from pull_err
            # Retry once
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read())
            except Exception as retry_err:
                raise OllamaUnavailable(f"ollama embed failed after pull: {retry_err}") from retry_err
        else:
            raise OllamaUnavailable(f"ollama embed failed HTTP {e.code}: {body}") from e
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise OllamaUnavailable(f"ollama embed failed ({e})") from e
    
    embs = data.get("embeddings") if isinstance(data, dict) else None
    if not isinstance(embs, list) or len(embs) != len(texts):
        # A count mismatch would silently misalign unit<->vector pairing in
        # every caller (zip truncation / positional indexing) — always raise
        # so callers hit their documented lexical-fallback path instead.
        got = len(embs) if isinstance(embs, list) else 0
        raise OllamaUnavailable(f"ollama returned {got} embeddings for {len(texts)} inputs")
    return embs


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _index_path(name: str) -> Path:
    return INDEX_DIR / f"{_slugify(name)}.json"


def cmd_index(args) -> int:
    """Embed the units of a distillation JSON and persist a vector index so
    future runs can dedup / novelty-filter against it. Idempotent per name."""
    data = _load_json_input(args.in_file)
    units = data.get("units", []) if isinstance(data, dict) else data
    units = [u for u in units if u.get("status") != "removed" and u.get("text")]
    src = data.get("source", {}) if isinstance(data, dict) else {}
    name = args.name or _slugify(src.get("title") or _basename_of(src))

    texts = [u["text"] for u in units]
    try:
        vectors = _ollama_embed(texts, args.model)
    except OllamaUnavailable as e:
        print(f"ERROR {e}; index needs ollama running.", file=sys.stderr)
        return 2

    entries = [
        {"id": u.get("id"), "text": u["text"], "type": u.get("type"),
         "source": src.get("ref"), "vector": v}
        for u, v in zip(units, vectors)
    ]
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    path = _index_path(name)
    path.write_text(json.dumps(
        {"model": args.model, "generated": _today(), "entries": entries},
        ensure_ascii=False))
    print(json.dumps({"index": str(path), "vectors": len(entries),
                      "model": args.model}, indent=2))
    return 0


def _load_indexes(names: list[str] | None) -> list[dict]:
    if names:
        paths = [_index_path(n) for n in names]
    else:
        paths = sorted(INDEX_DIR.glob("*.json")) if INDEX_DIR.exists() else []
    out = []
    for p in paths:
        if p.exists():
            out.extend(json.loads(p.read_text()).get("entries", []))
    return out


def cmd_novelty(args) -> int:
    """Given candidate units/lines and one or more prior indexes, emit only the
    candidates NOT already covered (cosine below --threshold to every indexed
    unit). This is the incremental/corpus token-saver: the LLM classify pass
    only ever sees novel material. Falls back to lexical-only if ollama is down."""
    if not (0.0 <= args.threshold <= 1.0):
        print(f"ERROR: --threshold must be in [0,1], got {args.threshold}", file=sys.stderr)
        return 2
    cand = _load_json_input(args.in_file)
    if isinstance(cand, dict):
        cand = cand.get("units") or cand.get("added") or []
    cand_texts = [c.get("text", "") for c in cand]

    index = _load_indexes(args.against)
    if not index:
        # Nothing to compare against — everything is novel.
        print(json.dumps({"novel": cand, "matched": [],
                          "note": "no prior index; all candidates novel"},
                         ensure_ascii=False, indent=2))
        return 0

    index_texts = [e["text"] for e in index]
    semantic = True
    try:
        cand_vecs = _ollama_embed(cand_texts, args.model)
        idx_vecs = [e["vector"] for e in index]
    except OllamaUnavailable as e:
        print(f"WARN {e}; falling back to lexical novelty.", file=sys.stderr)
        semantic = False

    novel, matched = [], []
    for i, c in enumerate(cand):
        best_sim, best_j = 0.0, -1
        if semantic:
            for j, iv in enumerate(idx_vecs):
                s = _cosine(cand_vecs[i], iv)
                if s > best_sim:
                    best_sim, best_j = s, j
        else:
            ci_norm = _norm(cand_texts[i])
            for j, it in enumerate(index_texts):
                sm = difflib.SequenceMatcher(a=ci_norm, b=_norm(it), autojunk=False)
                # Upper-bound prune: a sub-threshold pair can never count as
                # matched, so skipping it cannot change the novel/matched split.
                if sm.real_quick_ratio() < args.threshold:
                    continue
                s = sm.ratio()
                if s > best_sim:
                    best_sim, best_j = s, j
        if best_sim >= args.threshold:
            matched.append({"candidate": c.get("text"), "similarity": round(best_sim, 3),
                            "matched_id": index[best_j].get("id"),
                            "matched_text": index[best_j].get("text")})
        else:
            novel.append(c)

    print(json.dumps({
        "mode": "semantic" if semantic else "lexical",
        "threshold": args.threshold,
        "novel_count": len(novel), "matched_count": len(matched),
        "novel": novel, "matched": matched,
    }, ensure_ascii=False, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# plumbing
import os
import sys
import json
import re
import argparse
import urllib.request
import urllib.error
import html
import unicodedata
import hashlib
import math
import subprocess
import difflib
from pathlib import Path
from html.parser import HTMLParser

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

# Filler/boilerplate patterns stripped by clean_and_split. Compiled once at
# module scope (clean_and_split runs per file over whole corpora). NOTE: the
# wiki-navigation entries are corpus-specific leftovers from a MediaWiki run —
# harmless no-ops elsewhere; externalize if a second wiki corpus ever needs
# its own set.
_FILLER_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in (
    r'\b(?:to be honest|in my opinion|as a matter of fact)\b',
    r'\b(?:basically|literally|actually|obviously)\b',
    r'\b(What links here|Related changes|Special pages|Printable version|Permanent link|Page information|Cite this page|Navigation menu|Personal tools|Search|Log in|Main page|Recent changes|Random page|Privacy policy|About DMT Nexus Wiki|Disclaimers|Mobile view)\b',
    r'\b(Page|File|User page|Category) Discussion View source History\b',
    r'Pages that link to .*',
    r'From DMT-Nexus Wiki.*?Hide redirects',
    r'The following pages link to.*?\(20 50 100 250 500\)',
    r'No pages link to .*',
    r'This page was last modified on .*?\.',
    r'This page has been accessed [\d,]+ times\.',
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3} Talk for this IP address',
    r'No higher resolution available\.',
    r'Click on a date time to view the file as it appeared at that time\.',
    r'You cannot overwrite this file\.',
    r'The following page links to this file',
    r'File history File usage',
    r'Date TimeThumbnailDimensionsUserComment.*?Talk contribs\)',
    r'Contents \d+.*?References',
    r'General Plant Info Geographic distribution Identification Alkaloid content.*?References',
)]


def clean_and_split(raw):
    if '<html' in raw.lower() or '<body' in raw.lower() or '<div' in raw.lower():
        raw = _html_to_text(raw)
    
    raw = html.unescape(raw)
    raw = re.sub(r'http[s]?://\S+', '', raw)
    raw = re.sub(r'^(?:hi|hello|hey|welcome|dear|greetings|sincerely|best regards|cheers|thanks|thank you)\b.*$', '', raw, flags=re.IGNORECASE | re.MULTILINE)
    
    # Flatten punctuation and newlines BEFORE applying fillers
    raw = re.sub(r'[^\w\s.,;:!?()-]', ' ', raw)
    raw = raw.replace('\n', ' ')
    raw = re.sub(r'[ \t]+', ' ', raw)
    
    for pat in _FILLER_PATTERNS:
        raw = pat.sub('', raw)
        
    sentences = []
    # No more parts because we replaced \n with space
    for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', raw):
        s = s.strip()
        if len(s) > 20 and not re.match(r'^\d+$', s):
            sentences.append(s)
                
    return sentences

def categorize(text):
    if text.endswith('?'): return "Questions"
    if re.search(r'\b(should|must|need to|run|add|ensure)\b', text, re.I): return "Actionables"
    return "Statements"

def precompute_magnitude(vec):
    if not vec: return 0.0
    return math.sqrt(sum(a * a for a in vec))

def get_canonical(text):
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r'[^\w\s]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def compute_jaccard(set_a, set_b):
    if not set_a or not set_b: return 0.0
    return len(set_a & set_b) / len(set_a | set_b)

def _load_json_input(path):
    if path in (None, "-"):
        return json.load(sys.stdin)
    return json.loads(Path(path).expanduser().read_text())

def _shard_owns(path: Path, shard_index: int, shard_count: int) -> bool:
    """Stable (non-randomized) hash-mod ownership, same scheme as
    web-text-mirror's URL sharding -- a file's shard never changes between
    runs/machines, so --resume still works per shard."""
    return int(hashlib.md5(str(path).encode()).hexdigest(), 16) % shard_count == shard_index


def _shard_index_path(target_dir: Path, base_name: str, shard_index: int) -> Path:
    return target_dir / f".{base_name}_distill_index.shard{shard_index}.json"


def _merge_shard_indexes(target_dir: Path, base_name: str, shard_count: int) -> dict:
    """Associative merge of N shards' {hash: unit} maps -- safe because Stage 1
    is embarrassingly parallel (each file's lines hash independently); only
    Stage 3's semantic clustering needs the FULL merged unique-unit list, so
    it still runs once, here, after every shard's Stage 1 is in."""
    merged = {"files_processed": [], "unique_units": {}}
    seen_files = set()
    for i in range(shard_count):
        shard_path = _shard_index_path(target_dir, base_name, i)
        if not shard_path.exists():
            print(f"WARN: shard {i} index missing ({shard_path}), merging without it", file=sys.stderr)
            continue
        with open(shard_path) as f:
            shard = json.load(f)
        for h, unit in shard.get("unique_units", {}).items():
            if h in merged["unique_units"]:
                existing = merged["unique_units"][h]
                existing["count"] += unit["count"]
                existing["sources"] = list(set(existing["sources"]) | set(unit["sources"]))
            else:
                merged["unique_units"][h] = unit
        for fp in shard.get("files_processed", []):
            if fp not in seen_files:
                seen_files.add(fp)
                merged["files_processed"].append(fp)
    return merged


def cmd_bulk(args) -> int:
    # Flags are real (BooleanOptionalAction, default ON) — use --no-semantic,
    # --no-resume, --no-fast-clean, --no-recursive to opt out.
    if not (0.0 <= args.threshold <= 1.0):
        print(f"ERROR: --threshold must be in [0,1], got {args.threshold}", file=sys.stderr)
        return 2
    if args.shard_count > 1 and not (0 <= args.shard_index < args.shard_count):
        print(f"ERROR: --shard-index must be in [0,{args.shard_count})", file=sys.stderr)
        return 2

    target_path = Path(args.dir)
    if not target_path.exists():
        print(f"ERROR: Path {target_path} does not exist.", file=sys.stderr)
        return 2

    if target_path.is_file():
        raw = target_path.read_text(errors="ignore")
        mirror_pages = parse_mirror(raw)
        if mirror_pages:
            # web-text-mirror docset: split per page first so unit sources
            # carry per-page URL provenance instead of one giant blob.
            pages_dir = target_path.parent / f"{target_path.stem}.pages"
            n = split_mirror_to_dir(raw, pages_dir)
            print(f"Mirror docset detected ({docset_key(mirror_pages, target_path)}): "
                  f"split {n} pages into {pages_dir}", flush=True)
            target_dir = pages_dir
            base_name = target_path.stem
            # Only the numbered page files — never bulk's own master/preview
            # outputs from a previous run (they land in this same dir).
            files = sorted(p for p in pages_dir.glob("*.md")
                           if _MIRROR_PAGE_FILE_RE.match(p.name))
        else:
            target_dir = target_path.parent
            base_name = target_path.stem
            files = [target_path]
    else:
        target_dir = target_path
        base_name = target_path.resolve().name
        excluded = {".bulk_distill_index.json", "semantic_master.md", "master_distilled.md", "bulk_live_preview.md", "bulk_master.md", f".{base_name}_distill_index.json", f"{base_name}_master.md", f"{base_name}_live_preview.md"}
        print(f"Scanning directory {target_dir}...", flush=True)
        # Allow md, txt, and html files
        exts = {".html", ".md", ".txt"}
        walker = target_dir.rglob("*") if args.recursive else target_dir.glob("*")
        files = [p for p in walker if p.is_file() and p.suffix in exts and p.name not in excluded and "Special_" not in p.name and "Special:" not in str(p)]

    if args.shard_count > 1 and target_path.is_file():
        # A raw mirror file triggers a destructive split (clears stale pages
        # from a prior run) -- concurrent shards racing that would corrupt
        # each other's output. Sharding only ever targets an ALREADY-split
        # pages dir (the dispatcher splits once, up front, then fans out).
        print("ERROR: --shard-count on a single file would race the mirror "
              "split across shards; pre-split with 'mirror --split-dir' "
              "and shard over that directory instead.", file=sys.stderr)
        return 2

    if args.merge_shards:
        print(f"Merging {args.shard_count} shard indexes for {base_name}...", flush=True)
        index = _merge_shard_indexes(target_dir, base_name, args.shard_count)
        index_file = target_dir / f".{base_name}_distill_index.json"
        tmp_index = index_file.with_suffix('.json.tmp')
        with open(tmp_index, 'w') as out:
            json.dump(index, out)
        os.replace(tmp_index, index_file)
        print(f"Merged: {len(index['unique_units'])} unique units from "
              f"{len(index['files_processed'])} files.", flush=True)
        pending = []  # Stage 1 already done per-shard; fall through to Stage 3
    else:
        if args.shard_count > 1:
            index_file = _shard_index_path(target_dir, base_name, args.shard_index)
            files = [f for f in files if _shard_owns(f, args.shard_index, args.shard_count)]
        else:
            index_file = target_dir / f".{base_name}_distill_index.json"

        index = {"files_processed": [], "unique_units": {}}
        if args.resume and index_file.exists():
            try:
                with open(index_file) as f:
                    index = json.load(f)
            except Exception as e:
                print(f"WARN: Could not load index ({e}), starting fresh.", file=sys.stderr)

        index.setdefault("unique_units", {})
        index.setdefault("files_processed", [])

        pending = [f for f in files if str(f) not in index["files_processed"]]
        print(f"Total files: {len(files)} | Processed: {len(index['files_processed'])} | Pending: {len(pending)}"
              + (f" | shard {args.shard_index}/{args.shard_count}" if args.shard_count > 1 else ""))

    preview_path = target_dir / f"{base_name}_live_preview.md"
    
    count = 0
    save_interval = 50
    
    # STAGE 1: Exact Hash Funnel
    preview_out = open(preview_path, "a")  # one handle for the run, not one per statement
    try:
        for f in pending:
            count += 1
            print(f"[{count}/{len(pending)}] Extracting: {f}", flush=True)
            # Read + extract FULLY before touching the shared index, so a
            # mid-file failure can't half-merge statements that a --resume
            # rerun would then double-count.
            try:
                raw = f.read_text(errors='ignore')
                if args.fast_clean:
                    stmts = clean_and_split(raw)
                else:
                    stmts = [s.strip() for s in raw.splitlines() if len(s.strip()) > 20]
                staged = [(hashlib.md5(get_canonical(s).encode()).hexdigest(), s) for s in stmts]
            except Exception as e:
                print(f"WARN reading {f} failed: {e}", file=sys.stderr)
                continue

            for h, s in staged:
                if h in index["unique_units"]:
                    index["unique_units"][h]["count"] += 1
                    if str(f) not in index["unique_units"][h]["sources"]:
                        index["unique_units"][h]["sources"].append(str(f))
                else:
                    index["unique_units"][h] = {
                        "text": s,
                        "count": 1,
                        "sources": [str(f)],
                        "cat": categorize(s)
                    }
                    preview_out.write(f"- {s} ({f.name})\n")

            index["files_processed"].append(str(f))

            if count % save_interval == 0:
                preview_out.flush()
                tmp_index = index_file.with_suffix('.json.tmp')
                with open(tmp_index, 'w') as out: json.dump(index, out)
                os.replace(tmp_index, index_file)
    finally:
        preview_out.close()
            
    tmp_index = index_file.with_suffix('.json.tmp')
    with open(tmp_index, 'w') as out: json.dump(index, out)
    os.replace(tmp_index, index_file)

    unique_list = list(index["unique_units"].values())
    print(f"\nStage 1 Complete: {len(unique_list)} exact-unique units.")

    if args.shard_count > 1 and not args.merge_shards:
        # This shard's slice of Stage 1 is done. Semantic clustering needs
        # every shard's units in one place -- run '--merge-shards' once, after
        # every shard here has finished, to do Stage 2/3 on the combined set.
        print(f"Shard {args.shard_index}/{args.shard_count} done -- "
              f"run --merge-shards once all shards finish.", flush=True)
        return 0

    # STAGE 2: Removed O(N^2) Jaccard. We rely on Exact Match + Semantic.
    lexical_clusters = []
    for u in unique_list:
        c = dict(u)
        c["items"] = [u]
        c["_words"] = set(get_canonical(u["text"]).split())
        lexical_clusters.append(c)
    print(f"Skipping Stage 2 Lexical Jaccard (too slow for 1.4M items). Passing {len(lexical_clusters)} clusters to Stage 3.", flush=True)
    
    out_md = target_dir / f"{base_name}_master.md"
    
    # STAGE 3: Semantic Embed & Dedup
    if args.semantic:
        print("\nStarting Stage 3: Semantic Dedup & Sort...")
        texts_to_embed = [c["text"] for c in lexical_clusters if "vector" not in c]
        if texts_to_embed:
            print(f"Embedding {len(texts_to_embed)} representatives...")
            
            # Chunk embeddings to avoid Ollama timeouts on massive lists.
            # Chunks round-robin across every host in OLLAMA_URLS (set via
            # OLLAMA_HOSTS, comma-separated) and run concurrently -- a single
            # host serializes every chunk behind its `-np 1` concurrency, so
            # spreading across N hosts cuts wall time roughly Nx.
            chunk_size = 100
            chunks = [texts_to_embed[i:i + chunk_size] for i in range(0, len(texts_to_embed), chunk_size)]
            results: list[list[list[float]] | None] = [None] * len(chunks)

            def _embed_one(idx: int, chunk: list[str]) -> None:
                host = OLLAMA_URLS[idx % len(OLLAMA_URLS)]
                try:
                    embs = _ollama_embed(chunk, args.model, host=host)
                    results[idx] = embs if embs else [None] * len(chunk)
                except Exception as e:
                    print(f"WARN: Embedding chunk {idx} on {host} failed ({e}), skipping chunk.", file=sys.stderr)
                    results[idx] = [None] * len(chunk)

            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(OLLAMA_URLS))) as ex:
                list(ex.map(lambda a: _embed_one(*a), enumerate(chunks)))

            all_embs = [v for chunk_res in results for v in chunk_res]
                    
            if all_embs:
                for c, v in zip([x for x in lexical_clusters if "vector" not in x], all_embs):
                    if v is not None:
                        c["vector"] = v
                        c["magnitude"] = precompute_magnitude(v)
                    
        semantic_clusters = []
        unembedded = []
        for c in lexical_clusters:
            vec = c.get("vector")
            mag = c.get("magnitude", 0.0)
            if not vec or mag == 0.0:
                # Embedding failed for this unit (chunk error) — keep it as its
                # own cluster; a transient Ollama hiccup must never silently
                # delete extracted content from the master.
                unembedded.append(dict(c))
                continue
            
            placed = False
            for sc in semantic_clusters:
                dot = sum(a * b for a, b in zip(vec, sc["centroid"]))
                sim = dot / (mag * sc["centroid_mag"]) if mag and sc["centroid_mag"] else 0.0
                if sim > args.threshold:
                    sc["items"].extend(c["items"])
                    sc["count"] += c["count"]
                    sc["sources"].extend(c["sources"])
                    sc["sources"] = list(set(sc["sources"]))
                    placed = True
                    break
            if not placed:
                sc = dict(c)
                sc["centroid"] = vec
                sc["centroid_mag"] = mag
                semantic_clusters.append(sc)
                
        if unembedded:
            print(f"WARN: {len(unembedded)} units kept unclustered (embedding failed for their chunks)", file=sys.stderr)
            semantic_clusters.extend(unembedded)
        semantic_clusters.sort(key=lambda x: x["count"], reverse=True)
        
        with open(out_md, 'w') as f:
            f.write("# Semantic Distillation Master (3-Stage Funnel)\n\n")
            for cat in ["Actionables", "Questions", "Statements"]:
                cat_clusters = [c for c in semantic_clusters if c["cat"] == cat]
                if not cat_clusters: continue
                f.write(f"## {cat}\n\n")
                for c in cat_clusters:
                    sources = [Path(s).name for s in c["sources"]]
                    src_str = ", ".join(sources[:3]) + ("..." if len(sources) > 3 else "")
                    dup_str = f" [x{c['count']}]" if c['count'] > 1 else ""
                    f.write(f"- {c['text']} _{src_str}_{dup_str}\n")
                f.write("\n")
        print(f"Done. Funneled {len(unique_list)} units into {len(semantic_clusters)} semantic points.")
    else:
        lexical_clusters.sort(key=lambda x: x["count"], reverse=True)
        with open(out_md, 'w') as f:
            f.write("# Bulk Distillation Master (2-Stage Lexical Funnel)\n\n")
            for c in lexical_clusters:
                sources = [Path(s).name for s in c["sources"]]
                src_str = ", ".join(sources[:3]) + ("..." if len(sources) > 3 else "")
                dup_str = f" [x{c['count']}]" if c['count'] > 1 else ""
                f.write(f"- {c['text']} _{src_str}_{dup_str}\n")
        print(f"Done. Extracted {len(lexical_clusters)} unique points.")

    print(f"Master file: {out_md}")
    return 0

def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Offline engine for /distill-offline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Tooltips for 'bulk':
--------------------
The 'bulk' subcommand processes entire directories of files to extract knowledge.
It implements the offline feature pipeline we've built, including:
  --recursive    Walk all subdirectories to find files.
  --resume       Save progress to a .bulk_distill_index.json file. If interrupted,
                 running the command again will pick up exactly where it left off.
  --fast-clean   Converts HTML -> Markdown, strips filler words, greetings,
                 URLs, and extremely short lines to get raw files down to size.
  --semantic     Calls Ollama to embed every extracted statement. Clusters and
                 deduplicates semantic matches across all files, sorting the
                 most frequently corroborated statements to the top.

Examples:
  distill_offline.py bulk ./wiki --recursive --resume --fast-clean --semantic
  distill_offline.py bulk ./wiki --no-semantic --no-resume  (lexical-only quick pass, no network)
"""
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bulk", help="bulk process a folder (or one mirror file): clean, extract, index, and dedup")
    b.add_argument("dir", help="target directory (or single mirror/doc file) to process")
    b.add_argument("--recursive", action=argparse.BooleanOptionalAction, default=True,
                   help="scan subdirectories recursively (default on; --no-recursive for top level only)")
    b.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True,
                   help="save/load state to resume on interrupt (default on)")
    b.add_argument("--fast-clean", action=argparse.BooleanOptionalAction, default=True,
                   help="strip HTML, filler words, greetings, normalize text (default on)")
    b.add_argument("--semantic", action=argparse.BooleanOptionalAction, default=True,
                   help="Ollama embeddings for cluster+dedup (default on; --no-semantic = lexical only, no network)")
    b.add_argument("--threshold", type=float, default=0.88, help="cosine similarity threshold for semantic dedup (default: 0.88)")
    b.add_argument("--model", default=DEFAULT_EMBED_MODEL, help="ollama embedding model")
    b.add_argument("--shard-index", type=int, default=0,
                   help="this process's shard number, 0-based (default: 0, unsharded)")
    b.add_argument("--shard-count", type=int, default=1,
                   help="total shards splitting Stage 1 across boxes (default: 1)")
    b.add_argument("--merge-shards", action="store_true",
                   help="skip Stage 1; merge every shard's index and run Stage 2/3 once "
                        "(run after all --shard-index workers finish)")
    b.set_defaults(func=cmd_bulk)

    r = sub.add_parser("render", help="compact units JSON -> md+json files")
    r.add_argument("--in", dest="in_file", default="-",
                   help="units JSON file, or - for stdin")
    r.add_argument("--slug", help="override output slug")
    r.add_argument("--json-only", action="store_true", help="skip markdown")
    r.set_defaults(func=cmd_render)

    d = sub.add_parser("diff", help="old+new files -> added/removed hunks JSON")
    d.add_argument("--old", required=True)
    d.add_argument("--new", required=True)
    d.set_defaults(func=cmd_diff)

    m = sub.add_parser("merge", help="dedup new units against existing set")
    m.add_argument("--existing", required=True, help="existing distillation JSON")
    m.add_argument("--new-units", dest="new_units", default="-",
                   help="new units JSON, or - for stdin")
    m.add_argument("--threshold", type=float, default=0.82,
                   help="near-duplicate ratio 0-1 (lexical ~0.82; "
                        "with --semantic try ~0.90)")
    m.add_argument("--semantic", action="store_true",
                   help="use ollama embeddings for dedup (catches rewordings)")
    m.add_argument("--model", default=DEFAULT_EMBED_MODEL,
                   help="ollama embedding model")
    m.set_defaults(func=cmd_merge)

    ix = sub.add_parser("index", help="embed a distillation's units -> vector index")
    ix.add_argument("--in", dest="in_file", default="-",
                    help="distillation JSON, or - for stdin")
    ix.add_argument("--name", help="index name (defaults to source slug)")
    ix.add_argument("--model", default=DEFAULT_EMBED_MODEL,
                    help="ollama embedding model")
    ix.set_defaults(func=cmd_index)

    nv = sub.add_parser("novelty",
                         help="drop candidates already covered by prior indexes")
    nv.add_argument("--in", dest="in_file", default="-",
                    help="candidate units/hunks JSON, or - for stdin")
    nv.add_argument("--against", nargs="*",
                    help="index names to compare against (default: all)")
    nv.add_argument("--threshold", type=float, default=0.90,
                    help="cosine/ratio above which a candidate is NOT novel")
    nv.add_argument("--model", default=DEFAULT_EMBED_MODEL,
                    help="ollama embedding model")
    nv.set_defaults(func=cmd_novelty)

    f = sub.add_parser("fetch", help="URL -> plain text (offline)")
    f.add_argument("--url", required=True)
    f.add_argument("--timeout", type=int, default=30)
    f.set_defaults(func=cmd_fetch)

    cl = sub.add_parser("clean",
                        help="local HTML file -> page text only (drop tags/CSS/JS)")
    cl.add_argument("--in", dest="in_file", default="-",
                    help="file to strip, or - for stdin")
    cl.add_argument("--force-html", action="store_true",
                    help="strip as HTML even if not auto-detected")
    cl.set_defaults(func=cmd_clean)

    e = sub.add_parser("extract", help="text -> HEURISTIC candidate units (degraded)")
    e.add_argument("--in", dest="in_file", default="-",
                   help="text file, or - for stdin")
    e.set_defaults(func=cmd_extract)

    mr = sub.add_parser("mirror",
                        help="web-text-mirror docset: stats/list/split/extract with per-page URL provenance")
    mr.add_argument("--in", dest="in_file", default="-",
                    help="mirror .md file (required in practice; - for stdin)")
    mr.add_argument("--list", action="store_true", help="print one page URL per line")
    mr.add_argument("--split-dir", dest="split_dir",
                    help="write one .md per page into this directory (for bulk)")
    mr.add_argument("--extract", action="store_true",
                    help="heuristic units across all pages, source_anchor = page URL")
    mr.set_defaults(func=cmd_mirror)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        # OSError covers FileNotFound/IsADirectory/Permission/FileExists —
        # any bad --in/--old/--new path fails with a clean ERROR, not a traceback.
        print(f"ERROR {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
