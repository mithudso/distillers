#!/usr/bin/env python3
"""Generate static file/CLI/operation inventories without imports or embeddings."""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
GENERATED = (
    "docs/codebase-overview.md", "docs/high_signal_file_index.json",
    "docs/llm-repo-index.json", "docs/tool-inventory.json",
    "docs/operations-registry.json", "llms.txt", "llms-small.txt",
    "llms-full.txt", "llms-facts.txt",
)
FROZEN = {"split_master.py", "categorize_topics.py", "clean_binary_garbage.py", "clean_index_garbage.py"}
PURPOSES = {
    "distill_offline.py": "Canonical document-distillation CLI and importable engine.",
    "tests/test_core.py": "Dependency-free data safety, provenance and fallback regressions.",
    "tests/test_ollama_layer.py": "Isolated configuration and optional loopback-client integration tests.",
    "scripts/generate_repo_docs.py": "Static inventory generator and documentation drift gate.",
    "scripts/rotate_workflow_logs.py": "Archive older workflow-log sections with editor-swap protection.",
    "pyproject.toml": "Package version, Python requirement and optional semantic dependency pin.",
    "Makefile": "Convenient stdlib verification and documentation targets.",
    "KICKOFF.md": "Historical implementation brief; current guidance lives under docs/.",
    "STATUS.md": "Historical downstream acceptance snapshot, not current integration evidence.",
    "SUMMARY.md": "Historical build summary, not current runtime evidence.",
}


def census(root: Path) -> list[str]:
    data = subprocess.check_output(
        ["git", "ls-files", "--cached", "-z"], cwd=root,
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    )
    names = {p.decode("utf-8") for p in data.split(b"\0") if p}
    return sorted({n for n in names if (root / n).is_file() or (root / n).is_symlink()} | set(GENERATED))


def role(path: str) -> str:
    if path in FROZEN:
        return "frozen-script"
    if path in GENERATED:
        return "generated"
    if path.startswith("tests/"):
        return "test"
    if path.startswith("scripts/"):
        return "tooling"
    if path.startswith(".github/workflows/"):
        return "infra"
    if path == "distill_offline.py":
        return "entrypoint"
    if path.startswith("docs/") or path.endswith(".md"):
        return "docs"
    return "config"


def checked_path(root: Path, name: str) -> Path:
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"refusing path outside repository: {name}")
    return path


def file_cards(root: Path, names: list[str]) -> list[dict]:
    cards = []
    for name in names:
        exports, imports = [], []
        path = root / name
        if path.is_symlink():
            cards.append({"path": name, "purpose": "Tracked symbolic link; target is not read.",
                          "layer": "symlink", "exports": [], "depends_on": []})
            continue
        path = checked_path(root, name)
        if name.endswith(".py") and path.exists():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            exports = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
        purpose = PURPOSES.get(name)
        if name in FROZEN:
            purpose = "Frozen historical corpus-specific helper; never import or run in routine checks."
        elif not purpose and name in GENERATED:
            purpose = "Generated repository reference; regenerate with scripts/generate_repo_docs.py."
        elif not purpose and path.exists() and path.suffix == ".md":
            purpose = next((line.lstrip("# ").strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("#")), name)
        cards.append({"path": name, "purpose": purpose or f"Repository {role(name)} file.",
                      "layer": role(name), "exports": exports, "depends_on": sorted(set(imports))})
    return cards


def cli_inventory(root: Path) -> dict:
    """Read argparse call sites; never execute the target or harvest --help."""
    entries = []
    for name in ("distill_offline.py", "scripts/generate_repo_docs.py", "scripts/rotate_workflow_logs.py"):
        text = checked_path(root, name).read_text(encoding="utf-8")
        tree = ast.parse(text)
        commands = []
        options = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr == "add_parser" and node.args and isinstance(node.args[0], ast.Constant):
                commands.append({"name": node.args[0].value, "line": node.lineno})
            elif node.func.attr == "add_argument":
                flags = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                defaults = {kw.arg: ast.get_source_segment(text, kw.value) for kw in node.keywords if kw.arg in {"default", "required", "type", "action", "nargs"}}
                if defaults.get("action") == "argparse.BooleanOptionalAction":
                    flags += ["--no-" + flag[2:] for flag in flags if flag.startswith("--")]
                options.append({"parser": ast.get_source_segment(text, node.func.value), "flags": flags,
                                "settings_source": defaults, "source": f"{name}:{node.lineno}"})
        entries.append({"name": name, "invocation": f"python3 {name}", "subcommands": sorted(commands, key=lambda c: c["line"]), "options": options})
    return {"generated_by": "scripts/generate_repo_docs.py", "kind": "CLI (no MCP server)", "totalTools": len(entries), "entrypoints": entries}


