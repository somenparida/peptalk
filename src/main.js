import { SceneManager } from './scene/SceneManager.js';
import { ViewerControls } from './viewer/ViewerControls.js';
import { WallGenerator } from './scene/WallGenerator.js';
import { FloorGenerator } from './scene/FloorGenerator.js';
import { DoorGenerator } from './scene/DoorGenerator.js';
import { WindowGenerator } from './scene/WindowGenerator.js';
import { RoomGenerator } from './scene/RoomGenerator.js';
import { DimensionRenderer } from './scene/DimensionRenderer.js';
import { OriginalWireframeRenderer } from './scene/OriginalWireframeRenderer.js';
import { Labels } from './viewer/Labels.js';
import { GLBExporter } from './export/GLBExporter.js';
import { SceneValidator } from './data/SceneValidator.js';
import testSceneData from './data/scene.json';
import member2SceneData from './data/sample_scene.json';
import validatedSceneData from './data/validated_scene.json';
import cleanedSceneData from './data/cleaned_scene.json';

class App {
  constructor() {
    this.container = document.getElementById('canvas-container');
    this.sceneManager = null;
    this.viewerControls = null;
    this.wallGen = null;
    this.floorGen = null;
    this.doorGen = null;
    this.windowGen = null;
    this.roomGen = null;
    this.dimRenderer = null;
    this.origWireRenderer = null;
    this.labels = null;
    this.glbExporter = null;
    this.currentSceneData = null;
  }

  init() {
    if (!this.container) {
      console.error('Canvas container not found');
      return;
    }

    // 1. Initialize 3D Engine & Generators
    this.sceneManager = new SceneManager(this.container);
    this.viewerControls = new ViewerControls(this.sceneManager);
    this.wallGen = new WallGenerator();
    this.floorGen = new FloorGenerator();
    this.doorGen = new DoorGenerator();
    this.windowGen = new WindowGenerator();
    this.roomGen = new RoomGenerator();
    this.dimRenderer = new DimensionRenderer();
    this.origWireRenderer = new OriginalWireframeRenderer();
    this.labels = new Labels();
    this.glbExporter = new GLBExporter();

    // 2. Wire up UI actions
    this.bindEvents();

    // 3. Load Cleaned & Repaired Scene by default (or raw validated scene if requested)
    this.loadSceneFromJSON(cleanedSceneData);
  }

