import * as THREE from 'three';

export class DoorGenerator {
  constructor(options = {}) {
    this.defaultHeight = options.defaultHeight || 2.1;

    // Architectural wood door panel material
    this.doorMaterial = new THREE.MeshStandardMaterial({
      color: 0x854d0e, // Warm architectural teak/wood
      roughness: 0.6,
      metalness: 0.05
    });

    // Dark trim / frame material
    this.frameMaterial = new THREE.MeshStandardMaterial({
      color: 0x292524, // Dark bronze/charcoal casing
      roughness: 0.7,
      metalness: 0.2
    });

    // Metallic hardware material (handle)
    this.handleMaterial = new THREE.MeshStandardMaterial({
      color: 0xd4af37, // Brass / satin gold
      roughness: 0.3,
      metalness: 0.8
    });
  }

  /**
   * Generates 3D doors attached to their corresponding walls
   * @param {Array} doorsData - Array of door objects
   * @param {Map<string, Object>} wallMap - Lookup map of wall information
   * @param {Object} settings - Scene settings
   * @returns {Array<THREE.Group>}
   */
  generate(doorsData = [], wallMap = new Map(), settings = {}) {
    const wallHeight = (settings && typeof settings.wallHeight === 'number')
      ? settings.wallHeight
      : ((settings && typeof settings.wall_height === 'number') ? settings.wall_height : 3.0);

    const doorHeightDefault = (settings && typeof settings.doorHeight === 'number')
      ? settings.doorHeight
      : ((settings && settings.defaults && typeof settings.defaults.door_height === 'number')
        ? settings.defaults.door_height
        : this.defaultHeight);

    const doors = [];

    doorsData.forEach(door => {
      // 1. Validate wall reference
      const wallInfo = wallMap.get(door.wall_id);
      if (!wallInfo) {
        console.warn(`[DoorGenerator] Door ${door.id} references missing wall ${door.wall_id}`);
        return;
      }

      // 2. Position along the wall vector
      const x1 = wallInfo.start[0];
      const z1 = wallInfo.start[1];
      const x2 = wallInfo.end[0];
      const z2 = wallInfo.end[1];
      const wallLength = wallInfo.length;

      let doorX, doorZ;
      const geom = door.geometry;
      let offset = (geom && typeof geom.offset_from_start === 'number')
        ? geom.offset_from_start
        : door.offset;
      let positionRatio = door.position;

      // Authoritative processed center if available
      if (geom && Array.isArray(geom.center) && geom.center.length >= 2 &&
          typeof geom.center[0] === 'number' && typeof geom.center[1] === 'number') {
        doorX = geom.center[0];
        doorZ = geom.center[1];
      } else if (door.center && Array.isArray(door.center) && door.center.length >= 2) {
        doorX = door.center[0];
        doorZ = door.center[1];
      } else if (typeof offset === 'number' && wallLength > 0.0001) {
        const dirX = (x2 - x1) / wallLength;
        const dirZ = (z2 - z1) / wallLength;
        doorX = x1 + dirX * offset;
        doorZ = z1 + dirZ * offset;
        positionRatio = offset / wallLength;
      } else if (typeof positionRatio === 'number') {
        doorX = x1 + positionRatio * (x2 - x1);
        doorZ = z1 + positionRatio * (z2 - z1);
        offset = positionRatio * wallLength;
      } else {
        doorX = (x1 + x2) / 2;
        doorZ = (z1 + z2) / 2;
        positionRatio = 0.5;
        offset = 0.5 * wallLength;
      }

      const doorWidth = (geom && typeof geom.width === 'number' && geom.width > 0)
        ? geom.width
        : ((typeof door.width === 'number' && door.width > 0) ? door.width : 0.9);

      const doorHeight = (geom && typeof geom.height === 'number' && geom.height > 0)
        ? geom.height
        : ((typeof door.height === 'number' && door.height > 0)
          ? door.height
          : doorHeightDefault);

      const doorY = doorHeight / 2;
      const doorThickness = wallInfo.thickness * 1.05;
      const frameJambWidth = 0.05; // 5cm frame border

      // 3. Create Door Group
      const doorGroup = new THREE.Group();
      doorGroup.name = `door_${door.id}`;

      // Left Frame Jamb
      const jambGeom = new THREE.BoxGeometry(frameJambWidth, doorHeight, doorThickness);
      const leftJamb = new THREE.Mesh(jambGeom, this.frameMaterial);
      leftJamb.position.set(-doorWidth / 2 + frameJambWidth / 2, 0, 0);
      leftJamb.castShadow = true;
      doorGroup.add(leftJamb);

      // Right Frame Jamb
      const rightJamb = new THREE.Mesh(jambGeom, this.frameMaterial);
      rightJamb.position.set(doorWidth / 2 - frameJambWidth / 2, 0, 0);
      rightJamb.castShadow = true;
      doorGroup.add(rightJamb);

      // Top Frame Header
      const headerGeom = new THREE.BoxGeometry(doorWidth, frameJambWidth, doorThickness);
      const header = new THREE.Mesh(headerGeom, this.frameMaterial);
      header.position.set(0, doorHeight / 2 - frameJambWidth / 2, 0);
      header.castShadow = true;
      doorGroup.add(header);

      // Door Leaf Panel (recessed inside frame)
      const panelWidth = doorWidth - 2 * frameJambWidth;
      const panelHeight = doorHeight - frameJambWidth;
      const panelGeom = new THREE.BoxGeometry(panelWidth, panelHeight, doorThickness * 0.5);
      const panelMesh = new THREE.Mesh(panelGeom, this.doorMaterial);
      panelMesh.position.set(0, -frameJambWidth / 2, 0);
      panelMesh.castShadow = true;
      panelMesh.receiveShadow = true;
      doorGroup.add(panelMesh);

      // Door Handle Hardware
      const handleGeom = new THREE.BoxGeometry(0.03, 0.12, doorThickness * 0.65);
      const handleMesh = new THREE.Mesh(handleGeom, this.handleMaterial);
      handleMesh.position.set(panelWidth * 0.35, -0.05, 0);
      doorGroup.add(handleMesh);

      // 4. Transform and rotate according to wall orientation
      doorGroup.position.set(doorX, doorY, doorZ);
      doorGroup.rotation.y = -wallInfo.angle;

      doorGroup.userData = {
        type: 'door',
        id: door.id,
        wallId: door.wall_id,
        offset: offset,
        positionRatio: positionRatio,
        width: doorWidth,
        height: doorHeight
      };

      doors.push(doorGroup);
    });

    return doors;
  }
}