def operation_inventory(root: Path) -> dict:
    tree = ast.parse(checked_path(root, "distill_offline.py").read_text(encoding="utf-8"))
    lines = {n.name: n.lineno for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    specs = [
        ("fetch-url", "check", "subprocess/http(s)", "caller-selected HTTP(S) URL via curl", "cmd_fetch", "fetch --url <URL>", True, "Bounded curl request; rerun explicitly.", {"CalledProcessError": "Check connectivity and URL; do not log URL credentials.", "TimeoutExpired": "Check connectivity or choose an appropriate timeout.", "FileNotFoundError": "Install curl."}),
        ("embed-units", "check", "http", "OLLAMA_HOSTS or OLLAMA_HOST via optional ollama-client", "_ollama_embed", "index --in <JSON>", False, "Shared client owns retries, failover and model pulls.", {"OllamaUnavailable": "Install optional client or restore Ollama; merge/novelty/bulk degrade where supported."}),
        ("render-artifacts", "sync", "local", "central and optional source-adjacent JSON/Markdown", "_write_pair", "render --in <JSON>", False, "No automatic retry.", {"OSError": "Check permissions and available storage."}),
        ("split-mirror", "sync", "local", "dedicated page directory and ownership manifest", "split_mirror_to_dir", "mirror --in <MIRROR> --split-dir <DIR>", False, "No automatic retry.", {"ValueError": "Use a dedicated directory; never bypass invalid ownership metadata."}),
        ("write-vector-index", "sync", "local", "flat JSON index under ~/.claude/distillations/.index", "cmd_index", "index --in <JSON>", False, "No automatic retry.", {"OSError": "Check output permissions and available storage."}),
        ("bulk-artifacts", "sync", "local", "versioned cache, preview and master next to input", "cmd_bulk", "bulk <PATH> --no-semantic", False, "Content-aware resume; explicit rerun.", {"ValueError": "Check shard completeness, ownership and input configuration.", "OSError": "Check input readability and output storage."}),
    ]
    operations = []
    for ident, kind, transport, target, symbol, invocation, read_only, retry, remediation in specs:
        operations.append({"id": ident, "kind": kind, "transport": transport, "target": target,
                           "sourceFile": "distill_offline.py", "sourceSymbol": symbol, "line": lines[symbol],
                           "trigger": f"python3 distill_offline.py {invocation}", "readOnly": read_only,
                           "retryPolicy": retry, "verifyDatastore": False,
                           "verification": "Regression tests inspect outputs; no runtime datastore read-back service.",
                           "remediation": {k: {"hint": v, "safety": "escalate"} for k, v in remediation.items()}})
    return {"generated_by": "scripts/generate_repo_docs.py", "operations": operations,
            "audit": {"scope": "Static operation-family inventory; not a runtime dispatcher.",
                      "five_standard_contract": "not fully adopted", "gaps": ["No centralized JSONL error sink", "No dashboard runtime", "No automatic remediation executor", "No runtime datastore read-back"]},
            "status": {"live_service_probed": False, "semantic_indexing_run": False}}


def render(root: Path) -> dict[str, str]:
    names = census(root)
    cards = file_cards(root, names)
    inventory = cli_inventory(root)
    version = tomllib.loads(checked_path(root, "pyproject.toml").read_text())["project"]["version"]
    intro = ("distillers is an offline Python document-distillation engine. The stdlib core parses "
             "fixed web-text-mirror banners, extracts source-anchored units, renders Markdown and JSON, "
             "and deduplicates text. Optional ollama-client supplies embeddings.\n")
    lines = ["# Codebase overview", "", "Generated by `python3 scripts/generate_repo_docs.py`. Do not edit.", "", "Every tracked project file appears below. Stage intended new files before regenerating. Frozen helpers are inventoried, never imported.", "", "| Path | Role | Purpose |", "| --- | --- | --- |"]
    for card in cards:
        name = card["path"]
        lines.append(f"| [{name}](../{name}) | {card['layer']} | {card['purpose'].replace('|', '/')} |")
    commands = ", ".join(c["name"] for c in inventory["entrypoints"][0]["subcommands"])
    full = ("# distillers reference\n\n" + intro + f"\nVersion: {version}. Python >=3.11. [src: pyproject.toml]\n"
            + f"\nCommands: {commands}. [src: distill_offline.py]\n"
            + "\nOLLAMA_HOST defaults to http://localhost:11434; OLLAMA_HOSTS configures the pool; DISTILL_EMBED_MODEL defaults to mxbai-embed-large. [src: distill_offline.py]\n"
            + "\nUse --no-semantic for a bulk run without embedding requests. index requires working embeddings. [src: distill_offline.py]\n"
            + "\nMirror extraction, bulk cache/master, vector entries and novelty matches retain source_anchor provenance. [src: distill_offline.py]\n"
            + "\nBulk cache reuse validates input content and configuration. Changed inputs rebuild the cache. [src: distill_offline.py]\n"
            + "\nFrozen corpus helpers have import-time writes. Never import them in routine tooling. [src: CLAUDE.md]\n"
            + "\nRead docs/wiki/README.md for commands, procedures and strategy. [src: docs/wiki/README.md]\n"
            + "\n## File map\n\n" + "\n".join(f"- {c['path']}: {c['purpose']} [src: {c['path']}]" for c in cards) + "\n")
    short = "# distillers quick reference\n\n" + intro + "\nStart with docs/wiki/README.md, docs/DEVELOPMENT.md and docs/TESTING.md.\n\nVerify:\npython3 -m py_compile distill_offline.py\npython3 -m unittest discover -s tests -v\npython3 scripts/generate_repo_docs.py --check\n\nCore: distill_offline.py. Frozen: split_master.py, categorize_topics.py, clean_*.py.\nConfiguration: OLLAMA_HOST, OLLAMA_HOSTS, DISTILL_EMBED_MODEL. Default host is localhost:11434.\nKeep mirror page source_anchor values intact. Use --no-semantic for offline bulk.\n"
    facts = "# distillers facts\n\n" + "\n".join(line for line in full.splitlines() if "[src:" in line and not line.startswith("- ")) + "\n"
    as_json = lambda obj: json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    return {
        "docs/codebase-overview.md": "\n".join(lines) + "\n",
        "docs/high_signal_file_index.json": as_json([{"component": "distillers", "files": cards}]),
        "docs/llm-repo-index.json": as_json({"generated_by": "scripts/generate_repo_docs.py", "files": cards}),
        "docs/tool-inventory.json": as_json(inventory),
        "docs/operations-registry.json": as_json(operation_inventory(root)),
        "llms.txt": "# distillers\n\n" + intro + "\n- [Quick reference](llms-small.txt)\n- [Full reference](llms-full.txt)\n- [Facts](llms-facts.txt)\n- [Project wiki](docs/wiki/README.md)\n- [File map](docs/codebase-overview.md)\n- [CLI inventory](docs/tool-inventory.json)\n",
        "llms-small.txt": short, "llms-full.txt": full, "llms-facts.txt": facts,
    }


def missing_links(root: Path, outputs: dict[str, str]) -> list[str]:
    missing = []
    for name, body in outputs.items():
        if not name.endswith((".md", ".txt")):
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", body):
            if target.startswith(("https://", "http://", "#")):
                continue
            relative = target.split("#", 1)[0]
            path = (root / name).parent / relative
            resolved = path.resolve()
            if not resolved.is_relative_to(root.resolve()) or not path.exists():
                missing.append(f"{name} -> {target}")
    return missing


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on inventory drift or dead paths")
    args = parser.parse_args(argv)
    try:
        outputs = render(ROOT)
        paths = {name: checked_path(ROOT, name) for name in outputs}
        missing = missing_links(ROOT, outputs)
        stale = [name for name, text in outputs.items() if not paths[name].exists() or paths[name].read_text(encoding="utf-8") != text]
    except (OSError, ValueError, SyntaxError, subprocess.CalledProcessError) as exc:
        print(f"ERROR static inventory: {exc}", file=sys.stderr)
        return 1
    if args.check:
        if stale or missing:
            if stale:
                print("Documentation drift: " + ", ".join(stale) + "; run python3 scripts/generate_repo_docs.py", file=sys.stderr)
            if missing:
                print("Missing or unsafe documentation paths: " + ", ".join(missing), file=sys.stderr)
            return 1
        print(f"Documentation indexes current: {len(census(ROOT))} files, {len(outputs)} artifacts; no dead paths.")
        return 0
    for name, text in outputs.items():
        path = paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"Generated {len(outputs)} artifacts for {len(census(ROOT))} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
