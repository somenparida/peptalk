import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// Global state
let scene, camera, renderer, controls;
let modelGroup = new THREE.Group();
let gridHelper, axesHelper;
let inspectMetadata = {};
let selectedObject = null;
let originalMaterial = null;
let initialCameraPos = new THREE.Vector3(8, -10, 8);
let sceneCenter = new THREE.Vector3(0, 0, 0);

const container = document.getElementById('canvas-container');
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

initScene();
loadModelAndMetadata();
setupUIListeners();

function initScene() {
  // 1. Scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x121417);
  scene.add(modelGroup);

  // In Three.js, +Y is usually up by default.
  // We align Three.js coordinate system with our architectural Z-up convention!
  THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

  // 2. Camera
  camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.up.set(0, 0, 1);
  camera.position.copy(initialCameraPos);

  // 3. Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  container.appendChild(renderer.domElement);

  // 4. Controls
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.screenSpacePanning = true;

  // 5. Lights
  const ambLight = new THREE.AmbientLight(0xffffff, 0.7);
  scene.add(ambLight);

  const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.9);
  dirLight1.position.set(10, -10, 15);
  scene.add(dirLight1);

  const dirLight2 = new THREE.DirectionalLight(0x90b0e0, 0.4);
  dirLight2.position.set(-10, 10, -5);
  scene.add(dirLight2);

  // 6. Helpers (Z-up orientation for grid)
  gridHelper = new THREE.GridHelper(30, 30, 0x4f46e5, 0x27272a);
  gridHelper.rotation.x = Math.PI / 2; // Lie flat in XY plane
  gridHelper.position.z = -0.01;
  scene.add(gridHelper);

  axesHelper = new THREE.AxesHelper(3);
  axesHelper.position.z = 0.01;
  scene.add(axesHelper);

  // 7. Event listeners
  window.addEventListener('resize', onWindowResize);
  container.addEventListener('pointerdown', onPointerDown);

  animate();
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

async function loadModelAndMetadata() {
  // Load inspection metadata & report
  try {
    const metaRes = await fetch('/api/inspect');
    inspectMetadata = await metaRes.json();

    const repRes = await fetch('/api/report');
    const repData = await repRes.json();
    populateReportUI(repData);
  } catch (err) {
    console.warn('Could not fetch inspection API:', err);
  }

  // Load GLB Model
  const loader = new GLTFLoader();
  loader.load(
    '/api/model.glb',
    (gltf) => {
      // Clear previous
      while (modelGroup.children.length > 0) {
        modelGroup.remove(modelGroup.children[0]);
      }

      const root = gltf.scene;
      modelGroup.add(root);

      // Analyze bounding box
      const box = new THREE.Box3().setFromObject(root);
      box.getCenter(sceneCenter);
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);

      // Default Ceilings: hidden so user can see inside
      applyLayerVisibility();

      // Fit camera
      fitCameraToScene(sceneCenter, maxDim);
    },
    undefined,
    (error) => {
      console.error('Error loading GLB:', error);
    }
  );
}

function fitCameraToScene(center, size) {
  controls.target.copy(center);
  const dist = size * 1.8;
  camera.position.set(center.x + dist * 0.7, center.y - dist * 0.9, center.z + dist * 0.8);
  camera.lookAt(center);
  controls.update();
  initialCameraPos.copy(camera.position);
}

function populateReportUI(report) {
  if (!report) return;
  document.getElementById('metric-area').textContent = `${report.total_floor_area_m2 || 0} m²`;
  document.getElementById('metric-rooms').textContent = `${report.rooms?.total || 0}`;
  document.getElementById('metric-walls').textContent = `${report.walls?.total || 0}`;
  const totalOpenings = (report.doors?.total || 0) + (report.windows?.total || 0);
  document.getElementById('metric-openings').textContent = `${totalOpenings}`;
}

// Layer visibility controller
function applyLayerVisibility() {
  const showWalls = document.getElementById('toggle-walls').checked;
  const showDoors = document.getElementById('toggle-doors').checked;
  const showWindows = document.getElementById('toggle-windows').checked;
  const showFloors = document.getElementById('toggle-floors').checked;
  const showCeilings = document.getElementById('toggle-ceilings').checked;
  const wireframe = document.getElementById('toggle-wireframe').checked;

  modelGroup.traverse((child) => {
    if (child.isMesh) {
      const name = (child.name || '').toLowerCase();

      // Check category
      if (name.includes('wall') && !name.includes('door') && !name.includes('window')) {
        child.visible = showWalls;
      } else if (name.includes('door')) {
        child.visible = showDoors;
      } else if (name.includes('window')) {
        child.visible = showWindows;
      } else if (name.includes('floor')) {
        child.visible = showFloors;
      } else if (name.includes('ceiling')) {
        child.visible = showCeilings;
      }

      if (child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach((m) => (m.wireframe = wireframe));
        } else {
          child.material.wireframe = wireframe;
        }
      }
    }
  });
}

// Raycasting & Debug Inspector
let downTime = 0;
let downPos = { x: 0, y: 0 };

