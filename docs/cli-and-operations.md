# CLI and operations

Invoke commands as `python3 distill_offline.py <subcommand>`. `main(argv=None)`
also supports an explicit argv list for callers and tests. Input JSON/text flags
that default to `-` read stdin; ordinary paths are local filesystem paths.

| Command | Important arguments / defaults | Result and side effects |
| --- | --- | --- |
| `mirror` | `--in -`; choose `--list`, `--split-dir DIR`, or `--extract`; otherwise statistics. | JSON stats/units or page URLs on stdout; split mode writes pages and ownership manifest. |
| `extract` | `--in -` | JSON degraded heuristic units; recognizes mirrors before HTML cleanup. |
| `clean` | `--in -`, `--force-html` | Plain text on stdout; no output file. |
| `fetch` | Required `--url`; `--timeout 30` seconds. | HTTP(S) request via curl, then plain text on stdout. |
| `diff` | Required `--old` and `--new`. | JSON added/removed nonblank lines on stdout. |
| `render` | `--in -`, optional `--slug`, `--json-only`. | Central dated JSON/Markdown plus best-effort source-adjacent copy; stdout reports written paths. |
| `merge` | Required `--existing`; `--new-units -`; threshold `0.82`; `--semantic` off. | Merged JSON on stdout, diagnostic counts on stderr. |
| `index` | `--in -`, optional `--name`, configurable `--model`. | Writes a named flat-JSON vector index; reports path/count/model. Requires embeddings. |
| `novelty` | `--in -`; `--against` names defaults to all prior indexes; threshold `0.90`. | JSON novel/matched units; lexical fallback when semantic comparison is unavailable. |
| `bulk` | Required `PATH`; recursive/resume/fast-clean/semantic default on; threshold `0.88`; shard count `1`, index `0`. | Split pages when input is a mirror, progress index, live preview and final master beside input. |

The bulk Boolean flags have explicit `--no-recursive`, `--no-resume`,
`--no-fast-clean`, and `--no-semantic` forms. Stage 2 no longer performs a quadratic
Jaccard pass; without embeddings the funnel retains exact-unique units. Model
flags default to `DISTILL_EMBED_MODEL` or `mxbai-embed-large`.

## Artifacts and ownership

| Artifact | Location |
| --- | --- |
| Rendered pair | `~/.claude/distillations/<slug>-<date>.json` and `.md`; optional pair beside a file source. |
| Unit vector index | `~/.claude/distillations/.index/<name>.json`. |
| Mirror split | Caller-selected `--split-dir`, or `<mirror-stem>.pages/` for bulk input. |
| Bulk state | `.<name>_distill_index.json`, with separate per-shard state when selected. |
| Bulk outputs | `<name>_live_preview.md` and `<name>_master.md` in the working input directory. |
| Split ownership | `.mirror_split_manifest.json` inside the split directory. |

Use dedicated directories and retain originals. Repeating a named render/index
or bulk run can update existing tool-owned artifacts. A split destination with
unowned numbered Markdown files is not a safe output directory.

## Shards and errors

For sharding, split a mirror once, then point workers at the resulting directory
with distinct `--shard-index` values and the same positive `--shard-count`.
Wait for every worker to finish successfully before `--merge-shards`. Avoid
concurrent writers to one state/output path. A single mirror file is not a safe
concurrent shard target.

The standard handled-error exit is 2; argparse also uses 2 for invalid arguments.
Warnings and degradation go to stderr. There is no long-lived process to stop,
service status endpoint, generic operation-history database, or dashboard reset.
See [external calls](external-calls.md), [logging](logging.md), and
[runbooks](wiki/README.md#operating-runbooks).
