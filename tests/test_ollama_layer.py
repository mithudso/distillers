"""Ollama layer of distill_offline.py (runs against an in-process fake Ollama).

Run: .venv/bin/python -m unittest discover -s tests -v   (needs `pip install ollama-client`)
"""
import importlib
import json
import math
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Fake(BaseHTTPRequestHandler):
    models = None  # set per server
    pulled = None

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._send(200, {"models": [{"name": m} for m in self.server.models]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
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
        if self.path == "/api/embeddings":  # legacy endpoint (the client falls back to it after a 404)
            return self._send(200, {"embedding": [1.0, float(len(body["prompt"]))]})
        self._send(404, {})


def _serve(models):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Fake)
    srv.models, srv.pulled = set(models), []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _load(env):
    for k in ("OLLAMA_HOST", "OLLAMA_HOSTS", "OLLAMA_URLS", "OLLAMA_URL"):
        os.environ.pop(k, None)
    os.environ.update(env)
    import distill_offline
    return importlib.reload(distill_offline)


class OllamaLayer(unittest.TestCase):
    def test_embed_and_cosine(self):
        srv, url = _serve({"mxbai-embed-large:latest"})
        d = _load({"OLLAMA_HOST": url})
        self.assertEqual(d._ollama_embed(["ab", "abc"], "mxbai-embed-large"), [[1.0, 2.0], [1.0, 3.0]])
        self.assertEqual(d._ollama_embed([], "x"), [])
        self.assertAlmostEqual(d._cosine([1, 0], [1, 1]), 1 / math.sqrt(2))
        self.assertEqual(d._cosine([0, 0], [1, 1]), 0.0)
        srv.shutdown()

    def test_unavailable_raises(self):
        d = _load({"OLLAMA_HOST": "http://127.0.0.1:9"})
        d_client = d._client()
        d_client.pool.retries = 0
        with self.assertRaises(d.OllamaUnavailable):
            d._ollama_embed(["x"], "mxbai-embed-large")

    def test_missing_model_is_pulled_once(self):
        srv, url = _serve(set())
        d = _load({"OLLAMA_HOST": url})
        out = d._ollama_embed(["ab"], "mxbai-embed-large")
        self.assertEqual(out, [[1.0, 2.0]])
        self.assertEqual(srv.pulled, ["mxbai-embed-large"])
        srv.shutdown()

    def test_hosts_env_failover(self):
        srv, url = _serve({"mxbai-embed-large:latest"})
        d = _load({"OLLAMA_HOST": "http://127.0.0.1:9", "OLLAMA_HOSTS": f"http://127.0.0.1:9,{url}"})
        self.assertEqual(len(d.OLLAMA_URLS), 2)
        self.assertEqual(d._ollama_embed(["ab"], "mxbai-embed-large"), [[1.0, 2.0]])
        srv.shutdown()

    def test_default_model_pinned(self):
        d = _load({"OLLAMA_HOST": "http://127.0.0.1:9"})
        self.assertEqual(d.DEFAULT_EMBED_MODEL, "mxbai-embed-large")


if __name__ == "__main__":
    unittest.main()
