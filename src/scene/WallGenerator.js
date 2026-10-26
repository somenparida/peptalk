import * as THREE from 'three';

export class WallGenerator {
  constructor(options = {}) {
    this.defaultHeight = options.defaultHeight || 3.0;
    this.defaultThickness = options.defaultThickness || 0.2;
    
    // Shared neutral architectural material
    this.wallMaterial = new THREE.MeshStandardMaterial({
      color: 0xe2e8f0, // Clean architectural off-white/light-slate
      roughness: 0.75,
      metalness: 0.05
    });
  }

  /**
   * Generates 3D walls from scene.json walls array
   * @param {Array} wallsData - Array of wall objects
   * @param {Object} settings - Scene settings (wallHeight, etc.)
   * @returns {Object} { meshes: Array<THREE.Mesh>, wallMap: Map<string, Object> }
   */
  generate(wallsData = [], settings = {}) {
    const wallHeight = (settings && typeof settings.wallHeight === 'number') 
      ? settings.wallHeight 
      : ((settings && typeof settings.wall_height === 'number') ? settings.wall_height : this.defaultHeight);

    const meshes = [];
    const wallMap = new Map();

    wallsData.forEach(wall => {
      // 1. Coordinate extraction: Prefer processed metric geometry.start/end over source coordinates
      const start = (wall.geometry && Array.isArray(wall.geometry.start)) ? wall.geometry.start : wall.start;
      const end = (wall.geometry && Array.isArray(wall.geometry.end)) ? wall.geometry.end : wall.end;

      // Floorplan [x, y] -> Three.js [x, height, z]
      const x1 = start[0];
      const z1 = start[1];
      const x2 = end[0];
      const z2 = end[1];
      const thickness = (wall.geometry && typeof wall.geometry.thickness === 'number')
        ? wall.geometry.thickness
        : ((typeof wall.thickness === 'number' && wall.thickness > 0) ? wall.thickness : this.defaultThickness);

      // 2. Metric geometry calculations
      const dx = x2 - x1;
      const dz = z2 - z1;
      const length = Math.sqrt(dx * dx + dz * dz);
      const suppliedLength = wall.supplied_length || (wall.geometry && typeof wall.geometry.length === 'number' ? wall.geometry.length : null);

      if (length < 0.001) {
        console.warn(`[WallGenerator] Skipping degenerate wall ${wall.id} with length ${length}`);
        return;
      }

      // Angle of wall vector relative to +X axis
      const angle = Math.atan2(dz, dx);

      // Midpoint in 3D
      const midX = (x1 + x2) / 2;
      const midZ = (z1 + z2) / 2;
      const midY = wallHeight / 2;

      // 3. Create BoxGeometry: length (X) × wallHeight (Y) × thickness (Z)
      const geometry = new THREE.BoxGeometry(length, wallHeight, thickness);
      const mesh = new THREE.Mesh(geometry, this.wallMaterial);

      mesh.name = `wall_${wall.id}`;
      mesh.position.set(midX, midY, midZ);
      // Three.js right-handed rotation around +Y
      mesh.rotation.y = -angle;
      mesh.castShadow = true;
      mesh.receiveShadow = true;

      // Store metadata for inspection & GLB export
      const wallInfo = {
        id: wall.id,
        start: [x1, z1],
        end: [x2, z2],
        dx,
        dz,
        length,
        calculatedLength: length,
        suppliedLength,
        thickness,
        wallHeight,
        angle,
        midpoint: [midX, midY, midZ],
        mesh
      };

      mesh.userData = {
        type: 'wall',
        id: wall.id,
        length,
        calculatedLength: length,
        suppliedLength,
        thickness,
        height: wallHeight
      };

      meshes.push(mesh);
      wallMap.set(wall.id, wallInfo);
    });

    return { meshes, wallMap };
  }
}