function onPointerDown(e) {
  downTime = Date.now();
  downPos = { x: e.clientX, y: e.clientY };

  const handlePointerUp = (upEvt) => {
    container.removeEventListener('pointerup', handlePointerUp);
    const dist = Math.hypot(upEvt.clientX - downPos.x, upEvt.clientY - downPos.y);
    const duration = Date.now() - downTime;
    // Only treat as a click if mouse didn't drag extensively
    if (dist < 5 && duration < 300) {
      selectObjectAt(upEvt.clientX, upEvt.clientY);
    }
  };
  container.addEventListener('pointerup', handlePointerUp);
}

function selectObjectAt(clientX, clientY) {
  mouse.x = (clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(clientY / window.innerHeight) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);
  const intersects = raycaster.intersectObjects(modelGroup.children, true);

  // Restore previous selection highlight
  if (selectedObject && originalMaterial) {
    selectedObject.material = originalMaterial;
    selectedObject = null;
    originalMaterial = null;
  }

  // Filter out invisible objects
  const hit = intersects.find((i) => i.object.visible && i.object.isMesh);
  if (!hit) {
    renderEmptyInspector();
    return;
  }

  const obj = hit.object;
  selectedObject = obj;
  originalMaterial = obj.material;

  // Highlight selection with amber glow
  const highlightMat = obj.material.clone();
  highlightMat.emissive = new THREE.Color(0xf59e0b);
  highlightMat.emissiveIntensity = 0.45;
  obj.material = highlightMat;

  // Inspect data
  const nodeKey = obj.name;
  const meta = inspectMetadata[nodeKey] || {
    node_id: nodeKey,
    name: obj.name,
    type: 'Mesh',
    dimensions: {},
    relationships: {},
  };

  renderInspectorData(meta);
}

function renderEmptyInspector() {
  const container = document.getElementById('inspector-content');
  container.innerHTML = `
    <div class="empty-state">
      <p>No element selected</p>
      <small>Click on any wall, floor, door, or window in the 3D scene to inspect dimensions and source coordinates.</small>
    </div>
  `;
}

function renderInspectorData(data) {
  const container = document.getElementById('inspector-content');
  const dims = data.dimensions || {};
  const rels = data.relationships || {};
  const coords = data.source_coordinates || {};

  let dimsRows = Object.entries(dims)
    .map(([k, v]) => `<tr><td class="key">${formatKey(k)}</td><td class="val">${v}</td></tr>`)
    .join('');

  let relsRows = Object.entries(rels)
    .map(([k, v]) => {
      const valStr = Array.isArray(v) ? (v.length ? v.join(', ') : 'None') : v;
      return `<tr><td class="key">${formatKey(k)}</td><td class="val">${valStr}</td></tr>`;
    })
    .join('');

  let coordsRows = Object.entries(coords)
    .map(([k, v]) => `<tr><td class="key">${formatKey(k)}</td><td class="val">${JSON.stringify(v)}</td></tr>`)
    .join('');

  container.innerHTML = `
    <div class="inspect-card">
      <div class="inspect-header">
        <h4 class="inspect-title">${data.name || data.node_id}</h4>
        <span class="inspect-type">${data.type || 'Object'}</span>
      </div>

      <h5 class="subgroup-title">Geometric Dimensions</h5>
      <table class="inspect-table">
        ${dimsRows || '<tr><td colspan="2" class="key">No dimension metadata</td></tr>'}
      </table>

      ${
        relsRows
          ? `
        <h5 class="subgroup-title">Spatial Relationships</h5>
        <table class="inspect-table">${relsRows}</table>
      `
          : ''
      }

      ${
        coordsRows
          ? `
        <h5 class="subgroup-title">Source 2D Coordinates</h5>
        <table class="inspect-table">${coordsRows}</table>
      `
          : ''
      }
    </div>
  `;
}

function formatKey(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/_m2?/g, ' (m)')
    .replace(/_deg/g, ' (°)')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function setupUIListeners() {
  // Layer toggles
  [
    'toggle-walls',
    'toggle-doors',
    'toggle-windows',
    'toggle-floors',
    'toggle-ceilings',
    'toggle-wireframe',
  ].forEach((id) => {
    document.getElementById(id).addEventListener('change', applyLayerVisibility);
  });

  // Helpers toggle
  document.getElementById('toggle-helpers').addEventListener('change', (e) => {
    gridHelper.visible = e.target.checked;
    axesHelper.visible = e.target.checked;
  });

  // Camera presets
  document.getElementById('btn-view-persp').addEventListener('click', () => {
    fitCameraToScene(sceneCenter, 10);
    setActiveBtn('btn-view-persp');
  });

  document.getElementById('btn-view-top').addEventListener('click', () => {
    controls.target.copy(sceneCenter);
    camera.position.set(sceneCenter.x, sceneCenter.y, sceneCenter.z + 18);
    camera.lookAt(sceneCenter);
    controls.update();
    setActiveBtn('btn-view-top');
  });

  document.getElementById('btn-view-reset').addEventListener('click', () => {
    camera.position.copy(initialCameraPos);
    controls.target.copy(sceneCenter);
    controls.update();
    setActiveBtn('btn-view-persp');
  });
}

function setActiveBtn(activeId) {
  ['btn-view-persp', 'btn-view-top'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('active', id === activeId);
  });
}
