# Code deep optimizer — 2026-11-11

Target: `mithudso/distillers`, baseline `cf8da39`, release 0.1.1. Profile: standard;
all 18 fix-track passes evaluated at their applicable file/repository scope.
No file cap truncated the census. The four frozen helpers received read-only
risk reviews and are excluded from the maintained-code convergence claim.
No advisory/feature mode, live embedding run or empirical champion was used:
there is no held-out optimization eval set.

## Severity and convergence

| Audit stage / scope | Critical | High | Medium |
| --- | ---: | ---: | ---: |
| Initial engine E1–E12 | 1 | 7 | 4 |
| Original test harness | 0 | 0 | 3 |
| Added tooling and its tests, before repair | 0 | 2 | 7 |
| First blind gate, including one tooling residual | 0 | 3 | 1 |
| Second blind gate | 0 | 1 | 0 |
| Post-gate targeted safety verification | No general re-audit | Resolved | No new finding |

Rows describe their named audit surface, not additive repository totals. Later
audits revisit earlier findings. Adjacent boundary hardening is grouped with the
corresponding issue family below. The first blind gate dissented; its reproduced
counterexamples became failing regression tests before the repair iteration.

## Findings and changes

Locations below name baseline lines for initial findings; final generated
inventories carry current symbol locations.

| Pass | Evidence | Severity | Finding / correction | Status |
| --- | --- | --- | --- | --- |
| S1/S3 | `distill_offline.py:684`, `split_mirror_to_dir` | Critical | Manifest traversal could delete a sibling. Validate ownership metadata and targets before mutation; reject filename traversal; atomically replace artifacts. | Fixed, regression tested |
| C2/M4 | `:1172`, `:1308`, `_bulk_extract` | High | Bulk discarded page URLs. Keep primary/all anchors through extraction, exact/semantic clustering, cache and master. | Fixed, regression tested |
| C2 | `:840`, `cmd_index` | High | Vector entries discarded `source_anchor`. Persist unit/source provenance and return anchors in novelty matches. | Fixed, regression tested |
| C1/C3 | `:1143`, `cmd_bulk` | High | Resume reused changed/deleted inputs. Version cache, fingerprint content and validate input set/settings/schema; rebuild visibly. | Fixed, regression tested |
| C1/C2 | `:855`, `cmd_novelty` | High | Model metadata was discarded. Validate model identity/dimensions and use lexical comparison for incompatible indexes. Select an actual best match at threshold zero. | Fixed, regression tested |
| C1/S2 | `:1048`, `_merge_shard_indexes` | High | Missing shards could replace complete output with partial data. Require all valid, complete, nonoverlapping, current shard inputs before writing. | Fixed, regression tested |
| P2/S3 | `:1084`, `cmd_bulk` | High | Rejected shard commands split before validation. Reject invalid arguments first; isolate shard previews and use relative shard ownership. | Fixed, regression tested |
| C1/S4 | `:468`, `_html_to_text` | High | HTML paths required undeclared trafilatura. Use stdlib HTMLParser; preserve inline spaces, void-tag behavior and single entity decoding. | Fixed, regression tested |
| C1/C2 | `:125`, `_render_unit_line` | Medium | Missing type raised despite promised fallback. Render unknown/missing types as statements without mutating input. | Fixed, regression tested |
| S3/C3 | `:840`, `:1250`, `_validate_vectors` | Medium | Partial/malformed vectors could truncate or misalign units. Validate count, finite numbers and dimensions; degrade safely. | Fixed, regression tested |
| P1 | `:1226`, `:906` | Medium | Unused per-unit word sets and repeated index normalization wasted work. Remove sets and precompute normalized references. | Fixed; no measured speedup claim |
| S2/T1/P2 | `tests/test_ollama_layer.py:59`, `:69` | Medium | Tests leaked environment, threads/sockets and required an absent optional dependency. Isolate module configuration, register cleanup and split core/optional integration coverage. | Fixed, both modes verified |
| S1/S5 | `cmd_fetch` | Critical | Subprocess error text could expose credential-bearing URL arguments. Emit bounded failure categories/status without argv or captured response diagnostics. | Fixed, redaction tested |
| C2/T1 | `_render_unit_line`, `render_markdown` | High | First blind gate found additional retained anchors missing from active/quote/removed Markdown. Render all retained anchors. | Repaired after failing tests |
| C1/C3 | `get_canonical`, `clean_and_split` | High | “Exact” normalization collapsed 1.2/12 and math operators. Preserve meaningful punctuation in keys and cleaned content. | Repaired after failing tests |
| C1/M3 | `cmd_bulk` input discovery | Medium | Directory runs ingested artifacts from other bulk basenames. Recognize provably generated masters/previews across runs. | Repaired after failing tests |
| S1/S3/M4 | `scripts/generate_repo_docs.py` | High / Medium | Untracked bodies, symlink targets and unchecked outputs could cross repository boundaries. Use staged/tracked census, read/write containment and link validation; include negative Boolean aliases. | Fixed, targeted regressions |
| C1/S2/P2/S3 | `scripts/rotate_workflow_logs.py` | High / Medium | Loose version parsing, stale swap checks, concurrent appends and archive symlinks could misplace/lose logs. Parse real headers outside fences, recheck swaps/changes, retain original inode and constrain archives. | Fixed, targeted regressions |
| S3/T1 | `tests/test_tooling.py` | Medium | Git overrides escaped fixtures; the symlink test did not prove no-read behavior. Clear Git overrides and guard private file opens. | Fixed, targeted regressions |

