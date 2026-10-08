# Member 3 Frontend Integration Guide — HNX26EPS06

This guide provides instructions for **Member 3 (Frontend / Three.js Viewer)** to connect your Vite + Three.js web application to the **FastAPI Backend Pipeline**.

---

## ⚡ Backend Server URL & Health Check

- **Base URL**: `http://localhost:8000`
- **CORS Status**: Enabled for all origins (`*`) and ports (including Vite `http://localhost:5173`).

Verify backend status:
```bash
curl http://localhost:8000/health
```

Expected Response:
```json
{
  "status": "ok",
  "implementations": {
    "ai": "real|stub",
    "geometry": "real|stub",
    "3d": "real|stub"
  }
}
```

---

## 📤 1. Uploading & Reconstructing Blueprint Scenes

When a user selects a floor plan image (`.png`, `.jpg`, `.jpeg`, `.pdf`), a Member 1 `.json` file, or a `.glb` model file, send a `multipart/form-data` request to the backend:

```javascript
async function reconstructFloorplan(fileObject) {
  const formData = new FormData();
  formData.append("file", fileObject);
  formData.append("mode", "proposed"); // "proposed" (calibrated) or "baseline"

  const response = await fetch("http://localhost:8000/reconstruct", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Reconstruction failed");
  }

  const result = await response.json();
  console.log("Reconstruction Success:", result);
  
  // result.model -> "/outputs/<plan_name>/scene.glb"
  // result.scene -> "/outputs/<plan_name>/scene.json"
  // result.report -> "/outputs/<plan_name>/report.json"
  
  return result;
}
```

---

## 🎨 2. Loading the Reconstructed 3D Model in Three.js

Use `GLTFLoader` to fetch and display the generated 3D `.glb` file:

```javascript
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const gltfLoader = new GLTFLoader();

function load3DModel(modelRelativePath) {
  const fullGlbUrl = `http://localhost:8000${modelRelativePath}`;

  gltfLoader.load(
    fullGlbUrl,
    (gltf) => {
      // Clear previous scene elements
      scene.add(gltf.scene);
      console.log("3D GLB Model loaded into Three.js scene successfully!");
    },
    (progress) => {
      console.log(`Loading GLB: ${(progress.loaded / progress.total * 100).toFixed(1)}%`);
    },
    (error) => {
      console.error("Error loading GLB model:", error);
    }
  );
}
```

---

## 📐 3. Procedural Scene JSON Spec (`scene.json`)

If your viewer renders procedural geometry directly from `scene.json`:

```javascript
async function loadSceneJson(sceneRelativePath) {
  const fullJsonUrl = `http://localhost:8000${sceneRelativePath}`;
  const sceneData = await fetch(fullJsonUrl).then((res) => res.json());

  const wallHeight = sceneData.wall_height || 2.8;
  const units = sceneData.units; // "meters"

  // Render rooms, walls, doors, windows...
}
```

### Coordinate System Mapping
Convert 2D floor-plan coordinates `[x, y]` into Three.js 3D coordinates `[x, height, y]` (where Y is Vertical Up):

| Floor Plan | Three.js | Description |
|---|---|---|
| **`x`** | **`X`** | Lateral width |
| **`y`** | **`Z`** | Longitudinal depth |
| **Elevation** | **`Y`** | Elevation / Wall height (0.0m to 2.8m) |

---

## 🛠️ Summary of API Response Format

```json
{
  "success": true,
  "scene": "/outputs/demo_01/scene.json",
  "model": "/outputs/demo_01/scene.glb",
  "report": "/outputs/demo_01/report.json",
  "warnings": []
}
```
