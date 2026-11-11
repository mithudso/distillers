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

Lexical modes use only the stdlib. Semantic modes use the optional shared
ollama-client library. Read the skill for how the LLM pass hands off here.
"""

from __future__ import annotations

import argparse
import concurrent.futures
from contextlib import contextmanager
import datetime as _dt
import difflib
import html
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

DIST_DIR = Path.home() / ".claude" / "distillations"
INDEX_DIR = DIST_DIR / ".index"

# Ollama is used ONLY as an offline semantic layer (dedup + novelty filtering).
# It never reads or generates prose — embeddings only — so it adds no LLM tokens.
# Transport (weighted pool, failover, retry, batching, pull) lives in the shared
# `ollama-client` library; this file keeps only the env mapping below.
try:
    from ollama_client import OllamaClient, OllamaPool, OllamaUnavailable, cosine as _cosine
    _HAVE_OLLAMA_CLIENT = True
except ImportError:  # keep the lexical-fallback contract when the library is absent
    _HAVE_OLLAMA_CLIENT = False

    class OllamaUnavailable(RuntimeError):  # type: ignore[no-redef]
        pass

    def _cosine(a, b):  # type: ignore[no-redef]
        raise OllamaUnavailable("ollama-client is not installed (pip install ollama-client)")

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
# Optional multi-host pool (OLLAMA_HOSTS, comma-separated; `url=weight` allowed).
# Falls back to the single OLLAMA_HOST. Chunks of the merge stage's Stage-3
# embedding run concurrently, one worker per host, with per-host failover.
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


def _safe_filename_part(value: str, field: str) -> str:
    """Reject path syntax in values used to construct output filenames."""
    if (not isinstance(value, str) or not value or value in (".", "..")
            or "/" in value or "\\" in value or "\x00" in value):
        raise ValueError(f"{field} must be a nonempty filename component")
    return value


@contextmanager
def _atomic_text_writer(path: Path):
    """Replace one artifact only after its complete UTF-8 contents are written."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as out:
            tmp_path = Path(out.name)
            yield out
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _atomic_write_text(path: Path, text: str) -> None:
    with _atomic_text_writer(path) as out:
        out.write(text)


def _atomic_write_json(path: Path, data: dict | list) -> None:
    with _atomic_text_writer(path) as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
        out.write("\n")


def _unit_anchors(unit: dict) -> list[str]:
    """Return every retained source anchor, in stable first-seen order."""
    return list(dict.fromkeys(a for a in [unit.get("source_anchor"),
                                        *(unit.get("source_anchors") or [])] if a))


# --------------------------------------------------------------------------- #
# render — the emit phase (the main token win: model never writes markdown)
# --------------------------------------------------------------------------- #

def _unit_salience(u: dict) -> int:
    return SALIENCE_RANK.get((u.get("salience") or "medium").lower(), 1)