## Verification gate

| Command / surface | Baseline | Final |
| --- | --- | --- |
| `python3 -m py_compile distill_offline.py scripts/*.py` | Engine passed; tooling did not exist | Pass |
| `python3 -m unittest discover -s tests -v` | 1 passed, 4 errors without optional client | 56 tests: 52 pass, 4 explicit optional-client skips |
| Isolated `pip install '.[semantic]'` plus suite | Existing 5 client tests passed with local shared-client source | Package/extra built; all 56 tests pass including fake transport |
| `python3 scripts/generate_repo_docs.py --check` | No checker/indexes | Pass after regeneration |
| Known Aider `mirror --in` | 128 pages / 1,007,829 bytes / 250,711 estimated tokens | Same statistics |
| Disposable-copy Aider `bulk --no-semantic` | Historical counts were not a current baseline | 128 pages processed; all retained primary anchors point to Aider page URLs; no network |
| `git diff --check` | Clean | Pass |
| Python 3.11 / 3.14 × core / semantic CI | No workflow | Exact final-push results recorded in delivery PR |

The first 20 new engine tests reproduced 22 failing subcases and 5 errors before
fixes. The blind-review tests separately reproduced six failing subcases before
repair. Tests assert data, anchors, exit status, diagnostics and artifact safety;
there is no numeric line-coverage mandate. Python 3.15 can report upstream
HTTPError cleanup ResourceWarnings in deliberate client-error tests; they pass.

## Activated reviewers and pass ledger

`lang-python` covers the runtime/tests. `software-engineering-patterns` review and
coding-standard references cover contracts and maintainability. `security-review`
covers input/output confinement, credentials, dependency and privacy boundaries.
Repo-bootstrapper covers applicable docs/workflow/tooling and static inventories.
Memory-central: five convention rows were checked against current repository
instructions; no prior distillers lesson set existed. No regression check was
inferred from a stale sample count.

