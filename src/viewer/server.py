"""Local HTTP server for interactive Three.js 3D architectural viewer."""

from __future__ import annotations

import functools
import http.server
import json
import os
from pathlib import Path
import socketserver
import threading
import webbrowser
from typing import Optional, Tuple


class ArchitecturalViewerHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler serving web assets and redirecting active model GLB."""

    glb_path: Optional[Path] = None
    web_dir: Path = Path(__file__).parent / "web"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.web_dir), **kwargs)

    def do_GET(self) -> None:
        # Route /model.glb or /scene.glb to the target file if specified
        if self.path.split("?")[0] in ("/model.glb", "/scene.glb") and self.glb_path and self.glb_path.exists():
            self.send_response(200)
            self.send_header("Content-Type", "model/gltf-binary")
            self.send_header("Content-Length", str(self.glb_path.stat().st_size))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(self.glb_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # Route /metadata.json
        if self.path.split("?")[0] in ("/metadata.json", "/scene_metadata.json"):
            candidates = []
            if self.glb_path:
                candidates.extend([
                    self.glb_path.with_name(f"{self.glb_path.stem}_metadata.json"),
                    self.glb_path.with_name("metadata.json"),
                ])
            candidates.append(self.web_dir / "metadata.json")
            for meta_path in candidates:
                if meta_path.exists():
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(meta_path.stat().st_size))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    with open(meta_path, "rb") as f:
                        self.wfile.write(f.read())
                    return

        return super().do_GET()


def start_viewer_server(
    glb_path: Optional[str | Path] = None,
    port: int = 8080,
    open_browser: bool = True,
    block: bool = True,
) -> Tuple[socketserver.TCPServer, int]:
    """Starts local server and opens browser."""
    ArchitecturalViewerHandler.glb_path = Path(glb_path) if glb_path else None

    # Try ports if selected port is occupied
    actual_port = port
    server = None
    for offset in range(10):
        try:
            actual_port = port + offset
            server = socketserver.TCPServer(("", actual_port), ArchitecturalViewerHandler)
            break
        except OSError:
            continue

    if server is None:
        raise RuntimeError(f"Could not bind to any port from {port} to {port + 9}")

    url = f"http://localhost:{actual_port}/"
    print(f"\n=======================================================")
    print(f"[VIEWER] HNX26EPS06 3D Architectural Viewer Running at:")
    print(f"   {url}")
    if glb_path:
        print(f"   Active Scene: {glb_path}")
    print(f"=======================================================\n")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    if block:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down viewer server...")
            server.server_close()
    else:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

    return server, actual_port
