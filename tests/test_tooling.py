"""Workflow maintenance must preserve log text and fail closed for active editors."""
import importlib.util
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("rotate_workflow_logs", Path(__file__).resolve().parents[1] / "scripts/rotate_workflow_logs.py")
rotation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rotation)

GEN_SPEC = importlib.util.spec_from_file_location("generate_repo_docs", Path(__file__).resolve().parents[1] / "scripts/generate_repo_docs.py")
generator = importlib.util.module_from_spec(GEN_SPEC)
GEN_SPEC.loader.exec_module(generator)


class DocumentationInventoryTests(unittest.TestCase):
    def test_untracked_private_note_is_not_in_census(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            subprocess.run(["git", "init", "-q", str(root)], check=True, env=git_env)
            (root / "tracked.md").write_text("# Public project guide")
            (root / "private-note.md").write_text("# PRIVATE BODY")
            subprocess.run(["git", "-C", str(root), "add", "tracked.md"], check=True, env=git_env)
            self.assertIn("tracked.md", generator.census(root))
            self.assertNotIn("private-note.md", generator.census(root))
            with patch.dict(os.environ, {"GIT_INDEX_FILE": str(root.parent / "outside-index")}):
                self.assertIn("tracked.md", generator.census(root))
                self.assertFalse((root.parent / "outside-index").exists())

    def test_symlink_target_content_is_never_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            outside = Path(directory) / "outside.md"
            outside.write_text("# PRIVATE OUTSIDE BODY")
            (root / "link.md").symlink_to(outside)
            original_open = Path.open
            def guarded_open(path, *args, **kwargs):
                if path == root / "link.md" or path.resolve() == outside.resolve():
                    raise AssertionError("generator opened private symlink content")
                return original_open(path, *args, **kwargs)
            with patch.object(Path, "open", guarded_open):
                card = generator.file_cards(root, ["link.md"])[0]
            self.assertEqual(card["layer"], "symlink")
            self.assertNotIn("PRIVATE", str(card))
            self.assertTrue(generator.missing_links(root, {"llms.txt": "[link](link.md)"}))

    def test_symlink_parent_is_rejected_before_read_or_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            outside = Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "note.md").write_text("# PRIVATE BODY")
            (root / "docs").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "outside repository"):
                generator.file_cards(root, ["docs/note.md"])
            with self.assertRaisesRegex(ValueError, "outside repository"):
                generator.checked_path(root, "docs/new-output.json")
            self.assertFalse((outside / "new-output.json").exists())

    def test_boolean_optional_flags_are_in_cli_inventory(self):
        inventory = generator.cli_inventory(Path(__file__).resolve().parents[1])
        flags = {f for option in inventory["entrypoints"][0]["options"] for f in option["flags"]}
        self.assertTrue({"--no-semantic", "--no-recursive", "--no-resume", "--no-fast-clean"}.issubset(flags))

    def test_generated_missing_links_are_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = {"llms.txt": "[wiki](docs/wiki/README.md)"}
            self.assertTrue(generator.missing_links(root, outputs))
            (root / "docs/wiki").mkdir(parents=True)
            (root / "docs/wiki/README.md").write_text("# Wiki")
            self.assertEqual(generator.missing_links(root, outputs), [])


class WorkflowRotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_rotation_preserves_old_and_latest_sections(self):
        text = "# Log\n\n## v0.1.0 - old\nEarlier facts.\n\n## v0.1.1 - current\nCurrent facts.\n"
        log = self.root / "memory.md"
        log.write_text(text)
        archives = rotation.rotate(self.root, limit=10)
        self.assertEqual(len(archives), 1)
        self.assertEqual((self.root / archives[0]).read_text(), text)
        self.assertEqual(log.read_text(), "# Log\n\n## v0.1.1 - current\nCurrent facts.\n")

    def test_swap_refuses_all_rotation_before_writes(self):
        log = self.root / "memory.md"
        text = "# Log\n## v1\nOld.\n## v2\nCurrent.\n"
        log.write_text(text)
        (self.root / ".prompts.md.swp").write_text("editor")
        with self.assertRaisesRegex(ValueError, "swap"):
            rotation.rotate(self.root, limit=1)
        self.assertEqual(log.read_text(), text)
        self.assertFalse((self.root / "docs").exists())

    def test_single_section_oversize_refuses_without_loss(self):
        log = self.root / "memory.md"
        text = "# Log\n## v1\nOnly section.\n"
        log.write_text(text)
        with self.assertRaisesRegex(ValueError, "older version"):
            rotation.rotate(self.root, limit=1)
        self.assertEqual(log.read_text(), text)

    def test_plain_heading_and_fenced_version_do_not_change_boundary(self):
        text = "# Log\n## v1\nEarlier.\n## v2\nCurrent.\n## validation\nKeep this.\n```md\n```python\n## v99\nExample.\n```\n"
        log = self.root / "memory.md"
        log.write_text(text)
        rotation.rotate(self.root, limit=1)
        self.assertIn("## v2", log.read_text())
        self.assertIn("## validation", log.read_text())
        self.assertIn("## v99", log.read_text())

    def test_external_archive_symlink_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / "docs").mkdir()
            (self.root / "docs/archive").symlink_to(outside)
            log = self.root / "memory.md"
            text = "# Log\n## v1\nOld.\n## v2\nCurrent.\n"
            log.write_text(text)
            with self.assertRaisesRegex(ValueError, "archive directory"):
                rotation.rotate(self.root, limit=1)
            self.assertEqual(log.read_text(), text)
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_late_swap_prevents_log_replacement(self):
        log = self.root / "memory.md"
        text = "# Log\n## v1\nOld.\n## v2\nCurrent.\n"
        log.write_text(text)
        original = rotation.atomic_write
        def add_swap(path, body, before_replace=None):
            (self.root / ".prompts.md.swp").write_text("editor")
            return original(path, body, before_replace)
        with patch.object(rotation, "atomic_write", side_effect=add_swap):
            with self.assertRaisesRegex(ValueError, "swap"):
                rotation.rotate(self.root, limit=1)
        self.assertEqual(log.read_text(), text)

    def test_concurrent_append_is_preserved_and_rotation_refused(self):
        log = self.root / "memory.md"
        text = "# Log\n## v1\nOld.\n## v2\nCurrent.\n"
        log.write_text(text)
        original = rotation.atomic_write
        def append(path, body, before_replace=None):
            with path.open("a") as out:
                out.write("Concurrent fact.\n")
            return original(path, body, before_replace)
        with patch.object(rotation, "atomic_write", side_effect=append):
            with self.assertRaisesRegex(ValueError, "changed during rotation"):
                rotation.rotate(self.root, limit=1)
        self.assertIn("Concurrent fact.", log.read_text())
        self.assertTrue(any("Concurrent fact." in p.read_text() for p in (self.root / "docs/archive").glob("*.md")))

    def test_small_logs_unchanged(self):
        log = self.root / "prompts.md"
        log.write_text("## Prompt v1\nRequest.\n")
        self.assertEqual(rotation.rotate(self.root), [])
        self.assertEqual(log.read_text(), "## Prompt v1\nRequest.\n")


if __name__ == "__main__":
    unittest.main()