| Passes | Result / applicability |
| --- | --- |
| C1/C2/C3 | Runtime contracts and adversarial counterexamples executed in temporary fixtures. |
| S1/S2/S3/S4/S5 | File confinement, failures, resources, stdlib portability and observable diagnostics checked. No source-directed review instruction was found. |
| P1/P2 | Grounded allocation/normalization fixes and shard/test isolation; same-target unsharded concurrent writers remain unsupported. |
| M1/M2/M3/M4 | Importable canonical module retained; optional transport reused; configuration centralized at env/argparse boundaries; docs refreshed. No unsolicited module split/service was added. |
| T1/T2/T3/T4 | Meaningful behavioral tests, pinned optional dependency, CI and source inventories. Dependency review was static, not a live vulnerability attestation. Tests use no sleeps; in-process global output capture requires serial execution. T4 is N/A for production files. |

## Diff and independent review

The delivery PR contains the complete per-file unified diff. Its scope includes
the canonical engine, optional packaging, behavioral tests, Python maintenance
tooling and applicable bootstrap documentation/metadata. A machine-readable
[file completion receipt](audit/completion-files.json) records each changed file.
No diff is hidden behind a claimed full-repository CLEAN verdict.

### Capped per-file diff previews

Each preview is capped at 65 lines. The delivery PR contains the full diff.

#### `distill_offline.py`

```diff
diff --git a/distill_offline.py b/distill_offline.py
index 5897ad4..a1fe6a9 100755
--- a/distill_offline.py
+++ b/distill_offline.py
@@ -34,5 +34,6 @@ Subcommands:
   clean    local HTML/text file -> page text only (tags/CSS/JS stripped)

-All modes are stdlib-only. Read the skill for how the LLM pass hands off here.
+Lexical modes use only the stdlib. Semantic modes use the optional shared
+ollama-client library. Read the skill for how the LLM pass hands off here.
 """

@@ -41,13 +42,18 @@ from __future__ import annotations
 import argparse
 import concurrent.futures
+from contextlib import contextmanager
 import datetime as _dt
 import difflib
 import html
+import hashlib
 import json
 import math
 import os
 import re
+import stat
 import subprocess
 import sys
+import tempfile
+import unicodedata
 import urllib.error
 import urllib.request
@@ -115,4 +121,44 @@ def _slugify(text: str) -> str:


+def _safe_filename_part(value: str, field: str) -> str:
+    """Reject path syntax in values used to construct output filenames."""
+    if (not isinstance(value, str) or not value or value in (".", "..")
+            or "/" in value or "\\" in value or "\x00" in value):
+        raise ValueError(f"{field} must be a nonempty filename component")
+    return value
+
+
+@contextmanager
+def _atomic_text_writer(path: Path):
+    """Replace one artifact only after its complete UTF-8 contents are written."""
+    tmp_path = None
+    try:
+        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
+                                         prefix=f".{path.name}.", delete=False) as out:
+            tmp_path = Path(out.name)
+            yield out
+        os.replace(tmp_path, path)
+    finally:
+        if tmp_path is not None:
+            tmp_path.unlink(missing_ok=True)
+
+
+def _atomic_write_text(path: Path, text: str) -> None:
+    with _atomic_text_writer(path) as out:
+        out.write(text)
+
+
+def _atomic_write_json(path: Path, data: dict | list) -> None:
+    with _atomic_text_writer(path) as out:
+        json.dump(data, out, indent=2, ensure_ascii=False)
```

Truncated: 1033 additional diff lines; see the delivery PR.

#### `pyproject.toml`

```diff
diff --git a/pyproject.toml b/pyproject.toml
index c9c53cd..6ae23a8 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -5,9 +5,12 @@ build-backend = "setuptools.build_meta"
 [project]
 name = "distillers"
-version = "0.1.0"
+version = "0.1.1"
 description = "Offline document-distillation engine (zero LLM tokens); Ollama embeddings via the shared ollama-client library."
 requires-python = ">=3.11"
-dependencies = [
-    "ollama-client @ git+https://github.com/mithudso/ollama-client",
+dependencies = []
+
+[project.optional-dependencies]
+semantic = [
+    "ollama-client @ git+https://github.com/mithudso/ollama-client@740aca7cbc5aab4941779f35f1ca17b59fe73c7f",
 ]

```

