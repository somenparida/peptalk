import * as THREE from 'three';

export class WindowGenerator {
  constructor(options = {}) {
    this.defaultHeight = options.defaultHeight || 1.2;
    this.defaultSillHeight = options.defaultSillHeight || 1.0;

    // Architectural glass material (clean, lightweight, transparent)
    this.glassMaterial = new THREE.MeshStandardMaterial({
      color: 0x7dd3fc, // Sky cyan architectural glass
      transparent: true,
      opacity: 0.45,
      roughness: 0.1,
      metalness: 0.2,
      side: THREE.DoubleSide
    });

    // Window frame casing material
    this.frameMaterial = new THREE.MeshStandardMaterial({
      color: 0x334155, // Dark slate aluminum casing
      roughness: 0.5,
      metalness: 0.3
    });
  }

  /**
   * Generates 3D windows attached to their corresponding walls
   * @param {Array} windowsData - Array of window objects
   * @param {Map<string, Object>} wallMap - Lookup map of wall information
   * @param {Object} settings - Scene settings
   * @returns {Array<THREE.Group>}
   */
  generate(windowsData = [], wallMap = new Map(), settings = {}) {
    const wallHeight = (settings && typeof settings.wallHeight === 'number')
      ? settings.wallHeight
      : ((settings && typeof settings.wall_height === 'number') ? settings.wall_height : 3.0);

    const windowHeightDefault = (settings && typeof settings.windowHeight === 'number')
      ? settings.windowHeight
      : ((settings && settings.defaults && typeof settings.defaults.window_height === 'number')
        ? settings.defaults.window_height
        : this.defaultHeight);

    const windowSillHeightDefault = (settings && typeof settings.windowSillHeight === 'number')
      ? settings.windowSillHeight
      : ((settings && settings.defaults && typeof settings.defaults.window_sill_height === 'number')
        ? settings.defaults.window_sill_height
        : this.defaultSillHeight);

    const windows = [];

    windowsData.forEach(win => {
      // 1. Validate wall reference
      const wallInfo = wallMap.get(win.wall_id);
      if (!wallInfo) {
        console.warn(`[WindowGenerator] Window ${win.id} references missing wall ${win.wall_id}`);
        return;
      }

      // 2. Position along the wall vector
      const x1 = wallInfo.start[0];
      const z1 = wallInfo.start[1];
      const x2 = wallInfo.end[0];
      const z2 = wallInfo.end[1];
      const wallLength = wallInfo.length;

      let winX, winZ;
      const geom = win.geometry;
      let offset = (geom && typeof geom.offset_from_start === 'number')
        ? geom.offset_from_start
        : win.offset;
      let positionRatio = win.position;

      // Authoritative processed center if available
      if (geom && Array.isArray(geom.center) && geom.center.length >= 2 &&
          typeof geom.center[0] === 'number' && typeof geom.center[1] === 'number') {
        winX = geom.center[0];
        winZ = geom.center[1];
      } else if (win.center && Array.isArray(win.center) && win.center.length >= 2) {
        winX = win.center[0];
        winZ = win.center[1];
      } else if (typeof offset === 'number' && wallLength > 0.0001) {
        const dirX = (x2 - x1) / wallLength;
        const dirZ = (z2 - z1) / wallLength;
        winX = x1 + dirX * offset;
        winZ = z1 + dirZ * offset;
        positionRatio = offset / wallLength;
      } else if (typeof positionRatio === 'number') {
        winX = x1 + positionRatio * (x2 - x1);
        winZ = z1 + positionRatio * (z2 - z1);
        offset = positionRatio * wallLength;
      } else {
        winX = (x1 + x2) / 2;
        winZ = (z1 + z2) / 2;
        positionRatio = 0.5;
        offset = 0.5 * wallLength;
      }

      const winWidth = (geom && typeof geom.width === 'number' && geom.width > 0)
        ? geom.width
        : ((typeof win.width === 'number' && win.width > 0) ? win.width : 1.5);

      const winHeight = (geom && typeof geom.height === 'number' && geom.height > 0)
        ? geom.height
        : ((typeof win.height === 'number' && win.height > 0)
          ? win.height
          : windowHeightDefault);

      const sillHeight = (geom && typeof geom.sill_height === 'number')
        ? geom.sill_height
        : ((typeof win.sill_height === 'number' && win.sill_height >= 0)
          ? win.sill_height
          : windowSillHeightDefault);

      const winY = sillHeight + winHeight / 2;
      const winThickness = wallInfo.thickness * 1.05;
      const frameBorder = 0.05; // 5cm frame border

      // 3. Create Window Group (Solid Frame + Glass Pane + Mullions)
      const windowGroup = new THREE.Group();
      windowGroup.name = `window_${win.id}`;

      // Left Frame Jamb
      const leftJamb = new THREE.Mesh(
        new THREE.BoxGeometry(frameBorder, winHeight, winThickness),
        this.frameMaterial
      );
      leftJamb.position.set(-winWidth / 2 + frameBorder / 2, 0, 0);
      windowGroup.add(leftJamb);

      // Right Frame Jamb
      const rightJamb = new THREE.Mesh(
        new THREE.BoxGeometry(frameBorder, winHeight, winThickness),
        this.frameMaterial
      );
      rightJamb.position.set(winWidth / 2 - frameBorder / 2, 0, 0);
      windowGroup.add(rightJamb);

      // Top Frame Header
      const header = new THREE.Mesh(
        new THREE.BoxGeometry(winWidth, frameBorder, winThickness),
        this.frameMaterial
      );
      header.position.set(0, winHeight / 2 - frameBorder / 2, 0);
      windowGroup.add(header);

      // Bottom Frame Sill
      const sill = new THREE.Mesh(
        new THREE.BoxGeometry(winWidth + 0.06, frameBorder * 1.2, winThickness * 1.15),
        this.frameMaterial
      );
      sill.position.set(0, -winHeight / 2 + frameBorder / 2, 0);
      windowGroup.add(sill);

      // Central Glass Pane
      const glassWidth = Math.max(0.01, winWidth - 2 * frameBorder);
      const glassHeight = Math.max(0.01, winHeight - 2 * frameBorder);
      const glassMesh = new THREE.Mesh(
        new THREE.BoxGeometry(glassWidth, glassHeight, winThickness * 0.25),
        this.glassMaterial
      );
      windowGroup.add(glassMesh);

      // Architectural Mullion cross
      const mullionH = new THREE.Mesh(
        new THREE.BoxGeometry(glassWidth, 0.03, winThickness * 0.35),
        this.frameMaterial
      );
      windowGroup.add(mullionH);

      const mullionV = new THREE.Mesh(
        new THREE.BoxGeometry(0.03, glassHeight, winThickness * 0.35),
        this.frameMaterial
      );
      windowGroup.add(mullionV);

      // 4. Transform and rotate according to wall orientation
      windowGroup.position.set(winX, winY, winZ);
      windowGroup.rotation.y = -wallInfo.angle;

      windowGroup.userData = {
        type: 'window',
        id: win.id,
        wallId: win.wall_id,
        offset: offset,
        positionRatio: positionRatio,
        width: winWidth,
        height: winHeight,
        sillHeight: sillHeight
      };

      windows.push(windowGroup);
    });

    return windows;
  }
}