def _render_unit_line(u: dict) -> str:
    t = u.get("type", "statement")
    text = u.get("text", "").strip()
    anchors = _unit_anchors(u)
    sal = (u.get("salience") or "").lower()
    anchor_md = ", ".join(f"_{anchor}_" for anchor in anchors)

    if t == "quote":
        attr = u.get("attribution")
        q = f'> "{text}"'
        if attr:
            q += f" — {attr}"
        if anchors:
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

    if anchors:
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
            anchors = _unit_anchors(u)
            when = u.get("removed_on") or generated
            anchor_md = " — " + ", ".join(f"_{anchor}_" for anchor in anchors) if anchors else ""
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
    _safe_filename_part(slug, "slug")
    _safe_filename_part(generated, "generated")
    markdown = None if json_only else render_markdown(data)
    stem_dir.mkdir(parents=True, exist_ok=True)
    written = []
    json_path = stem_dir / f"{slug}-{generated}.json"
    _atomic_write_json(json_path, data)
    written.append(str(json_path))
    if not json_only:
        md_path = stem_dir / f"{slug}-{generated}.md"
        _atomic_write_text(md_path, markdown)
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
            _validate_vectors(sem_targets + sem_cands, len(targets) + len(new_units))
        except OllamaUnavailable as e:
            print(f"WARN {e}; semantic dedup off, using lexical.", file=sys.stderr)
            sem_targets = sem_cands = None

    nid = _next_id(base)
    folded = 0
    kept = 0
    today = _today()
    for ci, nu in enumerate(new_units):
        ntext = _norm(nu.get("text", ""))
        best, best_ratio = None, -math.inf
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
            anchors = list(dict.fromkeys(_unit_anchors(best) + _unit_anchors(nu)))
            if anchors:
                best.setdefault("source_anchor", anchors[0])
                best["source_anchors"] = anchors
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
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_tags: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            if tag not in self._VOID:
                self._skip_tags.append(tag)
        elif not self._skip_tags and tag in self._BREAK:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            index = len(self._skip_tags) - 1 - self._skip_tags[::-1].index(tag)
            del self._skip_tags[index:]
        elif not self._skip_tags and tag in self._BREAK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_tags:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
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
    """Extract visible page text with the stdlib, without optional dependencies."""
    parser = _TextExtractor()
    parser.feed(body)
    parser.close()
    return parser.text()