#### `scripts/generate_repo_docs.py`

```diff
diff --git a/scripts/generate_repo_docs.py b/scripts/generate_repo_docs.py
new file mode 100644
index 0000000..71edb87
--- /dev/null
+++ b/scripts/generate_repo_docs.py
@@ -0,0 +1,232 @@
+#!/usr/bin/env python3
+"""Generate static file/CLI/operation inventories without imports or embeddings."""
+from __future__ import annotations
+
+import argparse
+import ast
+import json
+import os
+from pathlib import Path
+import re
+import subprocess
+import sys
+import tomllib
+
+ROOT = Path(__file__).resolve().parents[1]
+GENERATED = (
+    "docs/codebase-overview.md", "docs/high_signal_file_index.json",
+    "docs/llm-repo-index.json", "docs/tool-inventory.json",
+    "docs/operations-registry.json", "llms.txt", "llms-small.txt",
+    "llms-full.txt", "llms-facts.txt",
+)
+FROZEN = {"split_master.py", "categorize_topics.py", "clean_binary_garbage.py", "clean_index_garbage.py"}
+PURPOSES = {
+    "distill_offline.py": "Canonical document-distillation CLI and importable engine.",
+    "tests/test_core.py": "Dependency-free data safety, provenance and fallback regressions.",
+    "tests/test_ollama_layer.py": "Isolated configuration and optional loopback-client integration tests.",
+    "scripts/generate_repo_docs.py": "Static inventory generator and documentation drift gate.",
+    "scripts/rotate_workflow_logs.py": "Archive older workflow-log sections with editor-swap protection.",
+    "pyproject.toml": "Package version, Python requirement and optional semantic dependency pin.",
+    "Makefile": "Convenient stdlib verification and documentation targets.",
+    "KICKOFF.md": "Historical implementation brief; current guidance lives under docs/.",
+    "STATUS.md": "Historical downstream acceptance snapshot, not current integration evidence.",
+    "SUMMARY.md": "Historical build summary, not current runtime evidence.",
+}
+
+
+def census(root: Path) -> list[str]:
+    data = subprocess.check_output(
+        ["git", "ls-files", "--cached", "-z"], cwd=root,
+        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
+    )
+    names = {p.decode("utf-8") for p in data.split(b"\0") if p}
+    return sorted({n for n in names if (root / n).is_file() or (root / n).is_symlink()} | set(GENERATED))
+
+
+def role(path: str) -> str:
+    if path in FROZEN:
+        return "frozen-script"
+    if path in GENERATED:
+        return "generated"
+    if path.startswith("tests/"):
+        return "test"
+    if path.startswith("scripts/"):
+        return "tooling"
+    if path.startswith(".github/workflows/"):
+        return "infra"
+    if path == "distill_offline.py":
+        return "entrypoint"
+    if path.startswith("docs/") or path.endswith(".md"):
```

Truncated: 173 additional diff lines; see the delivery PR.

#### `scripts/rotate_workflow_logs.py`

