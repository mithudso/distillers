# Installation

## Prerequisites

Python 3.11+ runs the core on systems with standard filesystem and process APIs.
Git is needed to clone; curl is required only for `fetch`. Make and VS Code are
optional contributor conveniences. No server, daemon, GPU, or minimum hardware
profile is required by the core; corpus size determines memory and disk needs.

## Run from a checkout

```bash
git clone https://github.com/mithudso/distillers.git
cd distillers
python3 distill_offline.py mirror --in /path/to/mirror.md
```

No package installation is needed for stdlib operation. To install the importable
module into a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
```

For optional embedding support:

```bash
.venv/bin/python -m pip install '.[semantic]'
```

Configure endpoints/model using the process environment documented in
[development](DEVELOPMENT.md). Semantic commands send text to those endpoints;
a missing embedding model may be pulled. `bulk --no-semantic` avoids that path.

## Verification

Run the three [repository checks](TESTING.md), then `mirror --in` against a known
mirror. The absence of Ollama does not prevent mirror parsing, extraction, diff,
rendering, or lexical bulk/merge/novelty operation. `index` requires embeddings.

## Upgrade and uninstall

Preserve dirty work before updating a checkout. Fetch and fast-forward a clean
compatible branch, then repeat verification. Reinstall the optional extra when
its pin changes. If a skill contains an engine copy, follow the
[skill synchronization procedure](DEVELOPMENT.md#skill-copy-sync).

For an installed module, run `.venv/bin/python -m pip uninstall distillers`.
Retain source documents and output artifacts unless their deletion is separately
intended. Uninstalling the package does not delete `~/.claude/distillations/`,
bulk artifacts, the optional shared client, models, or skill copies.
