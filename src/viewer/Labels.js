import * as THREE from 'three';

export class Labels {
  constructor() {
    this.sprites = [];
  }

  /**
   * Generates billboard label sprites for rooms
   * @param {Array<Object>} roomInfos - Room metadata from RoomGenerator
   * @returns {Array<THREE.Sprite>}
   */
  generate(roomInfos = []) {
    this.dispose();
    const sprites = [];

    roomInfos.forEach(room => {
      const sprite = this.createRoomBadgeSprite(room.name, room.area);
      if (sprite) {
        sprite.position.set(room.centroid[0], 0.35, room.centroid[1]);
        sprite.userData = {
          type: 'room_label',
          roomId: room.id,
          roomName: room.name
        };
        sprites.push(sprite);
      }
    });

    this.sprites = sprites;
    return sprites;
  }

  createRoomBadgeSprite(roomName, area) {
    if (typeof document === 'undefined') {
      const mock = new THREE.Group();
      mock.name = `room_badge_${roomName}`;
      return mock;
    }
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 256;
    const ctx = canvas.getContext('2d');

    // High resolution crisp rendering
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Rounded rectangle card background
    const x = 32, y = 32, w = 448, h = 192, radius = 24;
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + w - radius, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
    ctx.lineTo(x + w, y + h - radius);
    ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
    ctx.lineTo(x + radius, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();

    ctx.fillStyle = 'rgba(15, 23, 42, 0.88)';
    ctx.fill();
    ctx.lineWidth = 4;
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.6)';
    ctx.stroke();

    // Text: Room Name
    ctx.textAlign = 'center';
    ctx.font = 'bold 44px "Plus Jakarta Sans", sans-serif';
    ctx.fillStyle = '#f8fafc';
    ctx.fillText(roomName, 256, 108);

    // Text: Room Area
    const areaText = area ? `${area.toFixed(2)} m²` : '';
    ctx.font = '500 30px "JetBrains Mono", monospace';
    ctx.fillStyle = '#38bdf8';
    ctx.fillText(areaText, 256, 168);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.needsUpdate = true;

    const material = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      depthTest: false
    });

    const sprite = new THREE.Sprite(material);
    sprite.scale.set(2.4, 1.2, 1);
    return sprite;
  }

  dispose() {
    this.sprites.forEach(sprite => {
      if (sprite.material) {
        if (sprite.material.map) sprite.material.map.dispose();
        sprite.material.dispose();
      }
    });
    this.sprites = [];
  }
}