```diff
diff --git a/scripts/rotate_workflow_logs.py b/scripts/rotate_workflow_logs.py
new file mode 100644
index 0000000..383df5a
--- /dev/null
+++ b/scripts/rotate_workflow_logs.py
@@ -0,0 +1,108 @@
+#!/usr/bin/env python3
+"""Archive older workflow-log sections; refuse while an editor swap file exists."""
+from __future__ import annotations
+
+import argparse
+from pathlib import Path
+import re
+import tempfile
+import os
+
+ROOT = Path(__file__).resolve().parents[1]
+LIMIT = 200_000
+
+
+def atomic_write(path: Path, text: str, before_replace=None) -> None:
+    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as out:
+        tmp = Path(out.name)
+        try:
+            out.write(text)
+            out.flush()
+            os.fsync(out.fileno())
+        except BaseException:
+            tmp.unlink(missing_ok=True)
+            raise
+    try:
+        if before_replace is not None:
+            before_replace()
+        os.replace(tmp, path)
+    finally:
+        tmp.unlink(missing_ok=True)
+
+
+def check_swaps(root: Path) -> None:
+    for name in ("memory.md", "prompts.md"):
+        if any(root.glob(f".{name}.sw?")) or any(root.glob(f"{name}.sw?")):
+            raise ValueError(f"refusing rotation: active editor swap for {name}")
+
+
+def version_starts(text: str) -> list[int]:
+    starts, offset, fence_char, fence_length = [], 0, None, 0
+    for line in text.splitlines(keepends=True):
+        fence = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
+        if fence:
+            marker = fence.group(1)
+            if fence_char is None:
+                fence_char, fence_length = marker[0], len(marker)
+            elif (marker[0] == fence_char and len(marker) >= fence_length
+                  and not line[fence.end():].strip()):
+                fence_char, fence_length = None, 0
+        elif fence_char is None and re.fullmatch(r"## (?:Prompt )?v\d+(?:\.\d+)*(?: -[^\n]*)?", line.rstrip("\r\n")):
+            starts.append(offset)
+        offset += len(line)
+    return starts
+
+
+def rotate(root: Path, limit: int = LIMIT) -> list[str]:
+    if limit <= 0:
+        raise ValueError("limit must be positive")
+    check_swaps(root)
```

Truncated: 49 additional diff lines; see the delivery PR.

#### `tests/test_core.py`

```diff
diff --git a/tests/test_core.py b/tests/test_core.py
new file mode 100644
index 0000000..629eb44
--- /dev/null
+++ b/tests/test_core.py
@@ -0,0 +1,405 @@
+"""Dependency-free regressions for data safety, provenance and lexical behavior."""
+from contextlib import redirect_stderr, redirect_stdout
+import io
+import json
+import os
+import subprocess
+from pathlib import Path
+import tempfile
+from types import SimpleNamespace
+import unittest
+from unittest.mock import patch
+
+import distill_offline as d
+
+
+def mirror(*pages):
+    return "\n".join(f"{'=' * 20}\nURL: {url}\n{'=' * 20}\n{text}" for url, text in pages)
+
+
+class CoreTests(unittest.TestCase):
+    def setUp(self):
+        self.tmp = tempfile.TemporaryDirectory()
+        self.addCleanup(self.tmp.cleanup)
+        self.root = Path(self.tmp.name)
+
+    def run_cli(self, *argv):
+        stdout, stderr = io.StringIO(), io.StringIO()
+        with redirect_stdout(stdout), redirect_stderr(stderr):
+            code = d.main(list(argv))
+        return code, stdout.getvalue(), stderr.getvalue()
+
+    def json_file(self, name, data):
+        p = self.root / name
+        p.write_text(json.dumps(data), encoding="utf-8")
+        return str(p)
+
+    def test_mirror_extract_retains_page_urls(self):
+        text = mirror(("https://example.test/one", "First source contains useful documented facts."),
+                      ("https://example.test/two", "Second source contains another useful statement."))
+        path = self.root / "mirror.md"
+        path.write_text(text)
+        code, output, _ = self.run_cli("mirror", "--in", str(path), "--extract")
+        self.assertEqual(code, 0)
+        units = json.loads(output)["units"]
+        self.assertEqual([u["source_anchor"] for u in units],
+                         ["https://example.test/one#L1", "https://example.test/two#L1"])
+
+    def test_manifest_traversal_refused_without_deletion(self):
+        victim = self.root / "victim.md"
+        victim.write_text("preserve me")
+        out = self.root / "pages"
+        out.mkdir()
+        (out / ".mirror_split_manifest.json").write_text('["../victim.md"]')
+        with self.assertRaises(ValueError):
+            d.split_mirror_to_dir(mirror(("https://example.test/a", "Documented source text.")), out)
+        self.assertEqual(victim.read_text(), "preserve me")
+        self.assertFalse(any(out.glob("[0-9]*.md")))
+
+    def test_manifest_shape_and_names_validated_before_writes(self):
```