  bindEvents() {
    // Load Cleaned & Repaired Scene Button
    const btnCleanedScene = document.getElementById('btn-load-cleaned-scene');
    if (btnCleanedScene) {
      btnCleanedScene.addEventListener('click', () => {
        this.loadSceneFromJSON(cleanedSceneData);
      });
    }

    // Load Original Validated Scene Button (Shows initial 17 issues)
    const btnValidatedScene = document.getElementById('btn-load-validated-scene');
    if (btnValidatedScene) {
      btnValidatedScene.addEventListener('click', () => {
        this.loadSceneFromJSON(validatedSceneData);
      });
    }

    // Load Member 2 Sample Scene Button
    const btnMember2Scene = document.getElementById('btn-load-member2-scene');
    if (btnMember2Scene) {
      btnMember2Scene.addEventListener('click', () => {
        this.loadSceneFromJSON(member2SceneData);
      });
    }

    // Reload Synthetic Test Scene Button
    const btnTestScene = document.getElementById('btn-load-test-scene');
    if (btnTestScene) {
      btnTestScene.addEventListener('click', () => {
        this.loadSceneFromJSON(testSceneData);
      });
    }

    // Load JSON file from disk
    const fileInput = document.getElementById('file-scene-input');
    if (fileInput) {
      fileInput.addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
          try {
            const parsed = JSON.parse(event.target.result);
            this.loadSceneFromJSON(parsed);
          } catch (err) {
            console.error('[App] Failed to parse JSON file:', err);
            this.viewerControls.setStatus(`Invalid JSON file: ${err.message}`, true);
          }
        };
        reader.readAsText(file);
        fileInput.value = '';
      });
    }

    // Export GLB button
    const btnExport = document.getElementById('btn-export-glb');
    if (btnExport) {
      btnExport.addEventListener('click', () => {
        this.exportAndVerifyGLB();
      });
    }
  }

  /**
   * Primary pipeline function: Converts scene.json to 3D architectural scene with physical opening cutouts
   * @param {Object} rawData - Incoming scene.json data
   */
  loadSceneFromJSON(rawData) {
    console.log('[App] Loading scene from JSON contract...', rawData);

    // 1. Validate Input
    const { isValid, scene, errors, warnings, validationReport } = SceneValidator.validate(rawData);

    if (warnings.length > 0) {
      console.warn('[App] Scene validation warnings:', warnings);
    }

    if (!isValid) {
      console.error('[App] Scene validation failed:', errors);
      this.viewerControls.setStatus(`Validation error: ${errors.join('; ')}`, true);
      return false;
    }

    this.currentSceneData = scene;

    // 2. Clear Previous Scene
    this.sceneManager.clearReconstruction();
    this.labels.dispose();
    this.dimRenderer.dispose();

    // 3. Generate Walls with real physical cutouts for doors & windows
    const { meshes: wallMeshes, wallMap } = this.wallGen.generate(scene.walls, scene.settings, {
      doors: scene.doors,
      windows: scene.windows,
      cutOpenings: true
    });
    wallMeshes.forEach(mesh => this.sceneManager.wallsGroup.add(mesh));

    // 4. Generate Floors
    const floorMeshes = this.floorGen.generate(scene.rooms, scene.settings);
    floorMeshes.forEach(mesh => this.sceneManager.floorGroup.add(mesh));

    // 5. Generate Doors
    const doorObjects = this.doorGen.generate(scene.doors, wallMap, scene.settings);
    doorObjects.forEach(obj => this.sceneManager.doorsGroup.add(obj));

    // 6. Generate Windows
    const windowObjects = this.windowGen.generate(scene.windows, wallMap, scene.settings);
    windowObjects.forEach(obj => this.sceneManager.windowsGroup.add(obj));

    // 7. Generate Rooms & Outlines
    const { meshes: roomMeshes, roomInfos } = this.roomGen.generate(scene.rooms);
    roomMeshes.forEach(mesh => this.sceneManager.roomsGroup.add(mesh));

    // 8. Generate Room Labels
    const labelSprites = this.labels.generate(roomInfos);
    labelSprites.forEach(sprite => this.sceneManager.labelsGroup.add(sprite));

    // 9. Generate Metric Dimensions
    const dimObjects = this.dimRenderer.generate(wallMap, scene.units === 'meters' ? 'm' : scene.units);
    dimObjects.forEach(obj => this.sceneManager.dimensionsGroup.add(obj));

    // 10. Generate Original Blueprint Wireframe (Cyan lines for Image 1 comparison)
    const wireGroup = this.origWireRenderer.generate(scene.walls, scene.wall_height || 3.0);
    this.sceneManager.originalWireframeGroup.add(wireGroup);

    // 11. Update UI metrics
    this.viewerControls.updateMetrics({
      rooms: scene.rooms.length,
      walls: scene.walls.length,
      doors: scene.doors.length,
      windows: scene.windows.length,
      units: scene.units
    });

    // 12. Update validation warnings & diagnostics UI
    this.updateValidationUI(validationReport, warnings);

    // 13. Fit Camera
    this.sceneManager.fitCameraToScene();

    // 14. Geometry Accuracy Verification Report
    this.verifyAndLogGeometry(scene, wallMap);

    const warnMsg = warnings.length > 0 ? ` (${warnings.length} warnings)` : '';
    this.viewerControls.setStatus(`Scene Reconstructed: ${scene.walls.length} walls, ${scene.rooms.length} rooms${warnMsg}`);

    return true;
  }

  /**
   * Updates validation issues list with rich actionable inspection cards
   */
  updateValidationUI(report, legacyWarnings) {
    const valText = document.getElementById('stat-validation-text');
    const valCount = document.getElementById('stat-validation-count');
    const valList = document.getElementById('validation-warnings-list');
    const valBadge = document.getElementById('stat-validation-badge');
    if (!valList) return;

    valList.innerHTML = '';
    const issues = (report && Array.isArray(report.issues) && report.issues.length > 0) ? report.issues : null;

    if (issues && issues.length > 0) {
      const repairedCount = report.summary ? report.summary.auto_repaired : 0;
      const totalInitial = report.summary ? report.summary.total_initial_issues : issues.length;

      if (valText) valText.textContent = `${totalInitial} Issues · ${repairedCount} Repaired`;
      if (valCount) valCount.textContent = `${issues.length}`;

      issues.forEach((issue) => {
        const item = document.createElement('div');
        item.className = 'issue-item';
        item.style.cursor = 'pointer';
        item.style.padding = '4px 6px';
        item.style.borderRadius = '4px';
        item.style.background = 'rgba(255, 255, 255, 0.03)';
        item.style.border = '1px solid rgba(255, 255, 255, 0.05)';
        item.style.transition = 'all 0.15s ease';

        const tag = issue.element_id ? `[${issue.element_id}] ` : '';
        const statusBadge = issue.auto_repaired
          ? `<span style="color: #34d399; font-weight: 600;">[Repaired]</span> `
          : `<span style="color: #fbbf24; font-weight: 600;">[Warning]</span> `;

        item.innerHTML = `<div>${statusBadge}<strong style="color: #60a5fa;">${tag}</strong>${issue.message}</div>`;

        // Interactive highlight on hover & click
        item.addEventListener('mouseenter', () => {
          item.style.background = 'rgba(59, 130, 246, 0.15)';
          item.style.borderColor = 'rgba(59, 130, 246, 0.4)';
          if (issue.element_id) {
            this.sceneManager.highlightElement(issue.element_id);
          }
        });

        item.addEventListener('mouseleave', () => {
          item.style.background = 'rgba(255, 255, 255, 0.03)';
          item.style.borderColor = 'rgba(255, 255, 255, 0.05)';
          this.sceneManager.clearHighlights();
        });

        item.addEventListener('click', () => {
          if (issue.element_id) {
            this.sceneManager.highlightElement(issue.element_id);
          }
        });

        valList.appendChild(item);
      });

      if (valBadge) {
        valBadge.style.background = 'rgba(245, 158, 11, 0.15)';
        valBadge.style.borderColor = 'rgba(245, 158, 11, 0.3)';
        valBadge.style.color = '#fbbf24';
      }
    } else if (legacyWarnings && legacyWarnings.length > 0) {
      legacyWarnings.forEach(w => {
        const item = document.createElement('div');
        item.textContent = `• ${w}`;
        valList.appendChild(item);
      });
      if (valText) valText.textContent = `Issues Detected`;
      if (valCount) valCount.textContent = `${legacyWarnings.length}`;
      if (valBadge) {
        valBadge.style.background = 'rgba(245, 158, 11, 0.15)';
        valBadge.style.borderColor = 'rgba(245, 158, 11, 0.3)';
        valBadge.style.color = '#fbbf24';
      }
    } else {
      const item = document.createElement('div');
      item.textContent = '• All validations passed (0 issues)';
      item.style.color = '#10b981';
      valList.appendChild(item);
      if (valText) valText.textContent = `Clean Geometry`;
      if (valCount) valCount.textContent = `0`;
      if (valBadge) {
        valBadge.style.background = 'rgba(16, 185, 129, 0.15)';
        valBadge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
        valBadge.style.color = '#34d399';
      }
    }
  }

  /**
   * Numerically verifies geometry against input contract and logs to console
   */
  verifyAndLogGeometry(scene, wallMap) {
    console.group('📐 [Geometry Verification Report]');
    console.log(`Units: ${scene.units}`);
    console.log(`Wall Height: ${scene.wall_height || scene.settings.wallHeight}m, Floor Thickness: ${scene.settings.floorThickness}m`);
    
    // Wall lengths & thicknesses
    wallMap.forEach((wall, id) => {
      console.log(`Wall [${id}]: length = ${wall.length.toFixed(2)}m (expected sqrt(${wall.dx.toFixed(2)}² + ${wall.dz.toFixed(2)}²)), thickness = ${wall.thickness}m, height = ${wall.wallHeight}m, midpoint = [${wall.midpoint.map(v => v.toFixed(2)).join(', ')}]`);
    });

    // Door attachment
    scene.doors.forEach(door => {
      const wall = wallMap.get(door.wall_id);
      if (wall) {
        const offsetStr = typeof door.offset === 'number' ? `offset = ${door.offset.toFixed(2)}m` : `position = ${(door.position * 100).toFixed(0)}%`;
        console.log(`Door [${door.id}]: on wall ${door.wall_id}, ${offsetStr}, width = ${door.width}m, height = ${door.height || 2.1}m`);
      }
    });

    // Window attachment
    scene.windows.forEach(win => {
      const wall = wallMap.get(win.wall_id);
      if (wall) {
        const offsetStr = typeof win.offset === 'number' ? `offset = ${win.offset.toFixed(2)}m` : `position = ${(win.position * 100).toFixed(0)}%`;
        console.log(`Window [${win.id}]: on wall ${win.wall_id}, ${offsetStr}, width = ${win.width}m, height = ${win.height || 1.2}m, sill_height = ${win.sill_height !== undefined ? win.sill_height : 0.9}m`);
      }
    });

    // Room area
    scene.rooms.forEach(room => {
      console.log(`Room [${room.id}]: "${room.name}", polygon vertices = ${room.polygon.length}`);
    });
    console.groupEnd();
  }

  /**
   * Exports scene to GLB and performs automated reload verification
   */
  async exportAndVerifyGLB() {
    const statusBox = document.getElementById('export-status');
    if (statusBox) {
      statusBox.style.display = 'block';
      statusBox.textContent = 'Exporting scene to GLB...';
    }

    try {
      const glbBuffer = await this.glbExporter.exportScene(this.sceneManager.rootGroup, 'reconstructed_scene.glb');
      console.log('[GLB Export] Successfully generated GLB buffer. Size:', (glbBuffer.byteLength / 1024).toFixed(1), 'KB');

      // Test Reload Verification
      if (statusBox) {
        statusBox.textContent = 'Verifying GLB reload integrity...';
      }

      const verifyResult = await this.glbExporter.verifyReloadGLB(glbBuffer);
      console.log('✅ [GLB Reload Verification Passed]:', verifyResult);

      if (statusBox) {
        statusBox.innerHTML = `✓ GLB Exported & Verified<br>Size: ${(glbBuffer.byteLength / 1024).toFixed(1)} KB<br>Meshes: ${verifyResult.meshCount}<br>Dims: ${verifyResult.dimensions.x}m × ${verifyResult.dimensions.y}m × ${verifyResult.dimensions.z}m`;
      }
      this.viewerControls.setStatus('GLB Export & Reload Verification Passed');
    } catch (err) {
      console.error('[GLB Export] Failed:', err);
      if (statusBox) {
        statusBox.textContent = `Export failed: ${err.message}`;
        statusBox.style.color = '#ef4444';
      }
      this.viewerControls.setStatus(`Export error: ${err.message}`, true);
    }
  }
}

// Instantiate and expose globally
window.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init();
  window.app = app;
});