def cmd_fetch(args) -> int:
    if not re.match(r"^https?://", args.url):
        print("ERROR fetch: only http(s) URLs are allowed", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("ERROR fetch: --timeout must be positive", file=sys.stderr)
        return 2
    try:
        out = subprocess.run(
            # --proto pins curl to http(s) even on redirects (no file:// etc.)
            ["curl", "-fsSL", "--proto", "=http,https", "--max-time", str(args.timeout), args.url],
            capture_output=True, text=True, check=True, timeout=args.timeout + 5,
        )
    except subprocess.CalledProcessError as e:
        print(f"ERROR fetch failed: curl exited with status {e.returncode}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print("ERROR fetch failed: request timed out", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print("ERROR fetch failed: curl is not installed", file=sys.stderr)
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
_MIRROR_OWNED_FILE_RE = re.compile(r"\d+_[\w-]+\.md\Z")


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
    if out_dir.is_symlink():
        raise ValueError("mirror output directory must not be a symlink")
    # Clear stale page files from a previous split (a shrunk/reordered mirror
    # would otherwise contaminate a later bulk run) — but only files THIS tool
    # wrote, tracked in a manifest. Numbered .md files are a common personal
    # note convention; never delete files we can't prove are ours.
    manifest_path = out_dir / ".mirror_split_manifest.json"
    ours = set()
    if manifest_path.is_symlink():
        raise ValueError("mirror split manifest must not be a symlink")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (not isinstance(manifest, list)
                or any(not isinstance(name, str) or not _MIRROR_OWNED_FILE_RE.fullmatch(name)
                       for name in manifest)):
            raise ValueError("mirror split manifest must list generated page basenames only")
        ours = set(manifest)
    strays = [p.name for p in out_dir.glob("*.md")
              if _MIRROR_PAGE_FILE_RE.match(p.name) and p.name not in ours]
    if strays:
        raise ValueError(
            f"{out_dir} already contains {len(strays)} numbered .md file(s) not "
            f"written by a previous split (e.g. {strays[0]!r}) — refusing to "
            "overwrite them; use an empty/dedicated --split-dir")
    planned = [(f"{n:03d}_{_page_slug(pg['url'])}.md", pg)
               for n, pg in enumerate(pages, start=1)]
    for name in ours | {name for name, _ in planned}:
        path = out_dir / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("mirror page targets must be regular files, not symlinks or directories")
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for fname, pg in planned:
        _atomic_write_text(out_dir / fname, f"URL: {pg['url']}\n\n{pg['text']}\n")
        written.append(fname)
    for name in ours:
        if name not in written:
            (out_dir / name).unlink(missing_ok=True)
    _atomic_write_json(manifest_path, written)
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

_CLIENT = None


def _client(host: str | None = None, workers: int = 1):
    """Pool-backed client: OLLAMA_HOSTS (else OLLAMA_HOST) weighted pool, or one explicit host."""
    global _CLIENT
    if not _HAVE_OLLAMA_CLIENT:
        raise OllamaUnavailable("ollama-client is not installed (pip install ollama-client)")
    if host is not None:
        return OllamaClient(OllamaPool([host]), embed_model=DEFAULT_EMBED_MODEL)
    if workers > 1:
        return OllamaClient(OllamaPool(OLLAMA_URLS), embed_model=DEFAULT_EMBED_MODEL, workers=workers)
    if _CLIENT is None:
        _CLIENT = OllamaClient(OllamaPool(OLLAMA_URLS), embed_model=DEFAULT_EMBED_MODEL)
    return _CLIENT


def _validate_vectors(vectors, count: int, dimension: int | None = None) -> list[list[float]]:
    """Fail closed on partial, nonnumeric or incompatible embedding batches."""
    if not isinstance(vectors, list) or len(vectors) != count:
        raise OllamaUnavailable("embedding response count does not match input count")
    for vector in vectors:
        if not isinstance(vector, list) or not vector:
            raise OllamaUnavailable("embedding response contains an empty or invalid vector")
        if dimension is None:
            dimension = len(vector)
        if len(vector) != dimension:
            raise OllamaUnavailable("embedding response contains incompatible vector dimensions")
        try:
            valid_numbers = all(not isinstance(value, bool) and isinstance(value, (int, float))
                                and math.isfinite(value) for value in vector)
            valid_magnitude = valid_numbers and math.isfinite(sum(value * value for value in vector))
        except (OverflowError, ValueError, TypeError):
            valid_magnitude = False
        if not valid_magnitude:
            raise OllamaUnavailable("embedding response contains non-finite or nonnumeric values")
    return vectors


def _ollama_embed(texts: list[str], model: str, host: str | None = None) -> list[list[float]]:
    """Batch-embed with validated alignment; translate failures for lexical fallback."""
    if not texts:
        return []
    try:
        client = _client(host)
        try:
            vectors = client.embed(texts, model=model)
        except OllamaUnavailable as first:
            # Pull only when a reachable host lacks the requested model.
            if not client.available() or _has_model(client, model):
                raise
            print(f"Model '{model}' missing. Pulling now (this may take a minute)...", file=sys.stderr)
            try:
                client.ensure_model(model)
            except OllamaUnavailable as pull_err:
                raise OllamaUnavailable(f"ollama pull '{model}' failed: {pull_err}") from pull_err
            try:
                vectors = client.embed(texts, model=model)
            except OllamaUnavailable as retry_err:
                raise OllamaUnavailable(f"ollama embed failed after pull: {retry_err}") from first
        return _validate_vectors(vectors, len(texts))
    except OllamaUnavailable:
        raise
    except Exception as error:
        raise OllamaUnavailable("embedding request failed") from error


def _has_model(client, model: str) -> bool:
    try:
        have = client.list_models()
    except OllamaUnavailable:
        return True  # cannot tell; do not attempt a pull
    want = model if ":" in model else f"{model}:latest"
    return any(h == model or h == want for h in have)


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
        _validate_vectors(vectors, len(units))
    except OllamaUnavailable as e:
        print(f"ERROR {e}; index needs ollama running.", file=sys.stderr)
        return 2

    entries = [
        {"id": u.get("id"), "text": u["text"], "type": u.get("type"),
         "source": src.get("ref") or src.get("url") or src.get("path"),
         "source_anchor": u.get("source_anchor"),
         "source_anchors": _unit_anchors(u), "vector": v}
        for u, v in zip(units, vectors)
    ]
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    path = _index_path(name)
    _atomic_write_json(path, {"model": args.model, "source": src,
                             "generated": _today(), "entries": entries})
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
        data = json.loads(p.read_text(encoding="utf-8"))
        out.extend(dict(entry, _index_model=data.get("model"))
                   for entry in data.get("entries", []))
    return out


def _model_identity(model: str | None) -> str | None:
    return model.removesuffix(":latest") if isinstance(model, str) else None


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
    index_norms = [_norm(text) for text in index_texts]
    semantic = True
    try:
        if any(_model_identity(e.get("_index_model")) != _model_identity(args.model)
               for e in index):
            raise OllamaUnavailable("prior index uses an incompatible or unknown embedding model")
        cand_vecs = _ollama_embed(cand_texts, args.model)
        _validate_vectors(cand_vecs, len(cand))
        idx_vecs = [e.get("vector") for e in index]
        _validate_vectors(idx_vecs, len(index), len(cand_vecs[0]) if cand_vecs else None)
    except OllamaUnavailable as e:
        print(f"WARN {e}; falling back to lexical novelty.", file=sys.stderr)
        semantic = False

    novel, matched = [], []
    for i, c in enumerate(cand):
        best_sim, best_j = -math.inf, -1
        if semantic:
            for j, iv in enumerate(idx_vecs):
                s = _cosine(cand_vecs[i], iv)
                if s > best_sim:
                    best_sim, best_j = s, j
        else:
            ci_norm = _norm(cand_texts[i])
            for j, it in enumerate(index_norms):
                sm = difflib.SequenceMatcher(a=ci_norm, b=it, autojunk=False)
                # Upper-bound prune: a sub-threshold pair can never count as
                # matched, so skipping it cannot change the novel/matched split.
                if sm.real_quick_ratio() < args.threshold:
                    continue
                s = sm.ratio()
                if s > best_sim:
                    best_sim, best_j = s, j
        if best_j >= 0 and best_sim >= args.threshold:
            matched.append({"candidate": c.get("text"), "similarity": round(best_sim, 3),
                            "matched_id": index[best_j].get("id"),
                            "matched_text": index[best_j].get("text"),
                            "source": index[best_j].get("source"),
                            "source_anchor": index[best_j].get("source_anchor"),
                            "source_anchors": _unit_anchors(index[best_j]),
                            "candidate_source_anchor": c.get("source_anchor"),
                            "candidate_source_anchors": _unit_anchors(c)})
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


def clean_and_split(raw, *, html_cleaned=False):
    if not html_cleaned:
        raw = _html_to_text(raw) if _looks_like_html(raw) else html.unescape(raw)
    raw = re.sub(r'http[s]?://\S+', '', raw)
    raw = re.sub(r'^(?:hi|hello|hey|welcome|dear|greetings|sincerely|best regards|cheers|thanks|thank you)\b.*$', '', raw, flags=re.IGNORECASE | re.MULTILINE)
    
    # Keep punctuation: decimal points and operators carry source meaning.
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
    text = unicodedata.normalize("NFC", text).lower()
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


_BULK_CACHE_VERSION = 2


def _bulk_fingerprints(files: list[Path]) -> dict[str, str]:
    fingerprints = {}
    for path in files:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        fingerprints[str(path)] = digest.hexdigest()
    return fingerprints


def _new_bulk_index(fingerprints: dict[str, str], fast_clean: bool) -> dict:
    return {"cache_version": _BULK_CACHE_VERSION,
            "input_fingerprints": fingerprints,
            "settings": {"fast_clean": fast_clean},
            "files_processed": [], "unique_units": {}}


def _valid_bulk_index(index) -> bool:
    """Treat corrupt or older checkpoints as invalid, before using their units."""
    if (not isinstance(index, dict) or index.get("cache_version") != _BULK_CACHE_VERSION
            or not isinstance(index.get("input_fingerprints"), dict)
            or not isinstance(index.get("files_processed"), list)
            or not isinstance(index.get("unique_units"), dict)
            or not isinstance(index.get("settings"), dict)
            or set(index["settings"]) != {"fast_clean"}
            or not isinstance(index["settings"]["fast_clean"], bool)):
        return False
    if (any(not isinstance(path, str) or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            for path, digest in index["input_fingerprints"].items())
            or any(not isinstance(path, str) for path in index["files_processed"])
            or len(set(index["files_processed"])) != len(index["files_processed"])
            or not set(index["files_processed"]).issubset(index["input_fingerprints"])):
        return False
    for unit in index["unique_units"].values():
        if (not isinstance(unit, dict) or not isinstance(unit.get("text"), str)
                or isinstance(unit.get("count"), bool) or not isinstance(unit.get("count"), int)
                or unit["count"] < 1 or unit.get("cat") not in ("Actionables", "Questions", "Statements")
                or not isinstance(unit.get("source_anchor"), str)
                or not isinstance(unit.get("sources"), list)
                or any(not isinstance(source, str) for source in unit["sources"])
                or not isinstance(unit.get("source_anchors"), list)
                or any(not isinstance(anchor, str) for anchor in unit["source_anchors"])):
            return False
    return True


def _bulk_cache_matches(index: dict, fingerprints: dict[str, str], fast_clean: bool) -> bool:
    return (_valid_bulk_index(index)
            and index.get("input_fingerprints") == fingerprints
            and index.get("settings") == {"fast_clean": fast_clean})


def _bulk_extract(raw: str, path: Path, fast_clean: bool) -> list[tuple[str, str]]:
    """Extract statements with page-local anchors, including already-split pages."""
    pages = parse_mirror(raw)
    if not pages:
        lines = raw.splitlines()
        match = _MIRROR_URL_RE.fullmatch(lines[0]) if lines else None
        if match:
            # split_mirror_to_dir adds a URL header and one blank line.
            first_body = 2 if len(lines) > 1 and not lines[1].strip() else 1
            pages = [{"url": match.group(1), "text": "\n".join(lines[first_body:])}]
        else:
            pages = [{"url": str(path), "text": raw}]
    extracted = []
    for page in pages:
        body = page["text"]
        html_cleaned = fast_clean and _looks_like_html(body)
        if html_cleaned:
            body = _html_to_text(body)
        for line_number, line in enumerate(body.splitlines(), start=1):
            statements = clean_and_split(line, html_cleaned=html_cleaned) if fast_clean else [line.strip()]
            for statement in statements:
                if len(statement) > 20 and get_canonical(statement):
                    extracted.append((statement, f"{page['url']}#L{line_number}"))
    return extracted


def _merge_shard_indexes(target_dir: Path, base_name: str, shard_count: int) -> dict:
    """Load and validate every shard before assembling a complete aggregate."""
    shards = []
    for i in range(shard_count):
        shard_path = _shard_index_path(target_dir, base_name, i)
        if not shard_path.is_file():
            raise ValueError(f"shard {i} index is missing; finish every shard before merging")
        shard = json.loads(shard_path.read_text(encoding="utf-8"))
        if (not _valid_bulk_index(shard)
                or set(shard["files_processed"]) != set(shard["input_fingerprints"])):
            raise ValueError(f"shard {i} index is incomplete or incompatible; rerun that shard")
        if shards and shard.get("settings") != shards[0].get("settings"):
            raise ValueError("shard indexes use different cleaning settings")
        shards.append(shard)
    merged = _new_bulk_index({}, shards[0]["settings"]["fast_clean"])
    for shard in shards:
        if set(merged["input_fingerprints"]) & set(shard["input_fingerprints"]):
            raise ValueError("shard indexes contain overlapping input files")
        merged["input_fingerprints"].update(shard["input_fingerprints"])
        merged["files_processed"].extend(shard["files_processed"])
        for digest, unit in shard["unique_units"].items():
            if digest in merged["unique_units"]:
                existing = merged["unique_units"][digest]
                existing["count"] += unit["count"]
                existing["sources"] = list(dict.fromkeys(existing["sources"] + unit["sources"]))
                existing["source_anchors"] = list(dict.fromkeys(_unit_anchors(existing) + _unit_anchors(unit)))
            else:
                merged["unique_units"][digest] = unit
    return merged


def _bulk_source_label(unit: dict) -> str:
    anchors = _unit_anchors(unit)
    return ", ".join(anchors) if anchors else ", ".join(unit.get("sources", []))


@contextmanager
def _bulk_preview_writer(path: Path, reset: bool, existing_units):
    """Never follow preview symlinks or truncate a nonregular target."""
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("bulk preview must be a regular file, not a symlink or directory")
    if not hasattr(os, "O_NOFOLLOW"):
        # Platforms without a no-follow open rebuild the preview atomically from
        # the checkpoint, rather than reading/appending through the target path.
        with _atomic_text_writer(path) as out:
            if not reset:
                for unit in existing_units:
                    out.write(f"- {unit['text']} _{unit['source_anchor']}_\n")
            yield out
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
    flags |= getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("bulk preview must be a regular file")
        if reset:
            os.ftruncate(fd, 0)
        out = os.fdopen(fd, "a", encoding="utf-8")
        fd = None
        with out:
            yield out
    finally:
        if fd is not None:
            os.close(fd)


def _is_owned_bulk_output(path: Path) -> bool:
    """Recognize prior outputs without excluding user files by suffix alone."""
    if path.name.endswith("_master.md"):
        with path.open(encoding="utf-8", errors="replace") as source:
            header = source.readline(256).rstrip("\r\n")
        if header in {"# Semantic Distillation Master (3-Stage Funnel)",
                      "# Bulk Distillation Master (2-Stage Lexical Funnel)"}:
            return True
    preview = re.fullmatch(r"(.+)_live_preview(?:\.shard(\d+))?\.md", path.name)
    if preview:
        base_name, shard = preview.groups()
        cache = (_shard_index_path(path.parent, base_name, int(shard)) if shard is not None
                 else path.parent / f".{base_name}_distill_index.json")
        return cache.is_file() and not cache.is_symlink()
    return False


def cmd_bulk(args) -> int:
    if not (0.0 <= args.threshold <= 1.0):
        print(f"ERROR: --threshold must be in [0,1], got {args.threshold}", file=sys.stderr)
        return 2
    if args.shard_count < 1 or not (0 <= args.shard_index < args.shard_count):
        print("ERROR: --shard-count must be positive and --shard-index must be in range", file=sys.stderr)
        return 2
    if args.merge_shards and args.shard_count < 2:
        print("ERROR: --merge-shards requires --shard-count greater than one", file=sys.stderr)
        return 2
    target_path = Path(args.dir).expanduser()
    if not target_path.exists():
        print(f"ERROR: Path {target_path} does not exist.", file=sys.stderr)
        return 2
    # This check must precede the split: even a rejected worker must not clear
    # another worker's pages or create output artifacts.
    if args.shard_count > 1 and target_path.is_file():
        print("ERROR: --shard-count on a single file would race the mirror split; "
              "pre-split with 'mirror --split-dir' and shard the directory instead.", file=sys.stderr)
        return 2

    if target_path.is_file():
        raw = target_path.read_text(encoding="utf-8", errors="replace")
        mirror_pages = parse_mirror(raw)
        base_name = target_path.stem
        if mirror_pages:
            target_dir = target_path.parent / f"{target_path.stem}.pages"
            n = split_mirror_to_dir(raw, target_dir)
            print(f"Mirror docset detected ({docset_key(mirror_pages, target_path)}): "
                  f"split {n} pages into {target_dir}", flush=True)
            files = sorted(p for p in target_dir.glob("*.md")
                           if _MIRROR_PAGE_FILE_RE.match(p.name))
        else:
            target_dir, files = target_path.parent, [target_path]
    else:
        target_dir, base_name = target_path, target_path.resolve().name
        excluded = {f"{base_name}_master.md", f"{base_name}_live_preview.md"}
        print(f"Scanning directory {target_dir}...", flush=True)
        walker = target_dir.rglob("*") if args.recursive else target_dir.glob("*")
        files = sorted(p for p in walker if p.is_file() and p.suffix in {".html", ".md", ".txt"}
                       and p.name not in excluded
                       and not _is_owned_bulk_output(p)
                       and "Special_" not in p.name and "Special:" not in str(p))

    if args.shard_count > 1 and not args.merge_shards:
        files = [path for path in files if _shard_owns(path.relative_to(target_dir),
                                                    args.shard_index, args.shard_count)]
    fingerprints = _bulk_fingerprints(files)
    index_file = (_shard_index_path(target_dir, base_name, args.shard_index)
                  if args.shard_count > 1 and not args.merge_shards
                  else target_dir / f".{base_name}_distill_index.json")
    reset = True
    if args.merge_shards:
        index = _merge_shard_indexes(target_dir, base_name, args.shard_count)
        if not _bulk_cache_matches(index, fingerprints, args.fast_clean):
            raise ValueError("shard inputs or cleaning settings changed; rerun every shard before merging")
        pending = []
        print(f"Merged: {len(index['unique_units'])} unique units from {len(index['files_processed'])} files.")
    else:
        index = _new_bulk_index(fingerprints, args.fast_clean)
        if args.resume and index_file.exists():
            try:
                candidate = json.loads(index_file.read_text(encoding="utf-8"))
                if _bulk_cache_matches(candidate, fingerprints, args.fast_clean):
                    index, reset = candidate, False
                else:
                    print("WARN: bulk inputs, cleaning settings or cache format changed; rebuilding cache.", file=sys.stderr)
            except (OSError, ValueError, TypeError):
                print("WARN: bulk cache is unreadable or invalid; rebuilding cache.", file=sys.stderr)
        processed = set(index["files_processed"])
        pending = [path for path in files if str(path) not in processed]
        print(f"Total files: {len(files)} | Processed: {len(processed)} | Pending: {len(pending)}"
              + (f" | shard {args.shard_index}/{args.shard_count}" if args.shard_count > 1 else ""))

    preview_suffix = f".shard{args.shard_index}" if args.shard_count > 1 and not args.merge_shards else ""
    preview_path = target_dir / f"{base_name}_live_preview{preview_suffix}.md"
    # A fresh cache gets a fresh preview too. Shards never share a preview handle.
    if not args.merge_shards:
        with _bulk_preview_writer(preview_path, reset, index["unique_units"].values()) as preview:
            for count, path in enumerate(pending, start=1):
                print(f"[{count}/{len(pending)}] Extracting: {path}", flush=True)
                raw = path.read_text(encoding="utf-8", errors="replace")
                if hashlib.sha256(path.read_bytes()).hexdigest() != fingerprints[str(path)]:
                    raise ValueError("an input changed during bulk extraction; rerun the command")
                staged = [(hashlib.md5(get_canonical(statement).encode()).hexdigest(), statement, anchor)
                          for statement, anchor in _bulk_extract(raw, path, args.fast_clean)]
                for digest, statement, anchor in staged:
                    unit = index["unique_units"].get(digest)
                    if unit is not None:
                        unit["count"] += 1
                        if str(path) not in unit["sources"]:
                            unit["sources"].append(str(path))
                        if anchor not in unit["source_anchors"]:
                            unit["source_anchors"].append(anchor)
                    else:
                        index["unique_units"][digest] = {
                            "text": statement, "count": 1, "sources": [str(path)],
                            "source_anchor": anchor, "source_anchors": [anchor],
                            "cat": categorize(statement)}
                        preview.write(f"- {statement} _{anchor}_\n")
                index["files_processed"].append(str(path))
                if count % 50 == 0:
                    preview.flush()
                    _atomic_write_json(index_file, index)
    _atomic_write_json(index_file, index)
    unique_list = list(index["unique_units"].values())
    print(f"\nStage 1 Complete: {len(unique_list)} exact-unique units.")
    if args.shard_count > 1 and not args.merge_shards:
        print(f"Shard {args.shard_index}/{args.shard_count} done -- run --merge-shards once all shards finish.")
        return 0

    clusters = [dict(unit, items=[unit]) for unit in unique_list]
    print(f"Skipping Stage 2 Lexical Jaccard. Passing {len(clusters)} clusters to Stage 3.", flush=True)
    if args.semantic and clusters:
        print("\nStarting Stage 3: Semantic Dedup & Sort...")
        chunk_size = 100
        chunks = [clusters[i:i + chunk_size] for i in range(0, len(clusters), chunk_size)]
        results = [None] * len(chunks)

        def embed_chunk(item):
            number, chunk = item
            try:
                results[number] = _validate_vectors(_ollama_embed([unit["text"] for unit in chunk], args.model), len(chunk))
            except OllamaUnavailable:
                print(f"WARN: embedding chunk {number} unavailable; keeping its units unclustered.", file=sys.stderr)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(OLLAMA_URLS))) as executor:
            list(executor.map(embed_chunk, enumerate(chunks)))
        dimension = None
        for chunk, vectors in zip(chunks, results):
            if vectors is None:
                continue
            try:
                _validate_vectors(vectors, len(chunk), dimension)
            except OllamaUnavailable:
                print("WARN: embedding chunks use incompatible dimensions; keeping affected units unclustered.", file=sys.stderr)
                continue
            dimension = len(vectors[0])
            for unit, vector in zip(chunk, vectors):
                unit["vector"] = vector
                unit["magnitude"] = precompute_magnitude(vector)
        semantic_clusters, unembedded = [], []
        for unit in clusters:
            vector, magnitude = unit.get("vector"), unit.get("magnitude", 0.0)
            if not vector or magnitude == 0.0:
                unembedded.append(unit)
                continue
            for existing in semantic_clusters:
                similarity = sum(a * b for a, b in zip(vector, existing["centroid"])) / (magnitude * existing["centroid_mag"])
                if similarity > args.threshold:
                    existing["items"].extend(unit["items"])
                    existing["count"] += unit["count"]
                    existing["sources"] = list(dict.fromkeys(existing["sources"] + unit["sources"]))
                    existing["source_anchors"] = list(dict.fromkeys(_unit_anchors(existing) + _unit_anchors(unit)))
                    break
            else:
                semantic_clusters.append(dict(unit, centroid=vector, centroid_mag=magnitude))
        if unembedded:
            print(f"WARN: {len(unembedded)} units kept unclustered because embeddings are unavailable or zero.", file=sys.stderr)
        clusters = semantic_clusters + unembedded
    clusters.sort(key=lambda unit: unit["count"], reverse=True)
    out_md = target_dir / f"{base_name}_master.md"
    with _atomic_text_writer(out_md) as out:
        if args.semantic:
            out.write("# Semantic Distillation Master (3-Stage Funnel)\n\n")
            for category in ("Actionables", "Questions", "Statements"):
                group = [unit for unit in clusters if unit["cat"] == category]
                if not group:
                    continue
                out.write(f"## {category}\n\n")
                for unit in group:
                    duplicate = f" [x{unit['count']}]" if unit["count"] > 1 else ""
                    out.write(f"- {unit['text']} _{_bulk_source_label(unit)}_{duplicate}\n")
                out.write("\n")
        else:
            out.write("# Bulk Distillation Master (2-Stage Lexical Funnel)\n\n")
            for unit in clusters:
                duplicate = f" [x{unit['count']}]" if unit["count"] > 1 else ""
                out.write(f"- {unit['text']} _{_bulk_source_label(unit)}_{duplicate}\n")
    print(f"Done. Funneled {len(unique_list)} units into {len(clusters)} points.")
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