Truncated: 346 additional diff lines; see the delivery PR.

#### `tests/test_ollama_layer.py`

```diff
diff --git a/tests/test_ollama_layer.py b/tests/test_ollama_layer.py
index 064e77a..d68e7c2 100644
--- a/tests/test_ollama_layer.py
+++ b/tests/test_ollama_layer.py
@@ -1,38 +1,66 @@
-"""Ollama layer of distill_offline.py (runs against an in-process fake Ollama).
+"""Configuration, lexical fallback, and optional Ollama transport tests.

-Run: .venv/bin/python -m unittest discover -s tests -v   (needs `pip install ollama-client`)
+Run: python3 -m unittest discover -s tests -v
+Transport integration tests use in-process fake servers and require ollama-client.
 """
-import importlib
+import importlib.util
+import io
 import json
 import math
 import os
 import sys
+import tempfile
 import threading
 import unittest
+from contextlib import redirect_stderr, redirect_stdout
 from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
 from pathlib import Path
+from types import SimpleNamespace
+from unittest.mock import patch

-sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

+_ENGINE_PATH = Path(__file__).resolve().parents[1] / "distill_offline.py"
+_HAVE_CLIENT = importlib.util.find_spec("ollama_client") is not None
+_CONFIG_KEYS = (
+    "OLLAMA_HOST", "OLLAMA_HOSTS", "OLLAMA_URLS", "OLLAMA_URL",
+    "DISTILL_EMBED_MODEL",
+)

-class _Fake(BaseHTTPRequestHandler):
-    models = None  # set per server
-    pulled = None

-    def log_message(self, *a):
+def _load(env=None, *, missing_client=False):
+    """Load fresh engine globals without reloading another test's engine module."""
+    test_env = {k: v for k, v in os.environ.items() if k not in _CONFIG_KEYS}
+    test_env.update(env or {})
+    spec = importlib.util.spec_from_file_location("_distillers_ollama_test", _ENGINE_PATH)
+    module = importlib.util.module_from_spec(spec)
+    with patch.dict(os.environ, test_env, clear=True):
+        if missing_client:
+            with patch.dict(sys.modules, {"ollama_client": None}):
+                spec.loader.exec_module(module)
+        else:
+            spec.loader.exec_module(module)
+    return module
+
+
+class _Fake(BaseHTTPRequestHandler):
+    def log_message(self, *args):
         pass

     def _send(self, code, obj):
-        b = json.dumps(obj).encode()
+        body = json.dumps(obj).encode()
         self.send_response(code)
```

Truncated: 167 additional diff lines; see the delivery PR.

#### `tests/test_tooling.py`

