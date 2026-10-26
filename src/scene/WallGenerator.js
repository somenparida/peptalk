import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

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

    // Highlighted material for active inspection/debugging
    this.highlightMaterial = new THREE.MeshStandardMaterial({
      color: 0xf59e0b, // Amber highlight
      roughness: 0.5,
      metalness: 0.1
    });
  }

  /**
   * Generates 3D walls from scene.json walls array with optional architectural cutouts for doors & windows
   * @param {Array} wallsData - Array of wall objects
   * @param {Object} settings - Scene settings (wallHeight, etc.)
   * @param {Object} options - Generation options (doors, windows, cutOpenings)
   * @returns {Object} { meshes: Array<THREE.Mesh>, wallMap: Map<string, Object> }
   */
  generate(wallsData = [], settings = {}, options = {}) {
    const wallHeight = (settings && typeof settings.wallHeight === 'number') 
      ? settings.wallHeight 
      : ((settings && typeof settings.wall_height === 'number') ? settings.wall_height : this.defaultHeight);

    const doors = options.doors || settings.doors || [];
    const windows = options.windows || settings.windows || [];
    const shouldCutOpenings = options.cutOpenings !== undefined 
      ? options.cutOpenings 
      : (settings.cutOpenings !== undefined ? settings.cutOpenings : true);

    // Group openings by host wall ID
    const openingsByWall = new Map();
    if (shouldCutOpenings) {
      doors.forEach(d => {
        if (!d.wall_id) return;
        if (!openingsByWall.has(d.wall_id)) openingsByWall.set(d.wall_id, []);
        openingsByWall.get(d.wall_id).push({
          type: 'door',
          id: d.id,
          offset: d.offset,
          position: d.position,
          center: d.center || (d.geometry && d.geometry.center),
          width: (d.geometry && typeof d.geometry.width === 'number') ? d.geometry.width : (d.width || 0.9),
          height: (d.geometry && typeof d.geometry.height === 'number') ? d.geometry.height : (d.height || settings.doorHeight || 2.1)
        });
      });

      windows.forEach(w => {
        if (!w.wall_id) return;
        if (!openingsByWall.has(w.wall_id)) openingsByWall.set(w.wall_id, []);
        openingsByWall.get(w.wall_id).push({
          type: 'window',
          id: w.id,
          offset: w.offset,
          position: w.position,
          center: w.center || (w.geometry && w.geometry.center),
          width: (w.geometry && typeof w.geometry.width === 'number') ? w.geometry.width : (w.width || 1.5),
          height: (w.geometry && typeof w.geometry.height === 'number') ? w.geometry.height : (w.height || settings.windowHeight || 1.2),
          sillHeight: (w.geometry && typeof w.geometry.sill_height === 'number') ? w.geometry.sill_height : (w.sill_height !== undefined ? w.sill_height : (settings.windowSillHeight || 0.9))
        });
      });
    }

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

      // 3. Create Wall Geometry: cut real openings if openings exist on this wall
      const wallOpenings = openingsByWall.get(wall.id) || [];
      const geometry = this._buildWallGeometry(length, wallHeight, thickness, wallOpenings, x1, z1, dx, dz);

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
        openingsCount: wallOpenings.length,
        mesh
      };

      mesh.userData = {
        type: 'wall',
        id: wall.id,
        length,
        calculatedLength: length,
        suppliedLength,
        thickness,
        height: wallHeight,
        hasOpenings: wallOpenings.length > 0
      };

      meshes.push(mesh);
      wallMap.set(wall.id, wallInfo);
    });

    return { meshes, wallMap };
  }

  /**
   * Constructs solid wall or segmented wall with clean physical opening voids
   */
  _buildWallGeometry(length, wallHeight, thickness, openings, x1, z1, dx, dz) {
    if (!openings || openings.length === 0) {
      return new THREE.BoxGeometry(length, wallHeight, thickness);
    }

    // Resolve metric offset along wall vector for each opening
    const resolvedOpenings = openings.map(op => {
      let offset = op.offset;
      if (op.center && Array.isArray(op.center) && op.center.length >= 2 && length > 0.0001) {
        // Project center coordinate onto wall line vector
        offset = ((op.center[0] - x1) * dx + (op.center[1] - z1) * dz) / length;
      } else if (typeof op.offset === 'number') {
        offset = op.offset;
      } else if (typeof op.position === 'number') {
        offset = op.position * length;
      } else {
        offset = 0.5 * length;
      }

      const w = op.width || 0.9;
      const u_start = Math.max(0, Math.min(length, offset - w / 2));
      const u_end = Math.max(0, Math.min(length, offset + w / 2));

      return {
        ...op,
        offset,
        u_start,
        u_end,
        span: u_end - u_start
      };
    }).filter(op => op.span > 0.005)
      .sort((a, b) => a.u_start - b.u_start);

    if (resolvedOpenings.length === 0) {
      return new THREE.BoxGeometry(length, wallHeight, thickness);
    }

    const subGeometries = [];
    let currentU = 0;

    resolvedOpenings.forEach(op => {
      // 1. Solid wall segment before opening
      if (op.u_start - currentU > 0.005) {
        const segLen = op.u_start - currentU;
        const segMid = currentU + segLen / 2;
        const solidGeom = new THREE.BoxGeometry(segLen, wallHeight, thickness);
        solidGeom.translate(segMid - length / 2, 0, 0);
        subGeometries.push(solidGeom);
      }

      const opSpan = op.u_end - op.u_start;
      const opMid = op.u_start + opSpan / 2;
      const localX = opMid - length / 2;

      if (op.type === 'door') {
        // Door opening: void below doorHeight, lintel header block above doorHeight
        const doorH = Math.min(wallHeight, op.height || 2.1);
        const lintelH = wallHeight - doorH;
        if (lintelH > 0.01) {
          const lintel = new THREE.BoxGeometry(opSpan, lintelH, thickness);
          const localY = (wallHeight + doorH) / 2 - wallHeight / 2;
          lintel.translate(localX, localY, 0);
          subGeometries.push(lintel);
        }
      } else if (op.type === 'window') {
        // Window opening: sill block below sillHeight, void in middle, lintel block above
        const sillH = Math.min(wallHeight - 0.1, op.sillHeight || 0.9);
        const winH = op.height || 1.2;
        const winTop = Math.min(wallHeight, sillH + winH);

        if (sillH > 0.01) {
          const sill = new THREE.BoxGeometry(opSpan, sillH, thickness);
          const localY = sillH / 2 - wallHeight / 2;
          sill.translate(localX, localY, 0);
          subGeometries.push(sill);
        }

        const lintelH = wallHeight - winTop;
        if (lintelH > 0.01) {
          const lintel = new THREE.BoxGeometry(opSpan, lintelH, thickness);
          const localY = (winTop + wallHeight) / 2 - wallHeight / 2;
          lintel.translate(localX, localY, 0);
          subGeometries.push(lintel);
        }
      }

      currentU = Math.max(currentU, op.u_end);
    });

    // 2. Final solid wall segment after last opening
    if (length - currentU > 0.005) {
      const segLen = length - currentU;
      const segMid = currentU + segLen / 2;
      const solidGeom = new THREE.BoxGeometry(segLen, wallHeight, thickness);
      solidGeom.translate(segMid - length / 2, 0, 0);
      subGeometries.push(solidGeom);
    }

    if (subGeometries.length > 0) {
      const merged = mergeGeometries(subGeometries, false);
      // Clean up temporary geometries to prevent memory leaks
      subGeometries.forEach(g => g.dispose());
      return merged;
    }

    return new THREE.BoxGeometry(length, wallHeight, thickness);
  }
}
