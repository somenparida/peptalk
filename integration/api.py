import sys
import shutil
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from integration.pipeline import reconstruct
from integration.adapters import load_ai, load_geometry, load_3d
from integration.validators import validate_input
from integration.config import OUTPUTS_DIR, DATA_DIR

log = logging.getLogger(__name__)

app = FastAPI(
    title="HNX26EPS06 3D Scene Generation API",
    description="Backend service for floor plan 3D reconstruction and GLB model export.",
    version="1.0.0",
)

# Enable CORS for Three.js web viewer integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount outputs directory for static serving (.json, .glb, mask images)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")


@app.get("/health")
def health_check():
    _, ai_impl = load_ai()
    _, geom_impl = load_geometry()
    _, export_impl = load_3d()

    return {
        "status": "ok",
        "implementations": {
            "ai": ai_impl,
            "geometry": geom_impl,
            "3d": export_impl,
        },
    }


@app.post("/reconstruct")
async def api_reconstruct(
    file: UploadFile = File(...),
    mode: str = Form("proposed")
):

    # 1. Upload size check (max 20 MB)
    MAX_SIZE = 20 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds maximum limit of 20MB."
        )

    # 2. Save upload into temporary input directory
    upload_dir = DATA_DIR / "input"
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_input = upload_dir / file.filename

    with open(temp_input, "wb") as f:
        f.write(content)

    # 3. Validate input
    try:
        usable_path, warnings = validate_input(temp_input)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input validation error: {e}"
        )

    # 4. Run pipeline
    try:
        result = reconstruct(usable_path, out_root=OUTPUTS_DIR, mode=mode)
        rep = result["report"]
        return {
            "success": True,
            "scene": f"/outputs/{temp_input.stem}/scene.json",
            "model": f"/outputs/{temp_input.stem}/scene.glb",
            "report": f"/outputs/{temp_input.stem}/report.json",
            "warnings": rep.get("validation", {}).get("warnings", []),
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": str(e),
                "debug": f"/outputs/{temp_input.stem}/",
            },
        )
def get_latest_scene():
    """Return the most recently generated scene.json payload directly as JSON."""
    json_files = sorted(OUTPUTS_DIR.glob("**/scene.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not json_files:
        raise HTTPException(status_code=404, detail="No scene.json generated yet.")
    
    import json
    with open(json_files[0], "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/latest_model")
def get_latest_model():
    """Return the relative URL of the most recently generated scene.glb model."""
    glb_files = sorted(OUTPUTS_DIR.glob("**/scene.glb"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not glb_files:
        raise HTTPException(status_code=404, detail="No scene.glb model generated yet.")
    
    latest_glb = glb_files[0]
    rel_path = latest_glb.relative_to(OUTPUTS_DIR)
    return {
        "model_url": f"/outputs/{rel_path}",
        "plan_name": latest_glb.parent.name,
    }