```diff
diff --git a/tests/test_tooling.py b/tests/test_tooling.py
new file mode 100644
index 0000000..f1986c7
--- /dev/null
+++ b/tests/test_tooling.py
@@ -0,0 +1,171 @@
+"""Workflow maintenance must preserve log text and fail closed for active editors."""
+import importlib.util
+import os
+from pathlib import Path
+import tempfile
+import subprocess
+import unittest
+from unittest.mock import patch
+
+SPEC = importlib.util.spec_from_file_location("rotate_workflow_logs", Path(__file__).resolve().parents[1] / "scripts/rotate_workflow_logs.py")
+rotation = importlib.util.module_from_spec(SPEC)
+SPEC.loader.exec_module(rotation)
+
+GEN_SPEC = importlib.util.spec_from_file_location("generate_repo_docs", Path(__file__).resolve().parents[1] / "scripts/generate_repo_docs.py")
+generator = importlib.util.module_from_spec(GEN_SPEC)
+GEN_SPEC.loader.exec_module(generator)
+
+
+class DocumentationInventoryTests(unittest.TestCase):
+    def test_untracked_private_note_is_not_in_census(self):
+        with tempfile.TemporaryDirectory() as directory:
+            root = Path(directory)
+            git_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
+            subprocess.run(["git", "init", "-q", str(root)], check=True, env=git_env)
+            (root / "tracked.md").write_text("# Public project guide")
+            (root / "private-note.md").write_text("# PRIVATE BODY")
+            subprocess.run(["git", "-C", str(root), "add", "tracked.md"], check=True, env=git_env)
+            self.assertIn("tracked.md", generator.census(root))
+            self.assertNotIn("private-note.md", generator.census(root))
+            with patch.dict(os.environ, {"GIT_INDEX_FILE": str(root.parent / "outside-index")}):
+                self.assertIn("tracked.md", generator.census(root))
+                self.assertFalse((root.parent / "outside-index").exists())
+
+    def test_symlink_target_content_is_never_read(self):
+        with tempfile.TemporaryDirectory() as directory:
+            root = Path(directory) / "repo"
+            root.mkdir()
+            outside = Path(directory) / "outside.md"
+            outside.write_text("# PRIVATE OUTSIDE BODY")
+            (root / "link.md").symlink_to(outside)
+            original_open = Path.open
+            def guarded_open(path, *args, **kwargs):
+                if path == root / "link.md" or path.resolve() == outside.resolve():
+                    raise AssertionError("generator opened private symlink content")
+                return original_open(path, *args, **kwargs)
+            with patch.object(Path, "open", guarded_open):
+                card = generator.file_cards(root, ["link.md"])[0]
+            self.assertEqual(card["layer"], "symlink")
+            self.assertNotIn("PRIVATE", str(card))
+            self.assertTrue(generator.missing_links(root, {"llms.txt": "[link](link.md)"}))
+
+    def test_symlink_parent_is_rejected_before_read_or_write(self):
+        with tempfile.TemporaryDirectory() as directory:
+            root = Path(directory) / "repo"
+            outside = Path(directory) / "outside"
+            root.mkdir()
+            outside.mkdir()
+            (outside / "note.md").write_text("# PRIVATE BODY")
+            (root / "docs").symlink_to(outside)
```

Truncated: 112 additional diff lines; see the delivery PR.

Blind gate 1: dissent, reproduced above. Blind gate 2: dissent on the ordinary live-preview open following a symlink.
The loop stopped at its two-gate limit. Fresh/resume counterexamples first failed,
then `_bulk_preview_writer` added nonregular-target rejection and a no-follow
open, with atomic checkpoint reconstruction where no-follow is unavailable.
A separate targeted check confirmed fresh, resumed and check/open-race protection.
It did not replace the blind verdict or perform a third general audit. No cross-model gate was requested.

The final preview remediation is corroborated at `_bulk_preview_writer`: existing
symlinks fail before writes; `O_NOFOLLOW` blocks a substituted target; `fstat`
precedes truncation; unsupported platforms rebuild the preview atomically from
checkpoint units. Four targeted regressions cover fresh/resume/race/fallback.

## Frozen files and retained risks

| File | Read-only findings retained under the explicit freeze |
| --- | --- |
| `split_master.py` | Import-time fixed-corpus reads and non-atomic output overwrites. |
| `categorize_topics.py` | Import-time output overwrite; source metadata can influence its one-off classification. |
| `clean_binary_garbage.py` | Import-time overwrite; multilingual text can be deleted by the 15% non-ASCII heuristic; source parsing is corpus-specific. |
| `clean_index_garbage.py` | Import-time in-place index rewrite; Unicode and empty-source units can be deleted. |

These files were not imported, executed, modified or represented as optimized.
They are excluded from routine checks and maintained-code convergence. Historical
reports remain historical. No downstream live hub acceptance or re-embedding ran.

## Summary

