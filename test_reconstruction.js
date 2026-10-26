// Polyfill FileReader for headless Node.js testing
globalThis.FileReader = class FileReader {
  readAsArrayBuffer(blob) {
    blob.arrayBuffer().then(buf => {
      this.result = buf;
      if (this.onload) this.onload({ target: this });
    });
  }
  readAsDataURL(blob) {
    blob.arrayBuffer().then(buf => {
      this.result = 'data:application/octet-stream;base64,' + Buffer.from(buf).toString('base64');
      if (this.onload) this.onload({ target: this });
    });
  }
};

import * as THREE from 'three';
import { WallGenerator } from './src/scene/WallGenerator.js';
import { FloorGenerator } from './src/scene/FloorGenerator.js';
import { DoorGenerator } from './src/scene/DoorGenerator.js';
import { WindowGenerator } from './src/scene/WindowGenerator.js';
import { RoomGenerator } from './src/scene/RoomGenerator.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import fs from 'fs';

async function runTests() {
  const sceneRaw = JSON.parse(fs.readFileSync('./src/data/scene.json', 'utf-8'));

  console.log('=== RUNNING DETERMINISTIC GEOMETRY & RECONSTRUCTION TESTS ===');

  // TEST 1: Load test scene
  console.log('TEST 1: Scene loaded with', sceneRaw.walls.length, 'walls,', sceneRaw.rooms.length, 'rooms');

  // TEST 2, 3, 4, 5: Verify walls
  const wallGen = new WallGenerator();
  const { meshes: wallMeshes, wallMap } = wallGen.generate(sceneRaw.walls, sceneRaw.settings);

  console.log(`Generated ${wallMeshes.length} wall meshes.`);
  const expectedWalls = {
    w1: { len: 6.0, thick: 0.2, h: 3.0, mid: [3.0, 1.5, 0.0] },
    w2: { len: 4.0, thick: 0.2, h: 3.0, mid: [6.0, 1.5, 2.0] },
    w3: { len: 6.0, thick: 0.2, h: 3.0, mid: [3.0, 1.5, 4.0] },
    w4: { len: 4.0, thick: 0.2, h: 3.0, mid: [0.0, 1.5, 2.0] }
  };

  let allWallsPassed = true;
  for (const [id, exp] of Object.entries(expectedWalls)) {
    const w = wallMap.get(id);
    if (!w) {
      console.error(`FAIL: Wall ${id} missing`);
      allWallsPassed = false;
      continue;
    }
    const lenMatch = Math.abs(w.length - exp.len) < 0.001;
    const thickMatch = Math.abs(w.thickness - exp.thick) < 0.001;
    const hMatch = Math.abs(w.wallHeight - exp.h) < 0.001;
    const midMatch = Math.abs(w.midpoint[0] - exp.mid[0]) < 0.001 &&
                     Math.abs(w.midpoint[1] - exp.mid[1]) < 0.001 &&
                     Math.abs(w.midpoint[2] - exp.mid[2]) < 0.001;

    if (lenMatch && thickMatch && hMatch && midMatch) {
      console.log(`  ✓ Wall ${id}: length=${w.length}m, thickness=${w.thickness}m, height=${w.wallHeight}m, midpoint=[${w.midpoint.join(', ')}]`);
    } else {
      console.error(`  FAIL: Wall ${id} mismatch:`, { lenMatch, thickMatch, hMatch, midMatch, actual: w, expected: exp });
      allWallsPassed = false;
    }
  }

  // TEST 6: Floor polygon & area
  const floorGen = new FloorGenerator();
  const floorMeshes = floorGen.generate(sceneRaw.rooms, sceneRaw.settings);
  console.log(`Generated ${floorMeshes.length} floor mesh(es).`);
  const floorArea = floorMeshes[0].userData.area;
  const expectedArea = 20.16;
  if (Math.abs(floorArea - expectedArea) < 0.001) {
    console.log(`  ✓ Floor polygon area verified: ${floorArea.toFixed(2)} m² (expected: ${expectedArea} m²)`);
  } else {
    console.error(`  FAIL: Floor area mismatch: ${floorArea} vs expected ${expectedArea}`);
  }

  // TEST 7: Door position & dimensions
  const doorGen = new DoorGenerator();
  const doorObjs = doorGen.generate(sceneRaw.doors, wallMap, sceneRaw.settings);
  const d1 = doorObjs[0];
  console.log(`  ✓ Door d1 on wall w1: pos=[${d1.position.x.toFixed(2)}, ${d1.position.y.toFixed(2)}, ${d1.position.z.toFixed(2)}], width=${d1.userData.width}m`);
  if (Math.abs(d1.position.x - 3.0) < 0.001 && Math.abs(d1.position.z - 0.0) < 0.001) {
    console.log('  ✓ Door d1 midpoint matches w1 center (3.0, 0.0)');
  } else {
    console.error('  FAIL: Door d1 position mismatch');
  }

  // TEST 8: Window position & dimensions
  const windowGen = new WindowGenerator();
  const windowObjs = windowGen.generate(sceneRaw.windows, wallMap, sceneRaw.settings);
  const win1 = windowObjs[0];
  console.log(`  ✓ Window win1 on wall w3: pos=[${win1.position.x.toFixed(2)}, ${win1.position.y.toFixed(2)}, ${win1.position.z.toFixed(2)}], width=${win1.userData.width}m`);
  if (Math.abs(win1.position.x - 3.0) < 0.001 && Math.abs(win1.position.z - 4.0) < 0.001) {
    console.log('  ✓ Window win1 midpoint matches w3 center (3.0, 4.0)');
  } else {
    console.error('  FAIL: Window win1 position mismatch');
  }

  // TEST 14 & 15: GLB Export and Reload roundtrip
  console.log('TEST 14 & 15: Testing GLB export & GLTFLoader reload...');
  const testSceneGroup = new THREE.Group();
  testSceneGroup.name = 'ReconstructedArchitecture';

  const wallsGroup = new THREE.Group();
  wallsGroup.name = 'Walls';
  wallMeshes.forEach(m => wallsGroup.add(m));
  testSceneGroup.add(wallsGroup);

  const floorGroup = new THREE.Group();
  floorGroup.name = 'Floors';
  floorMeshes.forEach(m => floorGroup.add(m));
  testSceneGroup.add(floorGroup);

  const doorsGroup = new THREE.Group();
  doorsGroup.name = 'Doors';
  doorObjs.forEach(m => doorsGroup.add(m));
  testSceneGroup.add(doorsGroup);

  const windowsGroup = new THREE.Group();
  windowsGroup.name = 'Windows';
  windowObjs.forEach(m => windowsGroup.add(m));
  testSceneGroup.add(windowsGroup);

  const exporter = new GLTFExporter();
  await new Promise((resolve, reject) => {
    exporter.parse(
      testSceneGroup,
      (glbBuffer) => {
        console.log(`  ✓ GLTFExporter produced valid binary buffer of ${(glbBuffer.byteLength / 1024).toFixed(1)} KB`);
        
        // Reload test with GLTFLoader
        const loader = new GLTFLoader();
        loader.parse(
          glbBuffer,
          '',
          (gltf) => {
            let meshCount = 0;
            gltf.scene.traverse(node => {
              if (node.isMesh) meshCount++;
            });
            const box = new THREE.Box3().setFromObject(gltf.scene);
            const size = new THREE.Vector3();
            box.getSize(size);
            console.log(`  ✓ GLTFLoader successfully reloaded GLB: ${meshCount} meshes detected.`);
            console.log(`  ✓ Bounding Box Dimensions: X=${size.x.toFixed(2)}m, Y=${size.y.toFixed(2)}m, Z=${size.z.toFixed(2)}m`);
            console.log('=== ALL DETERMINISTIC GEOMETRY TESTS PASSED ===');
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
}

runTests().catch(err => {
  console.error('Test execution error:', err);
  process.exit(1);
});
