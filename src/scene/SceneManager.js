import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export class SceneManager {
  constructor(container) {
    this.container = container;
    
    // Core Three.js components
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    
    // Lighting & Helpers
    this.ambientLight = null;
    this.dirLight = null;
    this.hemiLight = null;
    this.gridHelper = null;
    
    // Group hierarchy for architectural components
    this.rootGroup = null;
    this.wallsGroup = null;
    this.floorGroup = null;
    this.doorsGroup = null;
    this.windowsGroup = null;
    this.roomsGroup = null;
    this.dimensionsGroup = null;
    this.labelsGroup = null;
    
    // State & Animation
    this.animationFrameId = null;
    this.is2DView = false;
    this.fpsCounter = {
      frames: 0,
      lastTime: performance.now(),
      fps: 60
    };
    
    this.init();
  }

  init() {
    // 1. Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0d13);

    // 2. Camera: Perspective by default
    const width = this.container.clientWidth || window.innerWidth;
    const height = this.container.clientHeight || window.innerHeight;
    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    this.camera.position.set(10, 12, 14);

    // 3. WebGL Renderer
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      powerPreference: 'high-performance'
    });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.container.appendChild(this.renderer.domElement);

    // 4. Orbit Controls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    this.controls.screenSpacePanning = true;
    this.controls.target.set(3, 0, 2); // sensible default center near test room
    this.controls.update();

    // 5. Lighting
    this.ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    this.scene.add(this.ambientLight);

    this.hemiLight = new THREE.HemisphereLight(0xffffff, 0x334155, 0.4);
    this.hemiLight.position.set(0, 50, 0);
    this.scene.add(this.hemiLight);

    this.dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    this.dirLight.position.set(15, 25, 15);
    this.dirLight.castShadow = true;
    this.dirLight.shadow.mapSize.width = 2048;
    this.dirLight.shadow.mapSize.height = 2048;
    this.dirLight.shadow.camera.near = 0.5;
    this.dirLight.shadow.camera.far = 100;
    const d = 15;
    this.dirLight.shadow.camera.left = -d;
    this.dirLight.shadow.camera.right = d;
    this.dirLight.shadow.camera.top = d;
    this.dirLight.shadow.camera.bottom = -d;
    this.dirLight.shadow.bias = -0.0005;
    this.scene.add(this.dirLight);

    // 6. Grid Helper (XZ Plane: floor level Y = 0)
    // 30m x 30m grid, 1m intervals for accurate architectural context
    this.gridHelper = new THREE.GridHelper(30, 30, 0x3b82f6, 0x1e293b);
    this.gridHelper.position.y = -0.001; // tiny offset to prevent z-fighting with floor
    this.scene.add(this.gridHelper);

    // 7. Architectural Hierarchical Groups
    this.rootGroup = new THREE.Group();
    this.rootGroup.name = 'ReconstructedScene';
    this.scene.add(this.rootGroup);

    this.wallsGroup = new THREE.Group();
    this.wallsGroup.name = 'Walls';
    this.rootGroup.add(this.wallsGroup);

    this.floorGroup = new THREE.Group();
    this.floorGroup.name = 'Floors';
    this.rootGroup.add(this.floorGroup);

    this.doorsGroup = new THREE.Group();
    this.doorsGroup.name = 'Doors';
    this.rootGroup.add(this.doorsGroup);

    this.windowsGroup = new THREE.Group();
    this.windowsGroup.name = 'Windows';
    this.rootGroup.add(this.windowsGroup);

    this.roomsGroup = new THREE.Group();
    this.roomsGroup.name = 'Rooms';
    this.rootGroup.add(this.roomsGroup);

    this.dimensionsGroup = new THREE.Group();
    this.dimensionsGroup.name = 'Dimensions';
    this.rootGroup.add(this.dimensionsGroup);

    this.labelsGroup = new THREE.Group();
    this.labelsGroup.name = 'Labels';
    this.rootGroup.add(this.labelsGroup);

    // 8. Event Listeners (Resize)
    this.onWindowResize = this.onWindowResize.bind(this);
    window.addEventListener('resize', this.onWindowResize);

    // 9. Animation Loop
    this.animate = this.animate.bind(this);
    this.animate();
  }

  onWindowResize() {
    if (!this.container || !this.renderer || !this.camera) return;
    const width = this.container.clientWidth || window.innerWidth;
    const height = this.container.clientHeight || window.innerHeight;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  animate() {
    this.animationFrameId = requestAnimationFrame(this.animate);

    // Update orbit controls damping
    if (this.controls) {
      this.controls.update();
    }

    // Measure FPS
    this.fpsCounter.frames++;
    const now = performance.now();
    if (now >= this.fpsCounter.lastTime + 1000) {
      this.fpsCounter.fps = Math.round((this.fpsCounter.frames * 1000) / (now - this.fpsCounter.lastTime));
      this.fpsCounter.frames = 0;
      this.fpsCounter.lastTime = now;
      const fpsEl = document.getElementById('render-fps');
      if (fpsEl) {
        fpsEl.textContent = `${this.fpsCounter.fps} FPS`;
      }
    }

    // Render 3D scene
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  /**
   * Resets the camera to overview perspective
   */
  resetCamera() {
    this.fitCameraToScene();
  }

  /**
   * Fits camera view intelligently based on scene bounding box
   */
  fitCameraToScene() {
    // Compute bounding box of root architectural group
    const box = new THREE.Box3().setFromObject(this.rootGroup);
    
    // If empty, use a default 6x4 bounding box (matching test room)
    if (box.isEmpty()) {
      box.min.set(0, 0, 0);
      box.max.set(6, 3, 4);
    }

    const center = new THREE.Vector3();
    box.getCenter(center);

    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z, 5);

    // Set controls target to geometry center
    this.controls.target.copy(center);

    if (this.is2DView) {
      // Top down view
      this.camera.position.set(center.x, maxDim * 2.2, center.z + 0.001);
    } else {
      // Isometric 3D angle
      const distance = maxDim * 1.8;
      this.camera.position.set(
        center.x + distance * 0.7,
        center.y + distance * 0.8,
        center.z + distance * 0.9
      );
    }

    this.camera.lookAt(center);
    this.controls.update();
  }

  /**
   * Toggle between 3D perspective and Top-Down 2D floorplan view
   */
  toggle2D3DView() {
    this.is2DView = !this.is2DView;
    this.fitCameraToScene();
    return this.is2DView;
  }

  /**
   * Toggles visibility of specific layer groups
   */
  setLayerVisibility(layerName, visible) {
    const groups = {
      walls: this.wallsGroup,
      floor: this.floorGroup,
      doors: this.doorsGroup,
      windows: this.windowsGroup,
      rooms: this.roomsGroup,
      dimensions: this.dimensionsGroup,
      labels: this.labelsGroup
    };

    if (groups[layerName]) {
      groups[layerName].visible = visible;
    }
  }

  /**
   * Clears all reconstructed geometry
   */
  clearReconstruction() {
    const groups = [
      this.wallsGroup,
      this.floorGroup,
      this.doorsGroup,
      this.windowsGroup,
      this.roomsGroup,
      this.dimensionsGroup,
      this.labelsGroup
    ];

    groups.forEach(group => {
      while (group.children.length > 0) {
        const obj = group.children[0];
        group.remove(obj);
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) {
            obj.material.forEach(m => m.dispose());
          } else {
            obj.material.dispose();
          }
        }
      }
    });
  }

  dispose() {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
    window.removeEventListener('resize', this.onWindowResize);
    if (this.controls) this.controls.dispose();
    if (this.renderer) {
      this.renderer.dispose();
      if (this.renderer.domElement && this.renderer.domElement.parentNode) {
        this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
      }
    }
  }
}
