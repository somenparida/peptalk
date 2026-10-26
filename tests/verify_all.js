// Polyfill FileReader for headless Node.js GLTFExporter
if (typeof globalThis.FileReader === 'undefined') {
  globalThis.FileReader = class FileReader {
    readAsArrayBuffer(blob) {
      blob.arrayBuffer().then(buf => {
        this.result = buf;
        if (this.onload) this.onload({ target: this });
        if (this.onloadend) this.onloadend({ target: this });
      });
    }
    readAsDataURL(blob) {
      blob.arrayBuffer().then(buf => {
        this.result = 'data:application/octet-stream;base64,' + Buffer.from(buf).toString('base64');
        if (this.onload) this.onload({ target: this });
        if (this.onloadend) this.onloadend({ target: this });
      });
    }
  };
}

import * as THREE from 'three';
import { WallGenerator } from '../src/scene/WallGenerator.js';
import { FloorGenerator } from '../src/scene/FloorGenerator.js';
import { DoorGenerator } from '../src/scene/DoorGenerator.js';
import { WindowGenerator } from '../src/scene/WindowGenerator.js';
import { RoomGenerator } from '../src/scene/RoomGenerator.js';
import { DimensionRenderer } from '../src/scene/DimensionRenderer.js';
import { SceneValidator } from '../src/data/SceneValidator.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import fs from 'fs';

console.log('======================================================');
console.log('🧪 RUNNING COMPREHENSIVE SUITE FOR HACKNEX 2026 PS06');
console.log('======================================================\n');

let totalTests = 0;
let passedTests = 0;

function assert(condition, testName, details = '') {
  totalTests++;
  if (condition) {
    passedTests++;
    console.log(`  ✓ PASS: ${testName}`);
  } else {
    console.error(`  ❌ FAIL: ${testName} ${details ? '- ' + details : ''}`);
  }
}

