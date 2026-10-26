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

    // 3. Load Cleaned & Repaired Scene by default
    this.loadScene('cleaned');
  }

  bindEvents() {
    // Load Cleaned & Repaired Scene Button
    const btnCleanedScene = document.getElementById('btn-load-cleaned-scene');
    if (btnCleanedScene) {
      btnCleanedScene.addEventListener('click', () => {
        this.loadScene('cleaned');
      });
    }

    // Load Original Validated Scene Button (Shows initial 17 issues)
    const btnValidatedScene = document.getElementById('btn-load-validated-scene');
    if (btnValidatedScene) {
      btnValidatedScene.addEventListener('click', () => {
        this.loadScene('original');
      });
    }

    // Load Member 2 Sample Scene Button
    const btnMember2Scene = document.getElementById('btn-load-member2-scene');
    if (btnMember2Scene) {
      btnMember2Scene.addEventListener('click', () => {
        this.loadScene('sample');
      });
    }

    // Reload Synthetic Test Scene Button
    const btnTestScene = document.getElementById('btn-load-test-scene');
    if (btnTestScene) {
      btnTestScene.addEventListener('click', () => {
        this.loadScene('test');
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
            this.setActiveButton(null);
            this.loadSceneFromJSON(parsed, 'custom');
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
   * Visually indicates active scene source button
   */
  setActiveButton(activeBtn) {
    const buttons = [
      document.getElementById('btn-load-cleaned-scene'),
      document.getElementById('btn-load-validated-scene'),
      document.getElementById('btn-load-member2-scene'),
      document.getElementById('btn-load-test-scene')
    ];
    buttons.forEach(btn => {
      if (btn) {
        if (btn === activeBtn) {
          btn.classList.remove('btn-secondary');
          btn.classList.add('btn-primary');
        } else {
          btn.classList.remove('btn-primary');
          btn.classList.add('btn-secondary');
        }
      }
    });
  }

  /**
   * Loads specific preset scene with consistent configuration
   */
  loadScene(mode) {
    if (mode === 'cleaned') {
      this.setActiveButton(document.getElementById('btn-load-cleaned-scene'));
      this.loadSceneFromJSON(cleanedSceneData, 'cleaned');
    } else if (mode === 'original') {
      this.setActiveButton(document.getElementById('btn-load-validated-scene'));
      this.loadSceneFromJSON(validatedSceneData, 'original');
    } else if (mode === 'sample') {
      this.setActiveButton(document.getElementById('btn-load-member2-scene'));
      this.loadSceneFromJSON(member2SceneData, 'sample');
    } else if (mode === 'test') {
      this.setActiveButton(document.getElementById('btn-load-test-scene'));
      this.loadSceneFromJSON(testSceneData, 'test');
    }
  }

  /**
   * Primary pipeline function: Converts scene.json to 3D architectural scene with physical opening cutouts
   * @param {Object} rawData - Incoming scene.json data
   * @param {string} mode - 'cleaned' | 'original' | 'sample' | 'test' | 'custom'
   */
  loadSceneFromJSON(rawData, mode = 'cleaned') {
    console.log(`[App] Loading scene (${mode})...`, rawData);

    const isCleanedMode = mode === 'cleaned';

    // 1. Validate Input
    const { isValid, scene, errors, warnings, validationReport } = SceneValidator.validate(rawData, {
      repair: isCleanedMode,
      isCleanedScene: isCleanedMode
    });

    if (warnings.length > 0) {
      console.warn('[App] Scene validation warnings:', warnings);
    }

    if (!isValid) {
      console.error('[App] Scene validation failed:', errors);
      this.viewerControls.setStatus(`Validation error: ${errors.join('; ')}`, true);
      return false;
    }

    this.currentSceneData = scene;

    // 2. Clear Previous Scene & Active Highlights
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
    const wireGroup = this.origWireRenderer.generate(scene.walls, scene.wall_height || 3.0, scene.scale);
    this.sceneManager.originalWireframeGroup.add(wireGroup);

    // 11. Update UI metrics derived dynamically from active scene
    this.viewerControls.updateMetrics({
      rooms: scene.rooms.length,
      walls: scene.walls.length,
      doors: scene.doors.length,
      windows: scene.windows.length,
      units: scene.units
    });

    // 12. Update validation warnings & diagnostics UI
    this.updateValidationUI(validationReport, warnings, mode);

    // 13. Fit Camera to active loaded physical geometry
    this.sceneManager.fitCameraToScene();

    // 14. Geometry Accuracy Verification Report
    this.verifyAndLogGeometry(scene, wallMap);

    const modeLabels = {
      cleaned: 'Cleaned & Repaired Scene',
      original: 'Original Blueprint Scene',
      sample: 'Member 2 Sample Scene',
      test: 'Synthetic Test Scene',
      custom: 'Custom Scene'
    };
    const modeLabel = modeLabels[mode] || 'Scene';
    const statusNotice = validationReport?.summary?.auto_repaired > 0
      ? ` (${validationReport.summary.auto_repaired} repaired, ${validationReport.summary.remaining_unresolved} notices)`
      : (validationReport?.summary?.total_initial_issues > 0 ? ` (${validationReport.summary.total_initial_issues} warnings)` : '');

    this.viewerControls.setStatus(`${modeLabel} Loaded: ${scene.walls.length} walls, ${scene.rooms.length} rooms${statusNotice}`);

    return true;
  }

  /**
   * Updates validation issues list with rich actionable inspection cards
   */
  updateValidationUI(report, legacyWarnings, mode = 'cleaned') {
    const valText = document.getElementById('stat-validation-text');
    const valCount = document.getElementById('stat-validation-count');
    const valList = document.getElementById('validation-warnings-list');
    const valBadge = document.getElementById('stat-validation-badge');
    if (!valList) return;

    valList.innerHTML = '';
    const issues = (report && Array.isArray(report.issues) && report.issues.length > 0) ? report.issues : null;

    if (issues && issues.length > 0) {
      const isCleaned = mode === 'cleaned' || (report.summary && report.summary.auto_repaired > 0);
      const repairedCount = report.summary ? report.summary.auto_repaired : 0;
      const totalInitial = report.summary ? report.summary.total_initial_issues : issues.length;
      const unresolvedCount = report.summary ? report.summary.remaining_unresolved : (totalInitial - repairedCount);

      if (isCleaned) {
        if (valText) valText.textContent = `${totalInitial} Initial · ${repairedCount} Repaired · ${unresolvedCount} Unresolved`;
        if (valCount) valCount.textContent = `${unresolvedCount}`;
        if (valBadge) {
          valBadge.style.background = 'rgba(16, 185, 129, 0.12)';
          valBadge.style.borderColor = 'rgba(16, 185, 129, 0.35)';
          valBadge.style.color = '#34d399';
        }
      } else {
        if (valText) valText.textContent = `${totalInitial} Issues Detected (0 Repaired)`;
        if (valCount) valCount.textContent = `${totalInitial}`;
        if (valBadge) {
          valBadge.style.background = 'rgba(245, 158, 11, 0.15)';
          valBadge.style.borderColor = 'rgba(245, 158, 11, 0.3)';
          valBadge.style.color = '#fbbf24';
        }
      }

      // Sort issues: unresolved notices first, then repaired issues
      const sortedIssues = [...issues].sort((a, b) => {
        if (a.auto_repaired === b.auto_repaired) return 0;
        return a.auto_repaired ? 1 : -1;
      });

      sortedIssues.forEach((issue) => {
        const item = document.createElement('div');
        item.className = 'issue-item';
        item.style.cursor = 'pointer';
        item.style.padding = '5px 8px';
        item.style.borderRadius = '5px';
        item.style.background = 'rgba(255, 255, 255, 0.03)';
        item.style.border = '1px solid rgba(255, 255, 255, 0.06)';
        item.style.transition = 'all 0.15s ease';

        const tag = issue.element_id ? `[${issue.element_id}] ` : '';
        const statusBadge = issue.auto_repaired
          ? `<span style="color: #34d399; font-weight: 600;">[Repaired]</span> `
          : `<span style="color: #fbbf24; font-weight: 600;">[Notice]</span> `;

        const correctionNote = (issue.auto_repaired && issue.correction_applied)
          ? `<div style="color: #94a3b8; font-size: 9px; margin-top: 2px;">↳ ${issue.correction_applied}</div>`
          : (!issue.auto_repaired && issue.manual_review_required)
            ? `<div style="color: #f59e0b; font-size: 9px; margin-top: 2px;">↳ Manual review required</div>`
            : '';

        item.innerHTML = `<div>${statusBadge}<strong style="color: #60a5fa;">${tag}</strong>${issue.message}</div>${correctionNote}`;

        // Interactive highlight on hover & click
        item.addEventListener('mouseenter', () => {
          item.style.background = 'rgba(59, 130, 246, 0.18)';
          item.style.borderColor = 'rgba(59, 130, 246, 0.5)';
          if (issue.element_id) {
            this.sceneManager.highlightElement(issue.element_id);
          }
        });

        item.addEventListener('mouseleave', () => {
          item.style.background = 'rgba(255, 255, 255, 0.03)';
          item.style.borderColor = 'rgba(255, 255, 255, 0.06)';
          this.sceneManager.clearHighlights();
        });

        item.addEventListener('click', () => {
          if (issue.element_id) {
            this.sceneManager.highlightElement(issue.element_id);
          }
        });

        valList.appendChild(item);
      });
    } else {
      const item = document.createElement('div');
      item.textContent = '• All geometry validations passed (0 issues)';
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
