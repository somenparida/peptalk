export class ViewerControls {
  constructor(sceneManager) {
    this.sceneManager = sceneManager;
    this.init();
  }

  init() {
    // 1. Reset Camera Button
    const btnResetCam = document.getElementById('btn-reset-cam');
    if (btnResetCam) {
      btnResetCam.addEventListener('click', () => {
        this.sceneManager.resetCamera();
      });
    }

    // 2. Toggle 2D / 3D View Button
    const btnToggleView = document.getElementById('btn-toggle-view');
    if (btnToggleView) {
      btnToggleView.addEventListener('click', () => {
        const is2D = this.sceneManager.toggle2D3DView();
        btnToggleView.innerHTML = is2D 
          ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg> Perspective (3D)`
          : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg> Top-Down (2D)`;
      });
    }

    // 3. Layer Visibility Toggles
    const layerIds = ['walls', 'floor', 'doors', 'windows', 'labels', 'dimensions'];
    layerIds.forEach(id => {
      const checkbox = document.getElementById(`toggle-${id}`);
      const chip = document.getElementById(`chip-${id}`);
      if (checkbox) {
        checkbox.addEventListener('change', (e) => {
          const visible = e.target.checked;
          this.sceneManager.setLayerVisibility(id, visible);
          if (chip) {
            chip.classList.toggle('active', visible);
          }
        });
      }
    });
  }

  updateMetrics({ rooms = 0, walls = 0, doors = 0, windows = 0, units = 'meters' }) {
    const elRooms = document.getElementById('stat-rooms');
    const elWalls = document.getElementById('stat-walls');
    const elDoors = document.getElementById('stat-doors');
    const elWindows = document.getElementById('stat-windows');
    const elUnits = document.getElementById('stat-units');

    if (elRooms) elRooms.textContent = rooms;
    if (elWalls) elWalls.textContent = walls;
    if (elDoors) elDoors.textContent = doors;
    if (elWindows) elWindows.textContent = windows;
    if (elUnits) elUnits.textContent = units;
  }

  setStatus(message, isError = false) {
    const statusEl = document.getElementById('engine-status');
    if (statusEl) {
      statusEl.textContent = message;
      statusEl.style.color = isError ? '#ef4444' : '#94a3b8';
    }
  }
}
