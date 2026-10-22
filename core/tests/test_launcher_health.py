"""Offline launcher probe: localhost only, bounded, no PowerShell/browser."""
import importlib.util
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest


def test_health_probe_rejects_wrong_service_and_accepts_genesis(monkeypatch):
    script = Path(__file__).resolve().parents[2] / "deploy/installer/Check-GenesisCore.py"
    spec = importlib.util.spec_from_file_location("launcher_health", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Handler(BaseHTTPRequestHandler):
        status = b'{"status":"not-genesis"}'

        def do_GET(self):
            assert self.path == "/health"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(self.status)

        def log_message(self, *_args):
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            monkeypatch.setattr(module, "HEALTH_URL", f"http://127.0.0.1:{server.server_port}/health")
            assert not module.wait_for_core(1)
            Handler.status = b'{"status":"ok"}'
            assert not module.wait_for_core(1)  # zufaelliger Dienst, nicht GENESIS
            Handler.status = b'{"status":"ok","app":"GENESIS Media Manager"}'
            assert module.wait_for_core(1)
            with pytest.raises(ValueError):
                module.wait_for_core(61)
        finally:
            server.shutdown()
            thread.join(timeout=2)
