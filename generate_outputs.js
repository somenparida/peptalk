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

import fs from 'fs';
import path from 'path';
import * as THREE from 'three';
import { SceneValidator } from './src/data/SceneValidator.js';
import { TopologyRepairer } from './src/geometry/TopologyRepairer.js';
import { WallGenerator } from './src/scene/WallGenerator.js';
import { FloorGenerator } from './src/scene/FloorGenerator.js';
import { DoorGenerator } from './src/scene/DoorGenerator.js';
import { WindowGenerator } from './src/scene/WindowGenerator.js';
import { RoomGenerator } from './src/scene/RoomGenerator.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

async function generateOutputs() {
  console.log('--- Generating Cleaned Architectural Scene and Artifacts ---');

  const outDir = './geometry_output';
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  // 1. Load Real Member 2 input
  const rawScene = JSON.parse(fs.readFileSync('./src/data/validated_scene.json', 'utf-8'));

  // 2. Perform Validation with Topology Repairs
  const validationResult = SceneValidator.validate(rawScene, { repair: true });
  const cleanedScene = validationResult.scene;
  const report = validationResult.validationReport;

  // 3. Save Cleaned Scene JSON
  const cleanedJsonPath = path.join(outDir, 'validated_scene.json');
  fs.writeFileSync(cleanedJsonPath, JSON.stringify(cleanedScene, null, 2), 'utf-8');
  console.log(`✓ Wrote cleaned scene JSON to ${cleanedJsonPath} (${(fs.statSync(cleanedJsonPath).size / 1024).toFixed(1)} KB)`);

  // Also save to src/data/cleaned_scene.json for Vite frontend import
  fs.writeFileSync('./src/data/cleaned_scene.json', JSON.stringify(cleanedScene, null, 2), 'utf-8');

  // 4. Save Detailed Validation Report
  const reportPath = path.join(outDir, 'validation_report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf-8');
  console.log(`✓ Wrote validation report to ${reportPath} (${(fs.statSync(reportPath).size / 1024).toFixed(1)} KB)`);

  // 5. Generate 3D Reconstruction with Physical Openings
  const wallGen = new WallGenerator();
  const { meshes: wallMeshes, wallMap } = wallGen.generate(cleanedScene.walls, cleanedScene.settings, {
    doors: cleanedScene.doors,
    windows: cleanedScene.windows,
    cutOpenings: true
  });

  const floorGen = new FloorGenerator();
  const floorMeshes = floorGen.generate(cleanedScene.rooms, cleanedScene.settings);

  const doorGen = new DoorGenerator();
  const doorObjs = doorGen.generate(cleanedScene.doors, wallMap, cleanedScene.settings);

  const winGen = new WindowGenerator();
  const winObjs = winGen.generate(cleanedScene.windows, wallMap, cleanedScene.settings);

  const roomGen = new RoomGenerator();
  const { meshes: roomMeshes } = roomGen.generate(cleanedScene.rooms);

  const sceneGroup = new THREE.Group();
  sceneGroup.name = 'ReconstructedArchitecture';

  const gWalls = new THREE.Group();
  gWalls.name = 'Walls';
  wallMeshes.forEach(m => gWalls.add(m));
  sceneGroup.add(gWalls);

  const gFloors = new THREE.Group();
  gFloors.name = 'Floors';
  floorMeshes.forEach(m => gFloors.add(m));
  sceneGroup.add(gFloors);

  const gDoors = new THREE.Group();
  gDoors.name = 'Doors';
  doorObjs.forEach(m => gDoors.add(m));
  sceneGroup.add(gDoors);

  const gWindows = new THREE.Group();
  gWindows.name = 'Windows';
  winObjs.forEach(m => gWindows.add(m));
  sceneGroup.add(gWindows);

  const gRooms = new THREE.Group();
  gRooms.name = 'Rooms';
  roomMeshes.forEach(m => gRooms.add(m));
  sceneGroup.add(gRooms);

  // 6. GLB Export
  const exporter = new GLTFExporter();
  const glbBuffer = await new Promise((resolve, reject) => {
    exporter.parse(
      sceneGroup,
      (buf) => resolve(buf),
      reject,
      { binary: true }
    );
  });

  const glbPath = path.join(outDir, 'reconstructed_scene.glb');
  fs.writeFileSync(glbPath, Buffer.from(glbBuffer));
  // Also update root reconstructed_scene.glb
  fs.writeFileSync('./reconstructed_scene.glb', Buffer.from(glbBuffer));

  console.log(`✓ Wrote GLB 3D model to ${glbPath} (${(fs.statSync(glbPath).size / 1024).toFixed(1)} KB)`);

  // 7. Verify Reload with GLTFLoader
  const loader = new GLTFLoader();
  await new Promise((resolve, reject) => {
    loader.parse(
      glbBuffer,
      '',
      (gltf) => {
        let count = 0;
        gltf.scene.traverse(node => { if (node.isMesh) count++; });
        console.log(`✓ Reloaded and verified GLB: ${count} architectural meshes confirmed.`);
        resolve();
      },
      reject
    );
  });

  console.log('--- All Outputs Successfully Generated and Verified ---');
}

generateOutputs().catch(err => {
  console.error('Failed to generate outputs:', err);
  process.exit(1);
});
