# Known limitations

| Symptom | Cause / affected path | Workaround |
| --- | --- | --- |
| Extracted units need classification/review. | `cmd_extract` and mirror extraction use heuristics; they are not a semantic distillation. | Use the separate classification workflow and retain source anchors. |
| Semantic clustering becomes expensive on large corpora. | Bulk compares retained representatives with existing clusters. | Bound the corpus, use exact-only `--no-semantic`, and profile before redesigning. |
| `index` fails without embeddings. | A vector index cannot be created through lexical fallback. | Configure/install the optional client and host, or use lexical commands. |
| HTML cleanup is simpler than a browser/article extractor. | Stdlib `HTMLParser` does not execute JavaScript or reconstruct a DOM. | Prefer upstream text mirrors and inspect extracted text. |
| CLI diagnostics can include local path/endpoint context. | stderr is an operator diagnostic stream. | Review before sharing and avoid secrets in URLs or file names. |
| Old sample counts or hub commands differ. | Historical reports record the August 2026 environment. | Use current code, checks, and the downstream project's own docs. |
| Frozen helpers require a specific old corpus and write on import. | Four root one-off Python scripts. | Do not import/run them as maintained library components. |

The repository has no live-service health monitor, central JSONL error sink,
automatic remediation framework, or dashboard. These web-service bootstrap items
are not claimed as implemented. See [external calls](external-calls.md) for the
applicable CLI contract and [testing](TESTING.md) for verification limits.
