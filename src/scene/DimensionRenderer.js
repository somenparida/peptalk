import * as THREE from 'three';

export class DimensionRenderer {
  constructor() {
    this.lineMaterial = new THREE.LineBasicMaterial({
      color: 0x94a3b8, // Light slate architectural dimension line
      linewidth: 1.5,
      transparent: true,
      opacity: 0.8
    });
    this.dimensionObjects = [];
  }

  /**
   * Generates architectural dimension lines and numerical text badges
   * @param {Map<string, Object>} wallMap - Wall information map
   * @param {string} units - Unit label (default 'm')
   * @returns {Array<THREE.Object3D>}
   */
  generate(wallMap = new Map(), units = 'm') {
    this.dispose();
    const group = new THREE.Group();
    group.name = 'DimensionMarkers';

    wallMap.forEach(wall => {
      const { start, end, length, thickness, angle, dx, dz } = wall;
      if (length < 0.2) return;

      // Normal vector perpendicular to wall direction
      const nx = -dz / length;
      const nz = dx / length;

      // Offset dimension line outward from wall face
      const offsetDist = thickness / 2 + 0.45;
      const p1 = new THREE.Vector3(start[0] + nx * offsetDist, 0.05, start[1] + nz * offsetDist);
      const p2 = new THREE.Vector3(end[0] + nx * offsetDist, 0.05, end[1] + nz * offsetDist);

      // 1. Dimension line connecting p1 and p2
      const lineGeom = new THREE.BufferGeometry().setFromPoints([p1, p2]);
      const dimLine = new THREE.Line(lineGeom, this.lineMaterial);
      group.add(dimLine);

      // 2. Extension tick marks at endpoints
      const tickLen = 0.15;
      const tick1Geom = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(p1.x - nx * tickLen, 0.05, p1.z - nz * tickLen),
        new THREE.Vector3(p1.x + nx * tickLen, 0.05, p1.z + nz * tickLen)
      ]);
      const tick2Geom = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(p2.x - nx * tickLen, 0.05, p2.z - nz * tickLen),
        new THREE.Vector3(p2.x + nx * tickLen, 0.05, p2.z + nz * tickLen)
      ]);
      group.add(new THREE.Line(tick1Geom, this.lineMaterial));
      group.add(new THREE.Line(tick2Geom, this.lineMaterial));

      // 3. Numerical dimension text badge
      const midPoint = new THREE.Vector3(
        (p1.x + p2.x) / 2,
        0.3,
        (p1.z + p2.z) / 2
      );

      const labelText = `${length.toFixed(2)} ${units}`;
      const sprite = this.createDimensionSprite(labelText);
      sprite.position.copy(midPoint);
      group.add(sprite);
    });

    this.dimensionObjects.push(group);
    return [group];
  }

  createDimensionSprite(text) {
    if (typeof document === 'undefined') {
      const mock = new THREE.Group();
      mock.name = `dim_label_${text}`;
      return mock;
    }
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 96;
    const ctx = canvas.getContext('2d');

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Pill badge background
    ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.5)';
    ctx.lineWidth = 2;

    const x = 16, y = 16, w = 224, h = 64, r = 16;
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Metric text
    ctx.textAlign = 'center';
    ctx.font = 'bold 30px "JetBrains Mono", monospace';
    ctx.fillStyle = '#f8fafc';
    ctx.fillText(text, 128, 58);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.needsUpdate = true;

    const material = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      depthTest: false
    });

    const sprite = new THREE.Sprite(material);
    sprite.scale.set(1.4, 0.55, 1);
    return sprite;
  }

  dispose() {
    this.dimensionObjects.forEach(obj => {
      obj.traverse(child => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) {
          if (child.material.map) child.material.map.dispose();
          child.material.dispose();
        }
      });
    });
    this.dimensionObjects = [];
  }
}
