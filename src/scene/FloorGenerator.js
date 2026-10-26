import * as THREE from 'three';

export class FloorGenerator {
  constructor(options = {}) {
    this.defaultThickness = options.defaultThickness || 0.1;

    // Architectural neutral slate floor material
    this.floorMaterial = new THREE.MeshStandardMaterial({
      color: 0x334155, // Elegant architectural slate
      roughness: 0.65,
      metalness: 0.1,
      side: THREE.DoubleSide
    });
  }

  /**
   * Generates horizontal floor meshes from room polygons
   * @param {Array} roomsData - Array of room objects with polygon coordinates
   * @param {Object} settings - Scene settings
   * @returns {Array<THREE.Mesh>}
   */
  generate(roomsData = [], settings = {}) {
    const floorThickness = (settings && typeof settings.floorThickness === 'number')
      ? settings.floorThickness
      : this.defaultThickness;

    const meshes = [];

    roomsData.forEach(room => {
      if (!room.polygon || !Array.isArray(room.polygon) || room.polygon.length < 3) {
        console.warn(`[FloorGenerator] Skipping room ${room.id || 'unknown'} - insufficient polygon vertices`);
        return;
      }

      // 1. Build 2D shape in polygon space [x, y]
      const shape = new THREE.Shape();
      room.polygon.forEach((pt, index) => {
        const x = pt[0];
        const y = pt[1];
        if (index === 0) {
          shape.moveTo(x, y);
        } else {
          shape.lineTo(x, y);
        }
      });
      shape.closePath();

      // 2. Extrude geometry downwards
      const extrudeSettings = {
        depth: floorThickness,
        bevelEnabled: false
      };
      const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);

      // Rotate shape from XY plane to XZ plane:
      // rotateX(PI / 2) maps shape X -> X, shape Y -> +Z, extrusion depth (+Z) -> -Y
      geometry.rotateX(Math.PI / 2);
      geometry.computeVertexNormals();

      const mesh = new THREE.Mesh(geometry, this.floorMaterial);
      mesh.name = `floor_${room.id}`;
      mesh.receiveShadow = true;

      // Prefer processed area from geometry if available, else fallback to Shoelace formula
      const area = (room.geometry && typeof room.geometry.area === 'number')
        ? room.geometry.area
        : ((typeof room.area === 'number') ? room.area : this.calculatePolygonArea(room.polygon));

      const roomLabel = room.label || room.name || 'Unnamed Room';

      mesh.userData = {
        type: 'floor',
        roomId: room.id,
        roomName: roomLabel,
        thickness: floorThickness,
        area: area
      };

      meshes.push(mesh);
    });

    return meshes;
  }

  /**
   * Calculates area of 2D polygon via Shoelace formula
   */
  calculatePolygonArea(polygon) {
    let area = 0;
    const n = polygon.length;
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      area += polygon[i][0] * polygon[j][1];
      area -= polygon[j][0] * polygon[i][1];
    }
    return Math.abs(area) / 2.0;
  }
}
