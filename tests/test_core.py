"""Dependency-free regressions for data safety, provenance and lexical behavior."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
import subprocess
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import distill_offline as d


def mirror(*pages):
    return "\n".join(f"{'=' * 20}\nURL: {url}\n{'=' * 20}\n{text}" for url, text in pages)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_cli(self, *argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = d.main(list(argv))
        return code, stdout.getvalue(), stderr.getvalue()

    def json_file(self, name, data):
        p = self.root / name
        p.write_text(json.dumps(data), encoding="utf-8")
        return str(p)

    def test_mirror_extract_retains_page_urls(self):
        text = mirror(("https://example.test/one", "First source contains useful documented facts."),
                      ("https://example.test/two", "Second source contains another useful statement."))
        path = self.root / "mirror.md"
        path.write_text(text)
        code, output, _ = self.run_cli("mirror", "--in", str(path), "--extract")
        self.assertEqual(code, 0)
        units = json.loads(output)["units"]
        self.assertEqual([u["source_anchor"] for u in units],
                         ["https://example.test/one#L1", "https://example.test/two#L1"])

    def test_manifest_traversal_refused_without_deletion(self):
        victim = self.root / "victim.md"
        victim.write_text("preserve me")
        out = self.root / "pages"
        out.mkdir()
        (out / ".mirror_split_manifest.json").write_text('["../victim.md"]')
        with self.assertRaises(ValueError):
            d.split_mirror_to_dir(mirror(("https://example.test/a", "Documented source text.")), out)
        self.assertEqual(victim.read_text(), "preserve me")
        self.assertFalse(any(out.glob("[0-9]*.md")))

    def test_manifest_shape_and_names_validated_before_writes(self):
        out = self.root / "pages"
        out.mkdir()
        manifest = out / ".mirror_split_manifest.json"
        for data in ({"001_a.md": True}, [1], ["note.md"], [str(self.root / "victim.md")], ["..\\victim.md"]):
            with self.subTest(data=data):
                manifest.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    d.split_mirror_to_dir(mirror(("https://example.test/a", "Source content here.")), out)
                self.assertFalse(any(out.glob("[0-9]*.md")))

    def test_symlink_manifest_refused(self):
        out = self.root / "pages"
        out.mkdir()
        victim = self.root / "manifest.json"
        victim.write_text("[]")
        (out / ".mirror_split_manifest.json").symlink_to(victim)
        with self.assertRaises(ValueError):
            d.split_mirror_to_dir(mirror(("https://example.test/a", "Source text.")), out)
        self.assertEqual(victim.read_text(), "[]")

    def test_split_preserves_unowned_numbered_notes(self):
        out = self.root / "pages"
        out.mkdir()
        note = out / "001_notes.md"
        note.write_text("operator notes")
        with self.assertRaises(ValueError):
            d.split_mirror_to_dir(mirror(("https://example.test/a", "Source text.")), out)
        self.assertEqual(note.read_text(), "operator notes")

    def test_html_clean_is_stdlib_and_preserves_inline_spacing(self):
        with patch.dict("sys.modules", {"trafilatura": None}):
            self.assertEqual(d._html_to_text("<span>Hello</span> <span>world</span>"), "Hello world")
            text = d._html_to_text('<p>Before</p><embed src="x"><p>After</p><script>SECRET</script>')
        self.assertIn("Before", text)
        self.assertIn("After", text)
        self.assertNotIn("SECRET", text)

    def test_html_entities_decode_once(self):
        self.assertEqual(d._html_to_text("<p>&amp;lt;tag&amp;gt;</p>"), "&lt;tag&gt;")

    def test_html_nested_skipped_tags_remain_hidden(self):
        text = d._html_to_text("<nav><div>hidden</div></nav><p>Visible content</p>")
        self.assertEqual(text, "Visible content")

    def test_render_missing_unknown_type_retains_text_and_anchor(self):
        units = [{"text": "A retained documented statement.", "source_anchor": "https://example.test/a#L1"},
                 {"type": "custom", "text": "Another retained statement."}]
        text = d.render_markdown({"units": units})
        self.assertIn("## Statements", text)
        self.assertIn(units[0]["text"], text)
        self.assertIn(units[0]["source_anchor"], text)
        self.assertNotIn("type", units[0])

    def test_render_retains_all_active_quote_and_removed_anchors(self):
        first, second = "https://example.test/one#L1", "https://example.test/two#L2"
        for kind, status in (("statement", None), ("quote", None), ("statement", "removed")):
            with self.subTest(kind=kind, status=status):
                text = d.render_markdown({"units": [{"type": kind, "status": status, "text": "A documented shared source statement.", "source_anchor": first, "source_anchors": [first, second]}]})
                self.assertIn(first, text)
                self.assertIn(second, text)

    def test_bulk_exact_dedup_keeps_decimals_and_operators_distinct(self):
        path = self.root / "measurements.txt"
        statements = ["The calibrated voltage value is 1.2 millivolts.",
                      "The calibrated voltage value is 12 millivolts.",
                      "The configured arithmetic relation is x >= y.",
                      "The configured arithmetic relation is x <= y."]
        path.write_text("\n".join(statements))
        for options in (("--no-fast-clean",), ()):
            with self.subTest(options=options):
                code, _, err = self.run_cli("bulk", str(path), "--no-semantic", "--no-resume", *options)
                self.assertEqual(code, 0, err)
                master = (self.root / "measurements_master.md").read_text()
                for statement in statements:
                    self.assertIn(statement, master)

    def test_bulk_directory_does_not_reingest_owned_prior_outputs(self):
        path = self.root / "doc.txt"
        path.write_text("A documented source statement with useful content.")
        self.assertEqual(self.run_cli("bulk", str(path), "--no-semantic")[0], 0)
        self.assertEqual(self.run_cli("bulk", str(self.root), "--no-semantic")[0], 0)
        index = json.loads((self.root / f".{self.root.name}_distill_index.json").read_text())
        self.assertEqual(index["files_processed"], [str(path)])
        master = (self.root / f"{self.root.name}_master.md").read_text()
        self.assertEqual(master.count("documented source statement"), 1)
        self.assertNotIn("[x", master)

    def test_render_refuses_filename_traversal(self):
        with self.assertRaises(ValueError):
            d._write_pair(self.root / "out", "../escaped", "2026-11-11", {"units": []}, True)
        with self.assertRaises(ValueError):
            d._write_pair(self.root / "out", "safe", "../../escaped", {"units": []}, True)
        self.assertFalse((self.root / "escaped-2026-11-11.json").exists())

    def test_index_preserves_unit_and_source_provenance(self):
        src = {"title": "Guide", "ref": "mirror.md", "type": "file"}
        unit = {"id": "u001", "type": "fact", "text": "One factual source statement.",
                "source_anchor": "https://example.test/a#L3"}
        path = self.json_file("units.json", {"source": src, "units": [unit]})
        with patch.object(d, "INDEX_DIR", self.root / "indexes"), patch.object(d, "_ollama_embed", return_value=[[1.0, 0.0]]):
            code, out, _ = self.run_cli("index", "--in", path, "--name", "guide")
        self.assertEqual(code, 0)
        index = json.loads(Path(json.loads(out)["index"]).read_text())
        self.assertEqual(index["entries"][0]["source_anchor"], unit["source_anchor"])
        self.assertEqual(index["entries"][0]["source"], src["ref"])

    def test_index_rejects_partial_vectors_without_overwriting(self):
        units = self.json_file("units.json", [{"text": "First valid documented statement."}, {"text": "Second valid documented statement."}])
        index_dir = self.root / "indexes"
        index_dir.mkdir()
        prior = index_dir / "guide.json"
        prior.write_text("preserve existing index")
        with patch.object(d, "INDEX_DIR", index_dir), patch.object(d, "_ollama_embed", return_value=[[1.0]]):
            code, _, err = self.run_cli("index", "--in", units, "--name", "guide")
        self.assertEqual(code, 2)
        self.assertIn("ERROR", err)
        self.assertEqual(prior.read_text(), "preserve existing index")

    def test_embedding_client_value_error_degrades_to_unavailable(self):
        client = SimpleNamespace(embed=lambda *a, **kw: (_ for _ in ()).throw(ValueError("malformed transport reply")))
        with patch.object(d, "_client", return_value=client):
            with self.assertRaises(d.OllamaUnavailable):
                d._ollama_embed(["first"], "model")

    def test_embedding_batch_validation(self):
        bad_batches = ([[1.0]], [[1.0], [1.0, 2.0]], [[float("nan")], [1.0]], [[], []], [[True], [1.0]])
        for vectors in bad_batches:
            with self.subTest(vectors=vectors):
                client = SimpleNamespace(embed=lambda *a, **kw: vectors)
                with patch.object(d, "_client", return_value=client):
                    with self.assertRaises(d.OllamaUnavailable):
                        d._ollama_embed(["first", "second"], "model")

    def test_novelty_incompatible_model_uses_lexical_and_logs(self):
        cand = self.json_file("candidates.json", [{"text": "Entirely different new content.", "source_anchor": "https://example.test/new#L1"}])
        index_dir = self.root / "indexes"
        index_dir.mkdir()
        (index_dir / "prior.json").write_text(json.dumps({"model": "other-model", "entries": [{"id": "u1", "text": "Original reference.", "vector": [1.0, 0.0], "source_anchor": "https://example.test/old#L1"}]}))
        with patch.object(d, "INDEX_DIR", index_dir), patch.object(d, "_ollama_embed", return_value=[[1.0, 0.0]]), patch.object(d, "_cosine", return_value=1.0):
            code, out, err = self.run_cli("novelty", "--in", cand, "--against", "prior", "--model", "new-model")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["mode"], "lexical")
        self.assertEqual(json.loads(out)["novel_count"], 1)
        self.assertIn("WARN", err)

    def test_novelty_dimension_mismatch_uses_lexical(self):
        cand = self.json_file("candidates.json", [{"text": "Novel candidate with new information."}])
        index_dir = self.root / "indexes"
        index_dir.mkdir()
        (index_dir / "prior.json").write_text(json.dumps({"model": "model", "entries": [{"id": "u1", "text": "Reference text.", "vector": [1.0]}]}))
        with patch.object(d, "INDEX_DIR", index_dir), patch.object(d, "_ollama_embed", return_value=[[1.0, 0.0]]), patch.object(d, "_cosine", return_value=1.0):
            code, out, err = self.run_cli("novelty", "--in", cand, "--model", "model")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["mode"], "lexical")
        self.assertIn("WARN", err)

    def test_novelty_matches_retain_reference_anchor(self):
        text = "A repeated documented source statement."
        cand = self.json_file("candidates.json", [{"text": text}])
        index_dir = self.root / "indexes"
        index_dir.mkdir()
        anchor = "https://example.test/old#L7"
        (index_dir / "prior.json").write_text(json.dumps({"model": "model", "entries": [{"id": "u1", "text": text, "vector": [1.0], "source_anchor": anchor}]}))
        with patch.object(d, "INDEX_DIR", index_dir), patch.object(d, "_ollama_embed", side_effect=d.OllamaUnavailable("offline")):
            code, out, err = self.run_cli("novelty", "--in", cand)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["matched"][0]["source_anchor"], anchor)
        self.assertIn("WARN", err)

    def test_bulk_preserves_deduplicated_page_anchors(self):
        path = self.root / "guide.md"
        text = "A shared source statement retained by exact deduplication."
        path.write_text(mirror(("https://example.test/one", text), ("https://example.test/two", text)))
        code, _, _ = self.run_cli("bulk", str(path), "--no-semantic")
        self.assertEqual(code, 0)
        out = (self.root / "guide.pages/guide_master.md").read_text()
        index = json.loads((self.root / "guide.pages/.guide_distill_index.json").read_text())
        for url in ("https://example.test/one", "https://example.test/two"):
            self.assertIn(url, out)
            self.assertIn(url, json.dumps(index))
        unit = next(iter(index["unique_units"].values()))
        self.assertTrue(unit["source_anchor"].startswith("https://example.test/"))
        self.assertFalse(unit["text"].startswith("URL:"))

    def test_bulk_resume_rebuilds_changed_or_removed_inputs(self):
        a, b = self.root / "a.txt", self.root / "b.txt"
        a.write_text("Original material that must disappear after editing.")
        b.write_text("Deleted material that must disappear from output.")
        self.assertEqual(self.run_cli("bulk", str(self.root), "--no-semantic")[0], 0)
        a.write_text("Replacement material that must appear after editing.")
        b.unlink()
        code, _, err = self.run_cli("bulk", str(self.root), "--no-semantic")
        self.assertEqual(code, 0)
        master = (self.root / f"{self.root.name}_master.md").read_text()
        self.assertIn("Replacement material", master)
        self.assertNotIn("Original material", master)
        self.assertNotIn("Deleted material", master)
        self.assertIn("WARN", err)

    def test_corrupt_cache_rebuilds_with_warning(self):
        path = self.root / "doc.txt"
        path.write_text("A valid original documented statement.")
        self.assertEqual(self.run_cli("bulk", str(path), "--no-semantic")[0], 0)
        index_path = self.root / ".doc_distill_index.json"
        index = json.loads(index_path.read_text())
        index["unique_units"] = {"corrupt": {"text": "bad payload"}}
        index_path.write_text(json.dumps(index))
        code, _, err = self.run_cli("bulk", str(path), "--no-semantic")
        self.assertEqual(code, 0)
        self.assertIn("WARN", err)
        self.assertIn("valid original", (self.root / "doc_master.md").read_text())

    def test_bulk_mirror_resume_refreshes_source(self):
        path = self.root / "guide.md"
        path.write_text(mirror(("https://example.test/a", "Original source text that later changes.")))
        self.assertEqual(self.run_cli("bulk", str(path), "--no-semantic")[0], 0)
        path.write_text(mirror(("https://example.test/a", "Replacement source text with fresh content.")))
        self.assertEqual(self.run_cli("bulk", str(path), "--no-semantic")[0], 0)
        master = (self.root / "guide.pages/guide_master.md").read_text()
        self.assertIn("Replacement source text", master)
        self.assertNotIn("Original source text", master)

    def test_bulk_fresh_preview_symlink_preserves_external_target(self):
        path = self.root / "doc.txt"
        path.write_text("A documented source statement retained by the tool.")
        victim = self.root / "unrelated.md"
        victim.write_text("KEEP UNRELATED FILE")
        (self.root / "doc_live_preview.md").symlink_to(victim)
        code, _, err = self.run_cli("bulk", str(path), "--no-semantic")
        self.assertEqual(code, 2)
        self.assertIn("ERROR", err)
        self.assertEqual(victim.read_text(), "KEEP UNRELATED FILE")

    def test_bulk_resumed_preview_symlink_preserves_external_target(self):
        path = self.root / "doc.txt"
        path.write_text("A documented source statement retained by the tool.")
        self.assertEqual(self.run_cli("bulk", str(path), "--no-semantic")[0], 0)
        victim = self.root / "unrelated.md"
        victim.write_text("KEEP UNRELATED FILE")
        preview = self.root / "doc_live_preview.md"
        preview.unlink()
        preview.symlink_to(victim)
        code, _, err = self.run_cli("bulk", str(path), "--no-semantic")
        self.assertEqual(code, 2)
        self.assertIn("ERROR", err)
        self.assertEqual(victim.read_text(), "KEEP UNRELATED FILE")

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "platform uses atomic fallback")
    def test_bulk_preview_symlink_race_is_refused_by_open(self):
        path = self.root / "doc.txt"
        path.write_text("A documented source statement retained by the tool.")
        victim = self.root / "unrelated.md"
        victim.write_text("KEEP UNRELATED FILE")
        preview = self.root / "doc_live_preview.md"
        real_open = os.open
        def race(target, flags, *args, **kwargs):
            if Path(target) == preview:
                preview.symlink_to(victim)
            return real_open(target, flags, *args, **kwargs)
        with patch.object(d.os, "open", side_effect=race):
            code, _, err = self.run_cli("bulk", str(path), "--no-semantic")
        self.assertEqual(code, 2)
        self.assertIn("ERROR", err)
        self.assertEqual(victim.read_text(), "KEEP UNRELATED FILE")

    def test_bulk_preview_atomic_fallback_retains_checkpoint_content(self):
        path = self.root / "preview.md"
        path.write_text("old preview text")
        prior = [{"text": "Retained prior source statement.", "source_anchor": "https://example.test/a#L1"}]
        with patch.dict(d.os.__dict__):
            d.os.__dict__.pop("O_NOFOLLOW", None)
            with d._bulk_preview_writer(path, False, prior) as out:
                out.write("New source statement.\n")
        result = path.read_text()
        self.assertIn(prior[0]["text"], result)
        self.assertIn(prior[0]["source_anchor"], result)
        self.assertIn("New source statement.", result)
        self.assertNotIn("old preview text", result)

    def test_bulk_offline_semantic_fallback_keeps_content_and_logs(self):
        path = self.root / "doc.txt"
        path.write_text("A source statement retained when embedding is unavailable.")
        with patch.object(d, "_ollama_embed", side_effect=d.OllamaUnavailable("offline")):
            code, _, err = self.run_cli("bulk", str(path))
        self.assertEqual(code, 0)
        self.assertIn("source statement", (self.root / "doc_master.md").read_text())
        self.assertIn("WARN", err)

    def test_invalid_shard_arguments_have_no_output_side_effects(self):
        path = self.root / "guide.md"
        path.write_text(mirror(("https://example.test/a", "A documented source statement.")))
        for opts in (("--shard-count", "0"), ("--shard-index", "-1"), ("--shard-count", "2")):
            with self.subTest(opts=opts):
                code, _, err = self.run_cli("bulk", str(path), "--no-semantic", *opts)
                self.assertEqual(code, 2)
                self.assertIn("ERROR", err)
                self.assertFalse((self.root / "guide.pages").exists())

    def test_missing_shard_refuses_to_replace_master(self):
        master = self.root / f"{self.root.name}_master.md"
        master.write_text("previous complete result")
        before = {p.name for p in self.root.iterdir()}
        code, _, err = self.run_cli("bulk", str(self.root), "--no-semantic", "--merge-shards", "--shard-count", "2")
        self.assertEqual(code, 2)
        self.assertIn("ERROR", err)
        self.assertEqual(master.read_text(), "previous complete result")
        self.assertEqual({p.name for p in self.root.iterdir()}, before)


    def test_fetch_failure_does_not_log_url_credentials(self):
        url = "https://user:password@example.test/page?token=private-value"
        failure = subprocess.CalledProcessError(22, ["curl", url], stderr="private-value")
        with patch.object(d.subprocess, "run", side_effect=failure):
            code, out, err = self.run_cli("fetch", "--url", url)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("ERROR", err)
        for value in ("password", "private-value", url):
            self.assertNotIn(value, err)

    def test_novelty_zero_threshold_uses_an_actual_best_match(self):
        cand = self.json_file("candidates.json", [{"text": "zzzz"}])
        index_dir = self.root / "indexes"
        index_dir.mkdir()
        (index_dir / "prior.json").write_text(json.dumps({"model": "model", "entries": [
            {"id": "first", "text": "aaaa", "vector": [1.0]},
            {"id": "last", "text": "bbbb", "vector": [1.0]}]}))
        with patch.object(d, "INDEX_DIR", index_dir), patch.object(d, "_ollama_embed", side_effect=d.OllamaUnavailable("offline")):
            code, out, _ = self.run_cli("novelty", "--in", cand, "--threshold", "0")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["matched"][0]["matched_id"], "first")

    def test_complete_shards_merge_all_units_and_sources(self):
        (self.root / "one.txt").write_text("The first source contains a unique documented statement.")
        (self.root / "two.txt").write_text("The second source contains another unique documented fact.")
        for shard in (0, 1):
            code, _, err = self.run_cli("bulk", str(self.root), "--no-semantic", "--shard-count", "2", "--shard-index", str(shard))
            self.assertEqual(code, 0, err)
        code, _, err = self.run_cli("bulk", str(self.root), "--no-semantic", "--shard-count", "2", "--merge-shards")
        self.assertEqual(code, 0, err)
        master = (self.root / f"{self.root.name}_master.md").read_text()
        self.assertIn("first source", master)
        self.assertIn("second source", master)

if __name__ == "__main__":
    unittest.main()
