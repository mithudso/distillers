"""Configuration, lexical fallback, and optional Ollama transport tests.

Run: python3 -m unittest discover -s tests -v
Transport integration tests use in-process fake servers and require ollama-client.
"""
import importlib.util
import io
import json
import math
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


_ENGINE_PATH = Path(__file__).resolve().parents[1] / "distill_offline.py"
_HAVE_CLIENT = importlib.util.find_spec("ollama_client") is not None
_CONFIG_KEYS = (
    "OLLAMA_HOST", "OLLAMA_HOSTS", "OLLAMA_URLS", "OLLAMA_URL",
    "DISTILL_EMBED_MODEL",
)


def _load(env=None, *, missing_client=False):
    """Load fresh engine globals without reloading another test's engine module."""
    test_env = {k: v for k, v in os.environ.items() if k not in _CONFIG_KEYS}
    test_env.update(env or {})
    spec = importlib.util.spec_from_file_location("_distillers_ollama_test", _ENGINE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, test_env, clear=True):
        if missing_client:
            with patch.dict(sys.modules, {"ollama_client": None}):
                spec.loader.exec_module(module)
        else:
            spec.loader.exec_module(module)
    return module


class _Fake(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.server.unavailable:
            return self._send(503, {"error": "test server unavailable"})
        self._send(200, {"models": [{"name": m} for m in self.server.models]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.server.unavailable:
            return self._send(503, {"error": "test server unavailable"})
        model = body.get("model", "")
        have = model in self.server.models or f"{model}:latest" in self.server.models
        if self.path == "/api/pull":
            self.server.models.add(f"{model}:latest")
            self.server.pulled.append(model)
            return self._send(200, {"status": "success"})
        if not have:
            return self._send(404, {"error": f'model "{model}" not found'})
        if self.path == "/api/embed":
            return self._send(200, {"embeddings": [[1.0, float(len(t))] for t in body["input"]]})
        if self.path == "/api/embeddings":
            return self._send(200, {"embedding": [1.0, float(len(body["prompt"]))]})
        self._send(404, {})


class Configuration(unittest.TestCase):
    def test_default_model_pinned(self):
        d = _load()
        self.assertEqual(d.DEFAULT_EMBED_MODEL, "mxbai-embed-large")
        self.assertEqual(d.OLLAMA_URL, "http://localhost:11434")

    def test_explicit_model_override(self):
        d = _load({"DISTILL_EMBED_MODEL": "test-embedding-model"})
        self.assertEqual(d.DEFAULT_EMBED_MODEL, "test-embedding-model")

    def test_load_preserves_environment_and_shared_module(self):
        shared_module = sys.modules.get("distill_offline")
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://operator.invalid:11434",
                                     "DISTILL_EMBED_MODEL": "operator-model"}):
            before = dict(os.environ)
            d = _load({"OLLAMA_HOST": "http://127.0.0.1:12345"})
            self.assertEqual(d.DEFAULT_EMBED_MODEL, "mxbai-embed-large")
            self.assertEqual(d.OLLAMA_URL, "http://127.0.0.1:12345")
            self.assertEqual(dict(os.environ), before)
        self.assertIs(sys.modules.get("distill_offline"), shared_module)


class MissingClient(unittest.TestCase):
    def test_missing_library_reports_unavailable(self):
        d = _load(missing_client=True)
        self.assertFalse(d._HAVE_OLLAMA_CLIENT)
        self.assertEqual(d._ollama_embed([], "x"), [])
        with self.assertRaisesRegex(d.OllamaUnavailable, "not installed"):
            d._ollama_embed(["x"], d.DEFAULT_EMBED_MODEL)

    def test_missing_library_merge_uses_lexical_fallback(self):
        d = _load(missing_client=True)
        existing = {"units": [{"id": "u001", "type": "statement",
                               "text": "An existing useful statement.",
                               "source_anchor": "https://example.test/old#L1"}]}
        candidates = [
            {"id": "candidate-1", "type": "statement",
             "text": "An existing useful statement.",
             "source_anchor": "https://example.test/new#L1"},
            {"id": "candidate-2", "type": "actionable",
             "text": "Configure the offline documentation cache before ingestion.",
             "source_anchor": "https://example.test/new#L2"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            old_path, new_path = Path(tmp) / "existing.json", Path(tmp) / "new.json"
            old_path.write_text(json.dumps(existing), encoding="utf-8")
            new_path.write_text(json.dumps(candidates), encoding="utf-8")
            args = SimpleNamespace(existing=str(old_path), new_units=str(new_path),
                                   semantic=True, threshold=0.9, model=d.DEFAULT_EMBED_MODEL)
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(d.cmd_merge(args), 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(len(result["units"]), 2)
        self.assertEqual(result["units"][0]["duplicates"], ["candidate-1"])
        self.assertEqual(result["units"][0]["source_anchor"], "https://example.test/old#L1")
        self.assertEqual(result["units"][1]["source_anchor"], "https://example.test/new#L2")
        self.assertIn("semantic dedup off, using lexical", stderr.getvalue())
        self.assertIn("1 new, 1 folded", stderr.getvalue())


@unittest.skipUnless(_HAVE_CLIENT, "optional ollama-client is not installed")
class OllamaLayer(unittest.TestCase):
    def _serve(self, models, *, unavailable=False):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _Fake)
        srv.models, srv.pulled, srv.unavailable = set(models), [], unavailable
        thread = threading.Thread(target=srv.serve_forever,
                                  kwargs={"poll_interval": 0.01}, daemon=True)
        self.addCleanup(self._close_server, srv, thread)
        thread.start()
        return srv, f"http://127.0.0.1:{srv.server_address[1]}"

    def _close_server(self, srv, thread):
        try:
            if thread.is_alive():
                srv.shutdown()
        finally:
            srv.server_close()
            if thread.ident is not None:
                thread.join(timeout=1)
                self.assertFalse(thread.is_alive(), "fake Ollama server did not stop")

    def test_embed_and_cosine(self):
        srv, url = self._serve({"mxbai-embed-large:latest"})
        d = _load({"OLLAMA_HOST": url})
        self.assertEqual(d._ollama_embed(["ab", "abc"], "mxbai-embed-large"), [[1.0, 2.0], [1.0, 3.0]])
        self.assertEqual(d._ollama_embed([], "x"), [])
        self.assertAlmostEqual(d._cosine([1, 0], [1, 1]), 1 / math.sqrt(2))
        self.assertEqual(d._cosine([0, 0], [1, 1]), 0.0)

    def test_unavailable_raises(self):
        srv, url = self._serve(set(), unavailable=True)
        d = _load({"OLLAMA_HOST": url})
        d_client = d._client()
        d_client.pool.retries = 0
        with self.assertRaises(d.OllamaUnavailable):
            d._ollama_embed(["x"], "mxbai-embed-large")

    def test_missing_model_is_pulled_once(self):
        srv, url = self._serve(set())
        d = _load({"OLLAMA_HOST": url})
        out = d._ollama_embed(["ab"], "mxbai-embed-large")
        self.assertEqual(out, [[1.0, 2.0]])
        self.assertEqual(d._ollama_embed(["abc"], "mxbai-embed-large"), [[1.0, 3.0]])
        self.assertEqual(srv.pulled, ["mxbai-embed-large"])

    def test_hosts_env_failover(self):
        unavailable, unavailable_url = self._serve(set(), unavailable=True)
        srv, url = self._serve({"mxbai-embed-large:latest"})
        d = _load({"OLLAMA_HOST": unavailable_url,
                   "OLLAMA_HOSTS": f"{unavailable_url},{url}"})
        self.assertEqual(len(d.OLLAMA_URLS), 2)
        self.assertEqual(d._ollama_embed(["ab"], "mxbai-embed-large"), [[1.0, 2.0]])


if __name__ == "__main__":
    unittest.main()
