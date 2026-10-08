# Member 3 Frontend Integration Guide (Hotspot / LAN Setup)

This guide provides step-by-step instructions for **Member 3 (Frontend / Three.js Viewer)** to connect your Vite + Three.js web application to Member 4's **FastAPI Backend Pipeline** over a shared Wi-Fi or Mobile Hotspot network.

---

## 📶 1. Hotspot Network Setup & Base URL

When connected to the same mobile hotspot / Wi-Fi network:

- **Member 4 Backend Server Host**: `--host 0.0.0.0 --port 8000`
- **Member 4 Backend IP Address**: Replace `<HOTSPOT_IP>` with Member 4's IP (e.g. `10.190.117.218` or `192.168.49.1`)
- **Backend Base URL**: `http://<HOTSPOT_IP>:8000`

### Test Connection from Member 3's Laptop
Open browser or run in terminal:
```bash
curl http://<HOTSPOT_IP>:8000/health
```

Expected Response:
```json
{
  "status": "ok",
  "implementations": {
    "ai": "real",
    "geometry": "real",
    "3d": "real"
  }
}
```

---

## ⚡ 2. Instant Retrieval Endpoints (Fetching Active Scene & Model)

Member 3's frontend can instantly fetch the latest processed `scene.json` or 3D `.glb` model with a single `GET` request:

### A. Fetch Latest Scene JSON Payload
`GET http://<HOTSPOT_IP>:8000/latest_scene`

```javascript
// Fetch latest structured 3D scene JSON directly
async function fetchLatestSceneJson() {
  const response = await fetch("http://<HOTSPOT_IP>:8000/latest_scene");
  const sceneData = await response.json();
  console.log("Latest Scene Data:", sceneData);

  // sceneData.walls, sceneData.doors, sceneData.windows, sceneData.rooms
  return sceneData;
}
```

### B. Fetch Latest 3D GLB Model URL
`GET http://<HOTSPOT_IP>:8000/latest_model`

```javascript
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const gltfLoader = new GLTFLoader();

async function loadLatest3DModel(scene) {
  const res = await fetch("http://<HOTSPOT_IP>:8000/latest_model").then(r => r.json());
  const glbFullUrl = `http://<HOTSPOT_IP>:8000${res.model_url}`;

  gltfLoader.load(
    glbFullUrl,
    (gltf) => {
      scene.add(gltf.scene);
      console.log(`Loaded 3D model for plan: ${res.plan_name}`);
    },
    (progress) => {
      console.log(`Loading GLB: ${(progress.loaded / progress.total * 100).toFixed(1)}%`);
    },
    (error) => {
      console.error("Failed to load GLB over hotspot:", error);
    }
  );
}
```

---

## 📤 3. Uploading & Reconstructing Blueprint Scenes

Member 3's frontend can also upload a floor plan image (`.png`, `.jpg`, `.pdf`), a Member 1 `scene.json` file, or a `.glb` model file directly from the browser:

```javascript
async function uploadAndReconstruct(fileInputObject) {
  const formData = new FormData();
  formData.append("file", fileInputObject);
  formData.append("mode", "proposed");

  const response = await fetch("http://<HOTSPOT_IP>:8000/reconstruct", {
    method: "POST",
    body: formData,
  });

  const result = await response.json();
  console.log("Reconstruction Result:", result);

  // result.model -> "/outputs/<plan_name>/scene.glb"
  // result.scene -> "/outputs/<plan_name>/scene.json"

  // Load the model into Three.js
  const modelUrl = `http://<HOTSPOT_IP>:8000${result.model}`;
  gltfLoader.load(modelUrl, (gltf) => {
    scene.add(gltf.scene);
  });
}
```

---

## 📐 4. Coordinate System & Scale Conventions

- **Units**: `"meters"` (`1 unit = 1 meter`).
- **Wall Height**: Top-level `"wall_height": 2.8` (meters).
- **Coordinate Mapping**: Floor plan `[x, y]` maps to Three.js `[x, height, y]` (where Y-axis is Vertical Up).

---

## 🚀 Commands for Member 4 (Backend Server Host)

Run on Member 4's laptop to start backend server over hotspot:

```bash
# Discover Member 4's Hotspot IP Address
hostname -I

# Start FastAPI backend server listening on all network interfaces
uvicorn integration.api:app --host 0.0.0.0 --port 8000
```
