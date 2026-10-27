"""Unit test for local Three.js viewer server."""

import urllib.request
from pathlib import Path
import pytest

from src.viewer.server import start_viewer_server


def test_viewer_server_non_blocking(tmp_path: Path):
    # Create dummy GLB
    dummy_glb = tmp_path / "dummy.glb"
    dummy_glb.write_bytes(b"glTF\x02\x00\x00\x00")

    server, port = start_viewer_server(
        glb_path=dummy_glb,
        port=9123,
        open_browser=False,
        block=False,
    )

    try:
        url = f"http://localhost:{port}/index.html"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            content = resp.read().decode("utf-8")
            assert "HNX26EPS06" in content
            assert "Three.js" in content or "three" in content

        # Request /model.glb
        glb_url = f"http://localhost:{port}/model.glb"
        with urllib.request.urlopen(glb_url) as resp:
            assert resp.status == 200
            assert resp.read() == b"glTF\x02\x00\x00\x00"

    finally:
        server.shutdown()
        server.server_close()
