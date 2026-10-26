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

    this.dashMaterial = new THREE.LineDashedMaterial({
      color: 0x38bdf8,
      linewidth: 1.5,
      scale: 1,
      dashSize: 0.2,
      gapSize: 0.1,
      transparent: true,
      opacity: 0.7
    });
  }

  /**
   * Generates wireframe geometry from source wall and opening data
   * @param {Array} walls - Walls array
   * @param {number} wallHeight - Wall height in meters
   * @returns {THREE.Group} Group containing wireframe line segments
   */
  generate(walls = [], wallHeight = 3.0) {
    const group = new THREE.Group();
    group.name = 'OriginalBlueprintWireframe';

    walls.forEach(wall => {
      // Use original source coordinates if available, otherwise geometry
      const src = wall.source || wall.geometry || wall;
      const start = (src && Array.isArray(src.start)) ? src.start : wall.start;
      const end = (src && Array.isArray(src.end)) ? src.end : wall.end;

      if (!start || !end) return;

      const x1 = start[0], z1 = start[1];
      const x2 = end[0], z2 = end[1];

      // Ground line (Y = 0.02)
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
