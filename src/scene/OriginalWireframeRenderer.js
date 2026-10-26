import * as THREE from 'three';

/**
 * OriginalWireframeRenderer.js
 * Visualizes original / raw blueprint geometry as cyan wireframe lines (matching Image 1 target reference).
 * Enables instant visual comparison between un-repaired blueprint input and repaired 3D geometry.
 */
export class OriginalWireframeRenderer {
  constructor() {
    this.cyanMaterial = new THREE.LineBasicMaterial({
      color: 0x06b6d4, // Bright cyan wireframe
      linewidth: 2.0,
      transparent: true,
      opacity: 0.85
    });
  }

  /**
   * Generates wireframe geometry from source wall and opening data
   * @param {Array} walls - Walls array
   * @param {number} wallHeight - Wall height in meters
   * @param {Object} scale - Scale object ({ meters_per_pixel })
   * @returns {THREE.Group} Group containing wireframe line segments
   */
  generate(walls = [], wallHeight = 3.0, scale = null) {
    const group = new THREE.Group();
    group.name = 'OriginalBlueprintWireframe';

    const mpp = (scale && typeof scale.meters_per_pixel === 'number' && scale.meters_per_pixel > 0)
      ? scale.meters_per_pixel
      : 0.02;

    walls.forEach(wall => {
      let start = null;
      let end = null;

      // Prefer metric coordinates from geometry or unscaled metric start/end
      if (wall.geometry && Array.isArray(wall.geometry.start) && wall.geometry.start.length >= 2) {
        start = [wall.geometry.start[0], wall.geometry.start[1]];
        end = [wall.geometry.end[0], wall.geometry.end[1]];
      } else if (Array.isArray(wall.start) && wall.start.length >= 2 && wall.start[0] < 50) {
        start = [wall.start[0], wall.start[1]];
        end = [wall.end[0], wall.end[1]];
      } else if (wall.source && Array.isArray(wall.source.start) && wall.source.start.length >= 2) {
        // Convert source pixel coordinates to real-world meters using mpp scale
        start = [Number((wall.source.start[0] * mpp).toFixed(4)), Number((wall.source.start[1] * mpp).toFixed(4))];
        end = [Number((wall.source.end[0] * mpp).toFixed(4)), Number((wall.source.end[1] * mpp).toFixed(4))];
      }

      if (!start || !end) return;

      const x1 = start[0], z1 = start[1];
      const x2 = end[0], z2 = end[1];

      // Ground to wall-height line loop
      const pts = [
        new THREE.Vector3(x1, 0.02, z1),
        new THREE.Vector3(x2, 0.02, z2),
        new THREE.Vector3(x2, wallHeight, z2),
        new THREE.Vector3(x1, wallHeight, z1),
        new THREE.Vector3(x1, 0.02, z1)
      ];

      const geom = new THREE.BufferGeometry().setFromPoints(pts);
      const line = new THREE.Line(geom, this.cyanMaterial);
      line.name = `orig_wire_${wall.id}`;
      group.add(line);
    });

    return group;
  }
}