2 repair iterations · 18 applicable passes · Profile: standard · Known outstanding
maintained findings: 0 after targeted remediation · Verify: PASS · Status:
BLIND-AUDIT-DISSENT. The second blind gate reached the review limit before its
last finding received a targeted fix and verification. This is not a CLEAN exit.
No file cap, empirical champion, advisory or feature track applied.

## Snapshot and rollback

Original tracked files and iteration copies reside locally under
`~/.claude/skill-consolidation/backups/distillers-20261111-2107/`.
For example, from the repository root:

```sh
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/distill_offline.py distill_offline.py
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/tests/test_ollama_layer.py tests/test_ollama_layer.py
```

New files have no pre-run copy; the completion receipt marks them `added`.
Remove only those task-created paths when intentionally restoring the baseline.
After delivery, prefer a reviewed revert PR as described in the rollback runbook.

Index: static repo references refreshed; semantic-index refresh N/A outside the
optimizer corpus roots. No vectors were generated. Durable lessons are recorded
in the project tracker; global personal memory files were not edited.

### Literal task rollback commands

These commands intentionally restore the pre-run checkout. Review them before use.

```sh
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/.editorconfig .editorconfig
rm -- .env.example
rm -- .gitattributes
rm -- .github/CODEOWNERS
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/.github/FUNDING.yml .github/FUNDING.yml
rm -- .github/ISSUE_TEMPLATE/bug_report.md
rm -- .github/ISSUE_TEMPLATE/feature_request.md
rm -- .github/SECURITY.md
rm -- .github/copilot-instructions.md
rm -- .github/dependabot.yml
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/.github/pull_request_template.md .github/pull_request_template.md
rm -- .github/workflows/ci.yml
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/.gitignore .gitignore
rm -- .vscode/extensions.json
rm -- .vscode/launch.json
rm -- .vscode/settings.json
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/AGENTS.md AGENTS.md
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/CLAUDE.md CLAUDE.md
rm -- CODE_OF_CONDUCT.md
rm -- CONTRIBUTING.md
rm -- GEMINI.md
rm -- Makefile
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/README.md README.md
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/distill_offline.py distill_offline.py
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/docs/ARCHITECTURE.md docs/ARCHITECTURE.md
rm -- docs/COMPONENTS.md
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/docs/DEVELOPMENT.md docs/DEVELOPMENT.md
rm -- docs/INSTALLATION.md
rm -- docs/MCP.md
rm -- docs/SECURITY.md
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/docs/TESTING.md docs/TESTING.md
rm -- docs/archive/README.md
rm -- docs/audit/completion-files.json
rm -- docs/caching-and-optimization.md
rm -- docs/cli-and-operations.md
rm -- docs/code-deep-optimizer-2026-11-11.md
rm -- docs/codebase-overview.md
rm -- docs/external-calls.md
rm -- docs/high_signal_file_index.json
rm -- docs/integrations-and-assumptions.md
rm -- docs/known-issues.md
rm -- docs/llm-repo-index.json
rm -- docs/logging.md
rm -- docs/onboarding.md
rm -- docs/operations-registry.json
rm -- docs/repo-bootstrap-audit-2026-11-11.md
rm -- docs/requirements.md
rm -- docs/runbooks/embedding-fallback.md
rm -- docs/runbooks/mirror-distillation.md
rm -- docs/runbooks/release-and-rollback.md
rm -- docs/tool-inventory.json
rm -- docs/wiki/README.md
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/llms-facts.txt llms-facts.txt
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/llms-full.txt llms-full.txt
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/llms-small.txt llms-small.txt
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/llms.txt llms.txt
rm -- memory.md
rm -- prompts.md
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/pyproject.toml pyproject.toml
rm -- scripts/generate_repo_docs.py
rm -- scripts/rotate_workflow_logs.py
rm -- tests/test_core.py
cp ~/.claude/skill-consolidation/backups/distillers-20261111-2107/tests/test_ollama_layer.py tests/test_ollama_layer.py
rm -- tests/test_tooling.py
```