async function runTestSuite() {
  // =========================================================================
  // PART A: EXISTING SYNTHETIC / TEST SCENE TESTS (PRESERVED FUNCTIONALITY)
  // =========================================================================

  // 1. DATA VALIDATION TESTS
  console.log('--- TEST GROUP 1: INPUT VALIDATION & CONTRACTS (TEST SCENE) ---');
  const rawScene = JSON.parse(fs.readFileSync('./src/data/scene.json', 'utf-8'));
  const valResult = SceneValidator.validate(rawScene);
  assert(valResult.isValid === true, 'Test scene validates successfully');
  assert(valResult.errors.length === 0, 'Zero errors on valid test scene');
  assert(valResult.scene.walls.length === 4, '4 walls present in validated scene');
  assert(valResult.scene.rooms.length === 1, '1 room present in validated scene');

  // Test corrupted input handling
  const corruptedScene = {
    walls: [
      { id: 'w1', start: [0, 0], end: [4, 0], thickness: 0.2 },
      { id: 'w_corrupt', start: 'invalid', end: [0, 4] }
    ],
    doors: [
      { id: 'd1', wall_id: 'w1', position: 0.5, width: 0.9 },
      { id: 'd_orphan', wall_id: 'w_nonexistent', position: 0.5, width: 0.9 }
    ],
    rooms: [
      { id: 'r_empty', polygon: [] }
    ]
  };
  const corruptVal = SceneValidator.validate(corruptedScene);
  assert(corruptVal.isValid === true, 'Corrupted scene does not crash and keeps valid objects');
  assert(corruptVal.scene.walls.length === 1, 'Only valid wall w1 retained');
  assert(corruptVal.scene.doors.length === 1, 'Only valid door d1 retained, orphan skipped');
  assert(corruptVal.warnings.some(w => w.includes('w_nonexistent')), 'Identified missing wall w_nonexistent gracefully');

  // 2. WALL GENERATOR TESTS
  console.log('\n--- TEST GROUP 2: WALL GEOMETRY ACCURACY (TEST SCENE) ---');
  const wallGen = new WallGenerator();
  const { meshes: wallMeshes, wallMap } = wallGen.generate(rawScene.walls, rawScene.settings);
  assert(wallMeshes.length === 4, 'WallGenerator created 4 meshes');

  const w1 = wallMap.get('w1');
  assert(Math.abs(w1.length - 6.0) < 0.0001, 'w1 length is exactly 6.0m', `got ${w1.length}`);
  assert(Math.abs(w1.thickness - 0.2) < 0.0001, 'w1 thickness is 0.2m');
  assert(Math.abs(w1.wallHeight - 3.0) < 0.0001, 'w1 height is 3.0m');
  assert(Math.abs(w1.midpoint[0] - 3.0) < 0.0001 && Math.abs(w1.midpoint[1] - 1.5) < 0.0001 && Math.abs(w1.midpoint[2] - 0.0) < 0.0001,
    'w1 midpoint is exactly [3.0, 1.5, 0.0]');

  const w2 = wallMap.get('w2');
  assert(Math.abs(w2.length - 4.0) < 0.0001, 'w2 length is exactly 4.0m', `got ${w2.length}`);
  assert(Math.abs(w2.midpoint[0] - 6.0) < 0.0001 && Math.abs(w2.midpoint[1] - 1.5) < 0.0001 && Math.abs(w2.midpoint[2] - 2.0) < 0.0001,
    'w2 midpoint is exactly [6.0, 1.5, 2.0]');

  const w3 = wallMap.get('w3');
  assert(Math.abs(w3.length - 6.0) < 0.0001, 'w3 length is exactly 6.0m', `got ${w3.length}`);

  const w4 = wallMap.get('w4');
  assert(Math.abs(w4.length - 4.0) < 0.0001, 'w4 length is exactly 4.0m', `got ${w4.length}`);

  // 3. FLOOR GENERATOR TESTS
  console.log('\n--- TEST GROUP 3: FLOOR GEOMETRY & POLYGONS (TEST SCENE) ---');
  const floorGen = new FloorGenerator();
  const floorMeshes = floorGen.generate(rawScene.rooms, rawScene.settings);
  assert(floorMeshes.length === 1, 'FloorGenerator created 1 floor mesh');
  const flMesh = floorMeshes[0];
  assert(Math.abs(flMesh.userData.area - 20.16) < 0.0001, 'Floor area is exactly 20.16 m²', `got ${flMesh.userData.area}`);

  // 4. DOOR GENERATOR TESTS
  console.log('\n--- TEST GROUP 4: DOOR ATTACHMENT & DIMENSIONS (TEST SCENE) ---');
  const doorGen = new DoorGenerator();
  const doorObjs = doorGen.generate(rawScene.doors, wallMap, rawScene.settings);
  assert(doorObjs.length === 1, 'DoorGenerator created 1 door group');
  const d1 = doorObjs[0];
  assert(d1.userData.width === 0.9, 'Door d1 width is 0.9m');
  assert(Math.abs(d1.position.x - 3.0) < 0.0001 && Math.abs(d1.position.z - 0.0) < 0.0001,
    'Door d1 placed at wall w1 midpoint [3.0, 0.0]');
  assert(Math.abs(d1.position.y - 1.05) < 0.0001, 'Door bottom rests on floor (y center = 1.05m for 2.1m height)');

  // 5. WINDOW GENERATOR TESTS
  console.log('\n--- TEST GROUP 5: WINDOW ATTACHMENT & DIMENSIONS (TEST SCENE) ---');
  const windowGen = new WindowGenerator();
  const winObjs = windowGen.generate(rawScene.windows, wallMap, rawScene.settings);
  assert(winObjs.length === 1, 'WindowGenerator created 1 window group');
  const win1 = winObjs[0];
  assert(win1.userData.width === 1.5, 'Window win1 width is 1.5m');
  assert(Math.abs(win1.position.x - 3.0) < 0.0001 && Math.abs(win1.position.z - 4.0) < 0.0001,
    'Window win1 placed at wall w3 midpoint [3.0, 4.0]');
  assert(Math.abs(win1.position.y - 1.6) < 0.0001, 'Window win1 sill elevated (y center = 1.6m)');

  // 6. ROOM GENERATOR TESTS
  console.log('\n--- TEST GROUP 6: ROOM BOUNDARY & CENTROID (TEST SCENE) ---');
  const roomGen = new RoomGenerator();
  const { meshes: roomMeshes, roomInfos } = roomGen.generate(rawScene.rooms);
  assert(roomMeshes.length === 1, 'RoomGenerator created 1 boundary outline');
  assert(roomInfos.length === 1, 'RoomGenerator returned 1 room info');
  const rInfo = roomInfos[0];
  assert(rInfo.name === 'Test Room', 'Room name matches scene.json');
  assert(Math.abs(rInfo.centroid[0] - 3.0) < 0.0001 && Math.abs(rInfo.centroid[1] - 2.0) < 0.0001,
    'Room centroid accurately computed at [3.0, 2.0]');

  // 7. DIMENSION RENDERER TESTS
  console.log('\n--- TEST GROUP 7: DIMENSIONS & MEASUREMENTS (TEST SCENE) ---');
  const dimRenderer = new DimensionRenderer();
  const dimObjs = dimRenderer.generate(wallMap, 'm');
  assert(dimObjs.length === 1, 'DimensionRenderer created dimension marker group');
  assert(dimObjs[0].children.length >= 4, 'Dimension markers created for all walls');


  // =========================================================================
  // PART B: REAL MEMBER 2 SCENE VALIDATION (sample_scene.json)
  // Verification items 1 through 26 as specified in integration contract
  // =========================================================================
  console.log('\n--- TEST GROUP 8: REAL MEMBER 2 PARSING & SCHEMA VALIDATION ---');
  const member2Raw = JSON.parse(fs.readFileSync('./src/data/sample_scene.json', 'utf-8'));
  const m2Validation = SceneValidator.validate(member2Raw);

  // Requirement 1: JSON loads successfully
  assert(m2Validation.isValid === true, '1. Member 2 JSON loads & validates successfully');
  assert(m2Validation.errors.length === 0, 'Zero errors on valid Member 2 scene');

  const m2Scene = m2Validation.scene;

  // Requirement 2: 4 rooms detected
  assert(m2Scene.rooms.length === 4, '2. 4 rooms detected in Member 2 scene', `got ${m2Scene.rooms.length}`);

  // Requirement 3: 8 walls detected
  assert(m2Scene.walls.length === 8, '3. 8 walls detected in Member 2 scene', `got ${m2Scene.walls.length}`);

  // Requirement 4: 4 doors detected
  assert(m2Scene.doors.length === 4, '4. 4 doors detected in Member 2 scene', `got ${m2Scene.doors.length}`);

  // Requirement 5: 4 windows detected
  assert(m2Scene.windows.length === 4, '5. 4 windows detected in Member 2 scene', `got ${m2Scene.windows.length}`);

  // Requirement 6: wall height = 2.8m
  assert(Math.abs(m2Scene.wall_height - 2.8) < 0.0001 && Math.abs(m2Scene.settings.wallHeight - 2.8) < 0.0001,
    '6. wall height = 2.8m (explicit priority over settings)', `got ${m2Scene.wall_height}`);


  // WALL GENERATION & GEOMETRY (Requirements 7-14)
  console.log('\n--- TEST GROUP 9: MEMBER 2 WALL GEOMETRY ACCURACY ---');
  const m2WallGen = new WallGenerator();
  const { meshes: m2WallMeshes, wallMap: m2WallMap } = m2WallGen.generate(m2Scene.walls, m2Scene.settings);
  assert(m2WallMeshes.length === 8, 'WallGenerator created 8 wall meshes for Member 2');

  // Requirement 7: south wall length = 8m
  const wallSouth = m2WallMap.get('wall_south');
  assert(wallSouth && Math.abs(wallSouth.length - 8.0) < 0.0001, '7. south wall length = 8m', `got ${wallSouth?.length}`);
  assert(wallSouth && Math.abs(wallSouth.wallHeight - 2.8) < 0.0001, 'south wall height = 2.8m');

  // Requirement 8: north wall length = 8m
  const wallNorth = m2WallMap.get('wall_north');
  assert(wallNorth && Math.abs(wallNorth.length - 8.0) < 0.0001, '8. north wall length = 8m', `got ${wallNorth?.length}`);

  // Requirement 9: west wall length = 6m
  const wallWest = m2WallMap.get('wall_west');
  assert(wallWest && Math.abs(wallWest.length - 6.0) < 0.0001, '9. west wall length = 6m', `got ${wallWest?.length}`);

  // Requirement 10: east wall length = 6m
  const wallEast = m2WallMap.get('wall_east');
  assert(wallEast && Math.abs(wallEast.length - 6.0) < 0.0001, '10. east wall length = 6m', `got ${wallEast?.length}`);

  // Requirement 11: living/bed partition = 4.8m
  const wallPartLivingBed = m2WallMap.get('wall_partition_living_bed');
  assert(wallPartLivingBed && Math.abs(wallPartLivingBed.length - 4.8) < 0.0001, '11. living/bed partition = 4.8m', `got ${wallPartLivingBed?.length}`);

  // Requirement 12: kitchen/bath partition = 3.2m
  const wallPartKitBath = m2WallMap.get('wall_partition_kit_bath');
  assert(wallPartKitBath && Math.abs(wallPartKitBath.length - 3.2) < 0.0001, '12. kitchen/bath partition = 3.2m', `got ${wallPartKitBath?.length}`);

  // Requirement 13: living/kitchen partition = 3.5m
  const wallPartLivingKit = m2WallMap.get('wall_partition_living_kit');
  assert(wallPartLivingKit && Math.abs(wallPartLivingKit.length - 3.5) < 0.0001, '13. living/kitchen partition = 3.5m', `got ${wallPartLivingKit?.length}`);

  // Requirement 14: bedroom/bath partition = 2.5m
  const wallPartBedBath = m2WallMap.get('wall_partition_bed_bath');
  assert(wallPartBedBath && Math.abs(wallPartBedBath.length - 2.5) < 0.0001, '14. bedroom/bath partition = 2.5m', `got ${wallPartBedBath?.length}`);


  // DOOR OFFSETS & ATTACHMENT (Requirements 15-18)
  console.log('\n--- TEST GROUP 10: MEMBER 2 DOOR ATTACHMENTS & METRIC OFFSETS ---');
  const m2DoorGen = new DoorGenerator();
  const m2DoorObjs = m2DoorGen.generate(m2Scene.doors, m2WallMap, m2Scene.settings);
  assert(m2DoorObjs.length === 4, 'DoorGenerator created 4 door groups for Member 2');

  const doorMap = new Map();
  m2DoorObjs.forEach(d => doorMap.set(d.userData.id, d));

  // Requirement 15: entrance door offset = 1.5m
  const doorEntrance = doorMap.get('door_entrance');
  assert(doorEntrance && Math.abs(doorEntrance.userData.offset - 1.5) < 0.0001, '15. entrance door offset = 1.5m');
  assert(doorEntrance && Math.abs(doorEntrance.position.x - 1.5) < 0.0001 && Math.abs(doorEntrance.position.z - 0.0) < 0.0001,
    'entrance door calculated position = [1.5, 0.0]');
  assert(doorEntrance && Math.abs(doorEntrance.position.y - 1.05) < 0.0001, 'entrance door y center = 1.05m (floor-rested)');
  assert(doorEntrance && doorEntrance.userData.width === 0.9 && doorEntrance.userData.height === 2.1, 'entrance door width=0.9m, height=2.1m');

  // Requirement 16: bedroom door offset = 1.8m
  const doorBedroom = doorMap.get('door_bedroom');
  assert(doorBedroom && Math.abs(doorBedroom.userData.offset - 1.8) < 0.0001, '16. bedroom door offset = 1.8m');
  assert(doorBedroom && Math.abs(doorBedroom.position.x - 1.8) < 0.0001 && Math.abs(doorBedroom.position.z - 3.5) < 0.0001,
    'bedroom door calculated position = [1.8, 3.5]');
  assert(doorBedroom && doorBedroom.userData.width === 0.85 && doorBedroom.userData.height === 2.1, 'bedroom door width=0.85m, height=2.1m');

  // Requirement 17: kitchen door offset = 1.2m
  const doorKitchen = doorMap.get('door_kitchen');
  assert(doorKitchen && Math.abs(doorKitchen.userData.offset - 1.2) < 0.0001, '17. kitchen door offset = 1.2m');
  assert(doorKitchen && Math.abs(doorKitchen.position.x - 4.8) < 0.0001 && Math.abs(doorKitchen.position.z - 1.2) < 0.0001,
    'kitchen door calculated position = [4.8, 1.2]');
  assert(doorKitchen && doorKitchen.userData.width === 0.9 && doorKitchen.userData.height === 2.1, 'kitchen door width=0.9m, height=2.1m');

  // Requirement 18: bathroom door offset = 1.0m
  const doorBathroom = doorMap.get('door_bathroom');
  assert(doorBathroom && Math.abs(doorBathroom.userData.offset - 1.0) < 0.0001, '18. bathroom door offset = 1.0m');
  assert(doorBathroom && Math.abs(doorBathroom.position.x - 5.8) < 0.0001 && Math.abs(doorBathroom.position.z - 3.5) < 0.0001,
    'bathroom door calculated position = [5.8, 3.5]');
  assert(doorBathroom && doorBathroom.userData.width === 0.8 && doorBathroom.userData.height === 2.1, 'bathroom door width=0.8m, height=2.1m');


  // WINDOW OFFSETS & ATTACHMENT (Requirements 19-22)
  console.log('\n--- TEST GROUP 11: MEMBER 2 WINDOW ATTACHMENTS & METRIC OFFSETS ---');
  const m2WindowGen = new WindowGenerator();
  const m2WindowObjs = m2WindowGen.generate(m2Scene.windows, m2WallMap, m2Scene.settings);
  assert(m2WindowObjs.length === 4, 'WindowGenerator created 4 window groups for Member 2');

  const winMap = new Map();
  m2WindowObjs.forEach(w => winMap.set(w.userData.id, w));

  // Requirement 19: living window offset = 1.0m
  const winLiving = winMap.get('window_living');
  assert(winLiving && Math.abs(winLiving.userData.offset - 1.0) < 0.0001, '19. living window offset = 1.0m');
  assert(winLiving && Math.abs(winLiving.position.x - 0.0) < 0.0001 && Math.abs(winLiving.position.z - 1.0) < 0.0001,
    'living window calculated position = [0.0, 1.0]');
  assert(winLiving && Math.abs(winLiving.position.y - (0.9 + 1.4 / 2)) < 0.0001, 'living window y center = 1.6m (sill=0.9m, h=1.4m)');
  assert(winLiving && winLiving.userData.width === 1.6 && winLiving.userData.height === 1.4 && winLiving.userData.sillHeight === 0.9,
    'living window dims: width=1.6m, height=1.4m, sill=0.9m');

  // Requirement 20: bedroom window offset = 1.5m
  const winBedroom = winMap.get('window_bedroom');
  assert(winBedroom && Math.abs(winBedroom.userData.offset - 1.5) < 0.0001, '20. bedroom window offset = 1.5m');
  assert(winBedroom && Math.abs(winBedroom.position.x - 1.5) < 0.0001 && Math.abs(winBedroom.position.z - 6.0) < 0.0001,
    'bedroom window calculated position = [1.5, 6.0]');
  assert(winBedroom && Math.abs(winBedroom.position.y - (1.0 + 1.2 / 2)) < 0.0001, 'bedroom window y center = 1.6m (sill=1.0m, h=1.2m)');

  // Requirement 21: kitchen window offset = 1.2m
  const winKitchen = winMap.get('window_kitchen');
  assert(winKitchen && Math.abs(winKitchen.userData.offset - 1.2) < 0.0001, '21. kitchen window offset = 1.2m');
  assert(winKitchen && Math.abs(winKitchen.position.x - 8.0) < 0.0001 && Math.abs(winKitchen.position.z - 1.2) < 0.0001,
    'kitchen window calculated position = [8.0, 1.2]');
  assert(winKitchen && Math.abs(winKitchen.position.y - (1.1 + 1.1 / 2)) < 0.0001, 'kitchen window y center = 1.65m (sill=1.1m, h=1.1m)');

  // Requirement 22: bathroom window offset = 6.0m
  const winBathroom = winMap.get('window_bathroom');
  assert(winBathroom && Math.abs(winBathroom.userData.offset - 6.0) < 0.0001, '22. bathroom window offset = 6.0m');
  assert(winBathroom && Math.abs(winBathroom.position.x - 6.0) < 0.0001 && Math.abs(winBathroom.position.z - 6.0) < 0.0001,
    'bathroom window calculated position = [6.0, 6.0]');
  assert(winBathroom && Math.abs(winBathroom.position.y - (1.4 + 0.8 / 2)) < 0.0001, 'bathroom window y center = 1.8m (sill=1.4m, h=0.8m)');


  // ROOMS, CENTROIDS & AREAS (Requirements 23-26)
  console.log('\n--- TEST GROUP 12: MEMBER 2 ROOM NAMES, POLYGONS, CENTROIDS & AREAS ---');
  const m2RoomGen = new RoomGenerator();
  const { meshes: m2RoomMeshes, roomInfos: m2RoomInfos } = m2RoomGen.generate(m2Scene.rooms);
  assert(m2RoomMeshes.length === 4, 'RoomGenerator created 4 room boundary loops');
  assert(m2RoomInfos.length === 4, 'RoomGenerator produced 4 room info objects');

  const roomInfoMap = new Map();
  m2RoomInfos.forEach(r => roomInfoMap.set(r.id, r));

  // Requirement 23: room names preserved
  const rLiving = roomInfoMap.get('room_living');
  const rKit = roomInfoMap.get('room_kitchen');
  const rBed = roomInfoMap.get('room_bedroom');
  const rBath = roomInfoMap.get('room_bathroom');
  assert(rLiving && rLiving.name === 'Living Room' &&
         rKit && rKit.name === 'Kitchen' &&
         rBed && rBed.name === 'Bedroom' &&
         rBath && rBath.name === 'Bathroom',
    '23. room names preserved: Living Room, Kitchen, Bedroom, Bathroom');

  // Requirement 24: room polygons preserved
  assert(rLiving && rLiving.polygon.length === 4 &&
         rKit && rKit.polygon.length === 4 &&
         rBed && rBed.polygon.length === 4 &&
         rBath && rBath.polygon.length === 4,
    '24. room polygons preserved (4 vertices for each room)');

  // Requirement 25: room centroids are correctly calculated
  // Living Room: x in [0, 4.8], z in [0, 3.5] -> center [2.4, 1.75]
  assert(rLiving && Math.abs(rLiving.centroid[0] - 2.4) < 0.0001 && Math.abs(rLiving.centroid[1] - 1.75) < 0.0001,
    '25a. living room centroid = [2.4, 1.75]', `got [${rLiving?.centroid.join(', ')}]`);

  // Kitchen: x in [4.8, 8.0], z in [0, 3.5] -> center [6.4, 1.75]
  assert(rKit && Math.abs(rKit.centroid[0] - 6.4) < 0.0001 && Math.abs(rKit.centroid[1] - 1.75) < 0.0001,
    '25b. kitchen centroid = [6.4, 1.75]', `got [${rKit?.centroid.join(', ')}]`);

  // Bedroom: x in [0, 4.8], z in [3.5, 6.0] -> center [2.4, 4.75]
  assert(rBed && Math.abs(rBed.centroid[0] - 2.4) < 0.0001 && Math.abs(rBed.centroid[1] - 4.75) < 0.0001,
    '25c. bedroom centroid = [2.4, 4.75]', `got [${rBed?.centroid.join(', ')}]`);

  // Bathroom: x in [4.8, 8.0], z in [3.5, 6.0] -> center [6.4, 4.75]
  assert(rBath && Math.abs(rBath.centroid[0] - 6.4) < 0.0001 && Math.abs(rBath.centroid[1] - 4.75) < 0.0001,
    '25d. bathroom centroid = [6.4, 4.75]', `got [${rBath?.centroid.join(', ')}]`);

  // Requirement 26: room areas are correctly calculated
  // Living Room: 4.8 * 3.5 = 16.8 m²
  assert(rLiving && Math.abs(rLiving.area - 16.8) < 0.0001, '26a. living room area = 16.8 m²', `got ${rLiving?.area}`);

  // Kitchen: 3.2 * 3.5 = 11.2 m²
  assert(rKit && Math.abs(rKit.area - 11.2) < 0.0001, '26b. kitchen area = 11.2 m²', `got ${rKit?.area}`);

  // Bedroom: 4.8 * 2.5 = 12.0 m²
  assert(rBed && Math.abs(rBed.area - 12.0) < 0.0001, '26c. bedroom area = 12.0 m²', `got ${rBed?.area}`);

  // Bathroom: 3.2 * 2.5 = 8.0 m²
  assert(rBath && Math.abs(rBath.area - 8.0) < 0.0001, '26d. bathroom area = 8.0 m²', `got ${rBath?.area}`);

  // Total floor area
  const totalFloorArea = rLiving.area + rKit.area + rBed.area + rBath.area;
  assert(Math.abs(totalFloorArea - 48.0) < 0.0001, 'total apartment area = 48.0 m²', `got ${totalFloorArea}`);


  // OVERALL BOUNDS & GLB EXPORT / RELOAD ROUNDTRIP
  console.log('\n--- TEST GROUP 13: OVERALL BOUNDS & GLB ROUNDTRIP VALIDATION ---');
  const m2FloorGen = new FloorGenerator();
  const m2FloorMeshes = m2FloorGen.generate(m2Scene.rooms, m2Scene.settings);
  assert(m2FloorMeshes.length === 4, 'FloorGenerator created 4 floor meshes for Member 2');

  const m2SceneGroup = new THREE.Group();
  m2SceneGroup.name = 'ReconstructedArchitecture';

  const gWalls = new THREE.Group();
  gWalls.name = 'Walls';
  m2WallMeshes.forEach(m => gWalls.add(m));
  m2SceneGroup.add(gWalls);

  const gFloors = new THREE.Group();
  gFloors.name = 'Floors';
  m2FloorMeshes.forEach(m => gFloors.add(m));
  m2SceneGroup.add(gFloors);

  const gDoors = new THREE.Group();
  gDoors.name = 'Doors';
  m2DoorObjs.forEach(m => gDoors.add(m));
  m2SceneGroup.add(gDoors);

  const gWindows = new THREE.Group();
  gWindows.name = 'Windows';
  m2WindowObjs.forEach(m => gWindows.add(m));
  m2SceneGroup.add(gWindows);

  const gRooms = new THREE.Group();
  gRooms.name = 'Rooms';
  m2RoomMeshes.forEach(m => gRooms.add(m));
  m2SceneGroup.add(gRooms);

  // Check scene bounds before export
  const preBox = new THREE.Box3().setFromObject(m2SceneGroup);
  const preSize = new THREE.Vector3();
  preBox.getSize(preSize);
  console.log(`  Geometric Bounds: Width(X)=${preSize.x.toFixed(2)}m, Height(Y)=${preSize.y.toFixed(2)}m, Depth(Z)=${preSize.z.toFixed(2)}m`);
  assert(Math.abs(preSize.x - 8.2) < 0.25, 'Overall width remains approximately 8m (with wall thickness)', `got ${preSize.x.toFixed(2)}m`);
  assert(Math.abs(preSize.z - 6.2) < 0.25, 'Overall depth remains approximately 6m (with wall thickness)', `got ${preSize.z.toFixed(2)}m`);
  assert(Math.abs(preSize.y - 2.9) < 0.25, 'Overall height matches wall height + floor (approx 2.9m)', `got ${preSize.y.toFixed(2)}m`);

  // GLTFExporter export
  const exporter = new GLTFExporter();
  await new Promise((resolve, reject) => {
    exporter.parse(
      m2SceneGroup,
      (glbBuffer) => {
        const glbByteLength = glbBuffer.byteLength;
        assert(glbByteLength > 1000, 'GLTFExporter produced valid binary GLB buffer', `${(glbByteLength / 1024).toFixed(1)} KB`);

        // Save physical file to reconstructed_scene.glb
        fs.writeFileSync('./reconstructed_scene.glb', Buffer.from(glbBuffer));
        assert(fs.existsSync('./reconstructed_scene.glb'), 'reconstructed_scene.glb written successfully to disk');

        // Reload using GLTFLoader
        const loader = new GLTFLoader();
        loader.parse(
          glbBuffer,
          '',
          (gltf) => {
            assert(gltf && gltf.scene, 'GLTFLoader parsed reconstructed_scene.glb successfully');
            let meshCount = 0;
            gltf.scene.traverse(child => {
              if (child.isMesh) meshCount++;
            });
            // 8 walls + 4 floors + 4*5 door meshes (20) + 4*7 window meshes (28) = 60 meshes
            assert(meshCount >= 50, `Architectural meshes preserved in GLB: ${meshCount} meshes detected`);

            const reloadedBox = new THREE.Box3().setFromObject(gltf.scene);
            const reloadedSize = new THREE.Vector3();
            reloadedBox.getSize(reloadedSize);

            assert(Math.abs(reloadedSize.x - preSize.x) < 0.01, 'GLB reload: X dimension matches pre-export within 1cm');
            assert(Math.abs(reloadedSize.y - preSize.y) < 0.01, 'GLB reload: Y dimension matches pre-export within 1cm');
            assert(Math.abs(reloadedSize.z - preSize.z) < 0.01, 'GLB reload: Z dimension matches pre-export within 1cm');
            assert(Math.abs(reloadedSize.x - 8.2) < 0.25 && Math.abs(reloadedSize.z - 6.2) < 0.25,
              'GLB reload: overall dimensions remain approximately 8m × 6m with no unexpected scaling');

            resolve();
          },
          (err) => {
            console.error('FAIL: GLTFLoader failed to parse exported GLB:', err);
            reject(err);
          }
        );
      },
      (err) => {
        console.error('FAIL: GLTFExporter error:', err);
        reject(err);
      },
      { binary: true }
    );
  });

  // =========================================================================
  // PART C: REAL VALIDATED MEMBER 2 SCENE TESTS (validated_scene.json)
  // =========================================================================

  console.log('\n--- TEST GROUP 14: VALIDATED SCENE PARSING & SCHEMA VALIDATION ---');
  const rawValidatedScene = JSON.parse(fs.readFileSync('./src/data/validated_scene.json', 'utf-8'));
  const valSceneResult = SceneValidator.validate(rawValidatedScene);
  const valScene = valSceneResult.scene;

  assert(valSceneResult.isValid === true, 'validated_scene.json validates successfully');
  assert(valSceneResult.errors.length === 0, 'Zero validation errors on validated_scene.json');
  assert(valScene.walls.length === 14, '14 walls loaded from validated_scene.json');
  assert(valScene.doors.length === 4, '4 doors loaded from validated_scene.json');
  assert(valScene.windows.length === 4, '4 windows loaded from validated_scene.json');
  assert(valScene.rooms.length === 3, '3 rooms loaded from validated_scene.json');
  assert(valScene.units === 'meters', 'Units: meters');
  assert(valScene.coordinate_system === 'world', 'Coordinate system: world');
  assert(valScene.scale && valScene.scale.meters_per_pixel === 0.02, 'Scale: meters_per_pixel = 0.02');
  assert(valScene.wall_height === 3.0, 'Wall height = 3.0m (defaults.wall_height)');
  assert(valScene.settings.doorHeight === 2.1, 'Door height = 2.1m (defaults.door_height)');
  assert(valScene.settings.windowHeight === 1.2, 'Window height = 1.2m (defaults.window_height)');
  assert(valScene.settings.windowSillHeight === 0.9, 'Window sill height = 0.9m (defaults.window_sill_height)');
  assert(valScene.validation && valScene.validation.valid === true, 'Validation status: valid=true');
  assert(valSceneResult.warnings.length >= 15, `All 15 Member 2 validation issues preserved (${valSceneResult.warnings.length} warnings)`);

  // Verify processed geometry used instead of pixel source geometry
  console.log('\n--- TEST GROUP 15: PROCESSED METRIC GEOMETRY PREFERRED OVER SOURCE ---');
  assert(valScene.walls[0].start[0] === 4.76 && valScene.walls[0].start[1] === 0.36,
    'w1 uses processed metric start [4.76, 0.36] instead of source pixel [238.0, 18.0]');
  assert(valScene.walls[0].thickness === 0.32,
    'w1 uses processed metric thickness 0.32m instead of source thickness 16.0px');
  assert(valScene.doors[0].center[0] === 6.878 && valScene.doors[0].center[1] === 2.924,
    'd1 uses processed metric center [6.878, 2.924]');
  assert(valScene.windows[0].center[0] === 5.4 && valScene.windows[0].center[1] === 0.38,
    'win1 uses processed metric center [5.4, 0.38]');
  assert(valScene.rooms[0].polygon[0][0] === 1.7 && valScene.rooms[0].polygon[0][1] === 0.54,
    'room1 uses processed metric polygon start [1.7, 0.54] instead of source pixel [85.0, 27.0]');

  // Wall metric length verification (Section 11)
  console.log('\n--- TEST GROUP 16: VALIDATED SCENE WALL METRIC LENGTHS ---');
  const valWallGen = new WallGenerator();
  const { meshes: valWallMeshes, wallMap: valWallMap } = valWallGen.generate(valScene.walls, valScene.settings);
  assert(valWallMeshes.length === 14, 'WallGenerator created 14 wall meshes for validated scene');

  const vw1 = valWallMap.get('w1');
  assert(vw1 && Math.abs(vw1.length - 3.17) < 0.01, 'w1 metric length ≈ 3.17m', `got ${vw1?.length.toFixed(4)}m`);

  const vw2 = valWallMap.get('w2');
  assert(vw2 && Math.abs(vw2.length - 1.0812) < 0.01, 'w2 metric length ≈ 1.0812m', `got ${vw2?.length.toFixed(4)}m`);

  const vw3 = valWallMap.get('w3');
  assert(vw3 && Math.abs(vw3.length - 1.1804) < 0.01, 'w3 metric length ≈ 1.1804m', `got ${vw3?.length.toFixed(4)}m`);

  const vw4 = valWallMap.get('w4');
  assert(vw4 && Math.abs(vw4.length - 2.58) < 0.01, 'w4 metric length ≈ 2.58m', `got ${vw4?.length.toFixed(4)}m`);

  const vw5 = valWallMap.get('w5');
  assert(vw5 && Math.abs(vw5.length - 2.38) < 0.01, 'w5 metric length ≈ 2.38m', `got ${vw5?.length.toFixed(4)}m`);

  const vw6 = valWallMap.get('w6');
  assert(vw6 && Math.abs(vw6.length - 2.5446) < 0.01, 'w6 metric length ≈ 2.5446m', `got ${vw6?.length.toFixed(4)}m`);

  const vw7 = valWallMap.get('w7');
  assert(vw7 && Math.abs(vw7.length - 2.5804) < 0.01, 'w7 metric length ≈ 2.5804m', `got ${vw7?.length.toFixed(4)}m`);

  const vw8 = valWallMap.get('w8');
  assert(vw8 && Math.abs(vw8.length - 1.004) < 0.02, 'w8 metric length ≈ 1.004m (supplied 0.999m)', `got ${vw8?.length.toFixed(4)}m`);

  const vw9 = valWallMap.get('w9');
  assert(vw9 && Math.abs(vw9.length - 0.24) < 0.01, 'w9 metric length ≈ 0.24m (short wall preserved)', `got ${vw9?.length.toFixed(4)}m`);

  const vw10 = valWallMap.get('w10');
  assert(vw10 && Math.abs(vw10.length - 0.6986) < 0.01, 'w10 metric length ≈ 0.6986m', `got ${vw10?.length.toFixed(4)}m`);

  const vw11 = valWallMap.get('w11');
  assert(vw11 && Math.abs(vw11.length - 0.5814) < 0.01, 'w11 metric length ≈ 0.5814m', `got ${vw11?.length.toFixed(4)}m`);

  const vw12 = valWallMap.get('w12');
  assert(vw12 && Math.abs(vw12.length - 4.68) < 0.01, 'w12 metric length ≈ 4.68m', `got ${vw12?.length.toFixed(4)}m`);

  const vw13 = valWallMap.get('w13');
  assert(vw13 && Math.abs(vw13.length - 0.5036) < 0.01, 'w13 metric length ≈ 0.5036m', `got ${vw13?.length.toFixed(4)}m`);

  const vw14 = valWallMap.get('w14');
  assert(vw14 && Math.abs(vw14.length - 2.74) < 0.01, 'w14 metric length ≈ 2.74m', `got ${vw14?.length.toFixed(4)}m`);

  // Door tests (Section 11: d1 -> w8, d2 -> w10, d3 -> w11, d4 -> w14)
  console.log('\n--- TEST GROUP 17: VALIDATED SCENE DOOR HOST ATTACHMENTS ---');
  const valDoorGen = new DoorGenerator();
  const valDoorObjs = valDoorGen.generate(valScene.doors, valWallMap, valScene.settings);
  assert(valDoorObjs.length === 4, 'DoorGenerator created 4 door groups');

  const vDoorMap = new Map();
  valDoorObjs.forEach(d => vDoorMap.set(d.userData.id, d));

  const vd1 = vDoorMap.get('d1');
  assert(vd1 && vd1.userData.wallId === 'w8', 'd1 attached to host wall w8');
  assert(vd1 && Math.abs(vd1.position.x - 6.878) < 0.001 && Math.abs(vd1.position.z - 2.924) < 0.001,
    'd1 positioned at center [6.878, 2.924]');
  assert(vd1 && vd1.userData.width === 0.48, 'd1 width = 0.48m');

  const vd2 = vDoorMap.get('d2');
  assert(vd2 && vd2.userData.wallId === 'w10', 'd2 attached to host wall w10');
  assert(vd2 && Math.abs(vd2.position.x - 7.48) < 0.001 && Math.abs(vd2.position.z - 3.7) < 0.001,
    'd2 positioned at center [7.48, 3.7]');
  assert(vd2 && vd2.userData.width === 0.68, 'd2 width = 0.68m');

  const vd3 = vDoorMap.get('d3');
  assert(vd3 && vd3.userData.wallId === 'w11', 'd3 attached to host wall w11');
  assert(vd3 && Math.abs(vd3.position.x - 1.56) < 0.001 && Math.abs(vd3.position.z - 3.8) < 0.001,
    'd3 positioned at center [1.56, 3.8]');
  assert(vd3 && vd3.userData.width === 0.60, 'd3 width = 0.60m (wider than wall w11 0.58m, preserved without crashing)');

  const vd4 = vDoorMap.get('d4');
  assert(vd4 && vd4.userData.wallId === 'w14', 'd4 attached to host wall w14');
  assert(vd4 && Math.abs(vd4.position.x - 7.32) < 0.001 && Math.abs(vd4.position.z - 4.38) < 0.001,
    'd4 positioned at center [7.32, 4.38]');
  assert(vd4 && vd4.userData.width === 0.74, 'd4 width = 0.74m');

  // Window tests (Section 11: win1 -> w3, win2 -> w3, win3 -> w2, win4 -> w5)
  console.log('\n--- TEST GROUP 18: VALIDATED SCENE WINDOW HOST ATTACHMENTS ---');
  const valWindowGen = new WindowGenerator();
  const valWindowObjs = valWindowGen.generate(valScene.windows, valWallMap, valScene.settings);
  assert(valWindowObjs.length === 4, 'WindowGenerator created 4 window groups');

  const vWinMap = new Map();
  valWindowObjs.forEach(w => vWinMap.set(w.userData.id, w));

  const vwin1 = vWinMap.get('win1');
  assert(vwin1 && vwin1.userData.wallId === 'w3', 'win1 attached to host wall w3');
  assert(vwin1 && Math.abs(vwin1.position.x - 5.4) < 0.001 && Math.abs(vwin1.position.z - 0.38) < 0.001,
    'win1 positioned at center [5.4, 0.38]');
  assert(vwin1 && vwin1.userData.width === 0.34, 'win1 width = 0.34m');

  const vwin2 = vWinMap.get('win2');
  assert(vwin2 && vwin2.userData.wallId === 'w3', 'win2 attached to host wall w3');
  assert(vwin2 && Math.abs(vwin2.position.x - 6.58) < 0.001 && Math.abs(vwin2.position.z - 0.35) < 0.001,
    'win2 positioned at center [6.58, 0.35]');
  assert(vwin2 && vwin2.userData.width === 0.38, 'win2 width = 0.38m');

  const vwin3 = vWinMap.get('win3');
  assert(vwin3 && vwin3.userData.wallId === 'w2', 'win3 attached to host wall w2');
  assert(vwin3 && Math.abs(vwin3.position.x - 1.54) < 0.001 && Math.abs(vwin3.position.z - 1.46) < 0.001,
    'win3 positioned at center [1.54, 1.46]');
  assert(vwin3 && vwin3.userData.width === 1.38, 'win3 width = 1.38m (wider than wall w2 1.08m, preserved without crashing)');

  const vwin4 = vWinMap.get('win4');
  assert(vwin4 && vwin4.userData.wallId === 'w5', 'win4 attached to host wall w5');
  assert(vwin4 && Math.abs(vwin4.position.x - 10.08) < 0.001 && Math.abs(vwin4.position.z - 2.74) < 0.001,
    'win4 positioned at center [10.08, 2.74]');
  assert(vwin4 && vwin4.userData.width === 0.90, 'win4 width = 0.90m');

  // Room tests (Section 11)
  console.log('\n--- TEST GROUP 19: VALIDATED SCENE ROOMS, POLYGONS & AREAS ---');
  const valFloorGen = new FloorGenerator();
  const valFloorMeshes = valFloorGen.generate(valScene.rooms, valScene.settings);
  assert(valFloorMeshes.length === 3, 'FloorGenerator created 3 floor meshes');

  const valRoomGen = new RoomGenerator();
  const { meshes: valRoomMeshes, roomInfos: valRoomInfos } = valRoomGen.generate(valScene.rooms);
  assert(valRoomMeshes.length === 3, 'RoomGenerator created 3 room boundary meshes');
  assert(valRoomInfos.length === 3, 'RoomGenerator returned 3 room infos');

  const vRoomMap = new Map();
  valRoomInfos.forEach(r => vRoomMap.set(r.id, r));

  const vr1 = vRoomMap.get('room1');
  assert(vr1 && vr1.polygon.length === 10, 'room1 polygon has 10 vertices');
  assert(vr1 && Math.abs(vr1.area - 18.586) < 0.01, 'room1 area ≈ 18.586 m²', `got ${vr1?.area}`);
  assert(vr1 && Math.abs(vr1.centroid[0] - 4.217) < 0.01 && Math.abs(vr1.centroid[1] - 2.5142) < 0.01,
    'room1 centroid ≈ [4.217, 2.5142]', `got [${vr1?.centroid.join(', ')}]`);

  const vr2 = vRoomMap.get('room2');
  assert(vr2 && vr2.polygon.length === 4, 'room2 polygon has 4 vertices');
  assert(vr2 && Math.abs(vr2.area - 2.277) < 0.01, 'room2 area ≈ 2.277 m²', `got ${vr2?.area}`);
  assert(vr2 && Math.abs(vr2.centroid[0] - 6.925) < 0.01 && Math.abs(vr2.centroid[1] - 1.6862) < 0.01,
    'room2 centroid ≈ [6.925, 1.6862]');

  const vr3 = vRoomMap.get('room3');
  assert(vr3 && vr3.polygon.length === 4, 'room3 polygon has 4 vertices');
  assert(vr3 && Math.abs(vr3.area - 9.2004) < 0.01, 'room3 area ≈ 9.2004 m²', `got ${vr3?.area}`);
  assert(vr3 && Math.abs(vr3.centroid[0] - 8.75) < 0.01 && Math.abs(vr3.centroid[1] - 2.41) < 0.01,
    'room3 centroid ≈ [8.75, 2.41]');

  // Dimension Overlay test
  const valDimGen = new DimensionRenderer();
  const valDimObjs = valDimGen.generate(valWallMap, 'm');
  assert(valDimObjs.length === 1, 'DimensionRenderer created dimension markers for validated scene');

  // GLB Export & Reload Verification for validated scene (Section 13)
  console.log('\n--- TEST GROUP 20: VALIDATED SCENE GLB EXPORT & RELOAD ROUNDTRIP ---');
  const valSceneGroup = new THREE.Group();
  valSceneGroup.name = 'ReconstructedValidatedScene';

  const gValWalls = new THREE.Group();
  gValWalls.name = 'Walls';
  valWallMeshes.forEach(m => gValWalls.add(m));
  valSceneGroup.add(gValWalls);

  const gValFloors = new THREE.Group();
  gValFloors.name = 'Floors';
  valFloorMeshes.forEach(m => gValFloors.add(m));
  valSceneGroup.add(gValFloors);

  const gValDoors = new THREE.Group();
  gValDoors.name = 'Doors';
  valDoorObjs.forEach(d => gValDoors.add(d));
  valSceneGroup.add(gValDoors);

  const gValWindows = new THREE.Group();
  gValWindows.name = 'Windows';
  valWindowObjs.forEach(w => gValWindows.add(w));
  valSceneGroup.add(gValWindows);

  const valPreBox = new THREE.Box3().setFromObject(valSceneGroup);
  const valPreSize = new THREE.Vector3();
  valPreBox.getSize(valPreSize);
  console.log(`  Validated Scene Bounds: Width(X)=${valPreSize.x.toFixed(2)}m, Height(Y)=${valPreSize.y.toFixed(2)}m, Depth(Z)=${valPreSize.z.toFixed(2)}m`);

  assert(Math.abs(valPreSize.x - 8.9) < 0.6, 'Validated scene overall width is approx 8.9m', `got ${valPreSize.x.toFixed(2)}m`);
  assert(Math.abs(valPreSize.z - 4.4) < 0.6, 'Validated scene overall depth is approx 4.4m', `got ${valPreSize.z.toFixed(2)}m`);
  assert(Math.abs(valPreSize.y - 3.1) < 0.3, 'Validated scene overall height matches 3.0m wall + floor thickness', `got ${valPreSize.y.toFixed(2)}m`);

  await new Promise((resolve, reject) => {
    exporter.parse(
      valSceneGroup,
      (glbBuffer) => {
        const glbByteLength = glbBuffer.byteLength;
        assert(glbByteLength > 1000, 'GLTFExporter produced valid binary GLB for validated scene', `${(glbByteLength / 1024).toFixed(1)} KB`);

        fs.writeFileSync('./reconstructed_scene.glb', Buffer.from(glbBuffer));
        assert(fs.existsSync('./reconstructed_scene.glb'), 'reconstructed_scene.glb written with validated scene data');

        const loader = new GLTFLoader();
        loader.parse(
          glbBuffer,
          '',
          (gltf) => {
            assert(gltf && gltf.scene, 'GLTFLoader parsed reconstructed_scene.glb (validated scene) successfully');
            let meshCount = 0;
            gltf.scene.traverse(child => {
              if (child.isMesh) meshCount++;
            });
            // 14 walls + 3 floors + 4*5 doors (20) + 4*7 windows (28) = 65 meshes
            assert(meshCount >= 50, `Architectural meshes preserved in GLB: ${meshCount} meshes detected`);

            const reloadedBox = new THREE.Box3().setFromObject(gltf.scene);
            const reloadedSize = new THREE.Vector3();
            reloadedBox.getSize(reloadedSize);

            assert(Math.abs(reloadedSize.x - valPreSize.x) < 0.01, 'GLB reload: X dimension matches pre-export within 1cm');
            assert(Math.abs(reloadedSize.y - valPreSize.y) < 0.01, 'GLB reload: Y dimension matches pre-export within 1cm');
            assert(Math.abs(reloadedSize.z - valPreSize.z) < 0.01, 'GLB reload: Z dimension matches pre-export within 1cm');
            assert(gltf.scene.up.y === 1, 'GLB reload: orientation preserved (Y is up-axis)');

            resolve();
          },
          (err) => {
            console.error('FAIL: GLTFLoader failed to parse exported GLB:', err);
            reject(err);
          }
        );
      },
      (err) => {
        console.error('FAIL: GLTFExporter error:', err);
        reject(err);
      },
      { binary: true }
    );
  });

  console.log('\n======================================================');
  console.log(`RESULTS: ${passedTests} / ${totalTests} TESTS PASSED (${((passedTests / totalTests) * 100).toFixed(1)}%)`);
  console.log('======================================================\n');

  if (passedTests === totalTests) {
    process.exit(0);
  } else {
    process.exit(1);
  }
}

runTestSuite().catch(err => {
  console.error('Test execution fatal error:', err);
  process.exit(1);
});

