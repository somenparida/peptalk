"""
Local HTTP Server for the Member 2 3D Scene Viewer.
Serves the Three.js web application and provides API endpoints for scene data and GLB models.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

from geometry.validator import SceneValidator
from geometry.scene_graph import SceneGraph
from geometry.exporter import SceneExporter


STATIC_DIR = Path(__file__).parent / "static"


class ViewerHandler(SimpleHTTPRequestHandler):
    """Handles static files and API requests for the 3D Viewer."""

    # Injected by server runner
    current_scene_path: Optional[Path] = None
    cached_glb_bytes: Optional[bytes] = None
    cached_metadata: Optional[dict] = None
    cached_report: Optional[dict] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        url_path = self.path.split("?")[0]

        if url_path == "/api/model.glb":
            if self.cached_glb_bytes is None:
                self.send_error(404, "No model generated")
                return
            self.send_response(200)
            self.send_header("Content-Type", "model/gltf-binary")
            self.send_header("Content-Length", str(len(self.cached_glb_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(self.cached_glb_bytes)
            return

        elif url_path == "/api/inspect":
            data = json.dumps(self.cached_metadata or {}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
            return

        elif url_path == "/api/report":
            data = json.dumps(self.cached_report or {}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
            return

        return super().do_GET()

    def end_headers(self):
        # Enable CORS and disable aggressive caching for local dev
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def start_viewer(scene_path: Path, port: int = 8080, open_browser: bool = True):
    """Builds scene geometry and starts local viewer HTTP server."""
    scene_path = Path(scene_path).resolve()
    if not scene_path.exists():
        raise FileNotFoundError(f"Scene file not found: {scene_path}")

    with open(scene_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    v_res = SceneValidator.validate_raw_json(raw_data)
    if not v_res.is_valid:
        print("\n[VALIDATION ERRORS IN SCENE]:")
        for err in v_res.errors:
            print(f"  - {err}")
        sys.exit(1)

    print(f"Generating 3D scene from {scene_path.name}...")
    sg = SceneGraph.from_specification(v_res.spec)
    trimesh_scene = sg.to_trimesh_scene()
    glb_bytes = trimesh_scene.export(file_type="glb")

    ViewerHandler.current_scene_path = scene_path
    ViewerHandler.cached_glb_bytes = glb_bytes
    ViewerHandler.cached_metadata = sg.get_inspection_metadata()
    ViewerHandler.cached_report = v_res.report

    server_address = ("", port)
    try:
        httpd = HTTPServer(server_address, ViewerHandler)
    except OSError:
        # If port 8080 is taken, try port 8081
        port = port + 1
        server_address = ("", port)
        httpd = HTTPServer(server_address, ViewerHandler)

    url = f"http://localhost:{port}/"
    print(f"\n=======================================================")
    print(f"  3D Scene Viewer running at: {url}")
    print(f"  Visual Debug Mode: ACTIVE")
    print(f"  Press Ctrl+C to stop the server")
    print(f"=======================================================\n")

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping viewer server...")
        httpd.server_close()
