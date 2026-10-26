import * as THREE from 'three';

export class RoomGenerator {
  constructor() {
    this.boundaryMaterial = new THREE.LineBasicMaterial({
      color: 0x38bdf8, // Blueprint cyan
      linewidth: 1.5,
      transparent: true,
      opacity: 0.6
    });
  }

  /**
   * Generates room boundary outlines and metadata
   * @param {Array} roomsData - Array of room objects
   * @returns {Object} { meshes: Array<THREE.Object3D>, roomInfos: Array<Object> }
   */
  generate(roomsData = []) {
    const meshes = [];
    const roomInfos = [];

    roomsData.forEach(room => {
      if (!room.polygon || !Array.isArray(room.polygon) || room.polygon.length < 3) {
        return;
      }

      // 1. Calculate or use processed centroid and area
      const centroid = (room.centroid && Array.isArray(room.centroid) && room.centroid.length >= 2)
        ? room.centroid
        : ((room.geometry && Array.isArray(room.geometry.centroid) && room.geometry.centroid.length >= 2)
          ? room.geometry.centroid
          : this.calculateCentroid(room.polygon));

      const area = (typeof room.area === 'number')
        ? room.area
        : ((room.geometry && typeof room.geometry.area === 'number')
          ? room.geometry.area
          : this.calculateArea(room.polygon));

      const roomLabel = room.label || room.name || 'Unnamed Room';

      // 2. Create boundary lines loop (Y = 0.005, just above floor level)
      const points = [];
      room.polygon.forEach(pt => {
        points.push(new THREE.Vector3(pt[0], 0.005, pt[1]));
      });
      // Close loop
      points.push(new THREE.Vector3(room.polygon[0][0], 0.005, room.polygon[0][1]));

      const boundaryGeom = new THREE.BufferGeometry().setFromPoints(points);
      const boundaryLine = new THREE.Line(boundaryGeom, this.boundaryMaterial);
      boundaryLine.name = `room_boundary_${room.id}`;

      const roomInfo = {
        id: room.id,
        name: roomLabel,
        label: roomLabel,
        polygon: room.polygon,
        centroid,
        area,
        mesh: boundaryLine
      };

      boundaryLine.userData = {
        type: 'room_boundary',
        id: room.id,
        name: roomLabel,
        label: roomLabel,
        area: area
      };

      meshes.push(boundaryLine);
      roomInfos.push(roomInfo);
    });

    return { meshes, roomInfos };
  }

  calculateCentroid(polygon) {
    let signedArea = 0;
    let cx = 0;
    let cz = 0;
    const n = polygon.length;

    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      const x0 = polygon[i][0];
      const z0 = polygon[i][1];
      const x1 = polygon[j][0];
      const z1 = polygon[j][1];
      const a = (x0 * z1 - x1 * z0);
      signedArea += a;
      cx += (x0 + x1) * a;
      cz += (z0 + z1) * a;
    }

    signedArea *= 0.5;
    if (Math.abs(signedArea) < 0.0001) {
      // Fallback simple average
      let sumX = 0, sumZ = 0;
      polygon.forEach(p => { sumX += p[0]; sumZ += p[1]; });
      return [sumX / n, sumZ / n];
    }

    cx /= (6 * signedArea);
    cz /= (6 * signedArea);
    return [cx, cz];
  }

  calculateArea(polygon) {
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
