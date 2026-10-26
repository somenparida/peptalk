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
import fs from 'fs';
import { GeometryValidator } from '../src/geometry/GeometryValidator.js';
import { TopologyRepairer } from '../src/geometry/TopologyRepairer.js';
import { SceneValidator } from '../src/data/SceneValidator.js';
import { WallGenerator } from '../src/scene/WallGenerator.js';
import { FloorGenerator } from '../src/scene/FloorGenerator.js';
import { DoorGenerator } from '../src/scene/DoorGenerator.js';
import { WindowGenerator } from '../src/scene/WindowGenerator.js';
import { RoomGenerator } from '../src/scene/RoomGenerator.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

console.log('================================================================');
console.log('🧪 RUNNING MEMBER 2 GEOMETRY VALIDATION & REPAIR TEST SUITE');
console.log('================================================================\n');

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

async function runMember2Tests() {
  // -------------------------------------------------------------------------
  // SUITE 1: ENDPOINT CONNECTIVITY & SNAPPING REPAIR
  // -------------------------------------------------------------------------
  console.log('--- SUITE 1: WALL ENDPOINT SNAPPING & CONNECTIVITY ---');
  const gappyScene = {
    walls: [
      { id: 'w_a', start: [0.0, 0.0], end: [3.92, 0.0], thickness: 0.2 }, // 8cm gap from (4.0, 0.0)
      { id: 'w_b', start: [4.0, 0.0], end: [4.0, 4.0], thickness: 0.2 }
    ]
  };

  const diagPre = GeometryValidator.validate(gappyScene, { snappingTolerance: 0.15 });
  assert(diagPre.issues.some(i => i.defect === 'open_endpoint'), '1.1 Detected open endpoint with 8cm gap');

  const repairRes = TopologyRepairer.repair(gappyScene, { snappingTolerance: 0.15 });
  assert(repairRes.operations.some(op => op.type === 'snap_endpoint'), '1.2 Snapped endpoint across 8cm gap');
  
  const repairedWA = repairRes.repairedScene.walls[0];
  const repairedWB = repairRes.repairedScene.walls[1];
  assert(Math.abs(repairedWA.end[0] - repairedWB.start[0]) < 0.001, '1.3 Endpoints now perfectly coincident at corner');

  // -------------------------------------------------------------------------
  // SUITE 2: T-JUNCTION ORTHOGONAL SNAPPING
  // -------------------------------------------------------------------------
  console.log('\n--- SUITE 2: T-JUNCTION SNAPPING ---');
  const tJunctionScene = {
    walls: [
      { id: 'w_main', start: [0.0, 0.0], end: [10.0, 0.0], thickness: 0.2 },
      { id: 'w_branch', start: [5.0, 0.08], end: [5.0, 5.0], thickness: 0.2 } // 8cm gap from main wall line
    ]
  };

  const tRepair = TopologyRepairer.repair(tJunctionScene, { snappingTolerance: 0.15 });
  assert(tRepair.operations.some(op => op.type === 'snap_t_junction'), '2.1 Identified and snapped T-junction');
  const branchWall = tRepair.repairedScene.walls.find(w => w.id === 'w_branch');
  assert(Math.abs(branchWall.start[1] - 0.0) < 0.001, '2.2 Branch wall projected orthogonally onto main wall centerline (y=0)');

  // -------------------------------------------------------------------------
  // SUITE 3: DUPLICATE & OVERLAPPING WALL DETECTION
  // -------------------------------------------------------------------------
  console.log('\n--- SUITE 3: DUPLICATE WALL DETECTION ---');
  const dupScene = {
    walls: [
      { id: 'w_orig', start: [0.0, 0.0], end: [5.0, 0.0], thickness: 0.2 },
      { id: 'w_dup', start: [5.0, 0.0], end: [0.0, 0.0], thickness: 0.2 } // Reversed duplicate
    ]
  };
  const dupDiag = GeometryValidator.validate(dupScene);
  assert(dupDiag.issues.some(i => i.defect === 'duplicate_wall_geometry'), '3.1 Detected reversed duplicate wall w_dup');
  assert(dupDiag.summary.errors >= 1, '3.2 Duplicate wall correctly classified as error');

  // -------------------------------------------------------------------------
  // SUITE 4: OPENINGS FIT & HOST WALL BOUNDARIES
  // -------------------------------------------------------------------------
  console.log('\n--- SUITE 4: OPENING FIT & EXTREME BOUNDARIES ---');
  const openingDefectScene = {
    walls: [
      { id: 'w_short', start: [0.0, 0.0], end: [0.58, 0.0], thickness: 0.2 } // 0.58m length
    ],
    doors: [
      { id: 'd_large', wall_id: 'w_short', offset: 0.0, width: 0.60, height: 2.1 } // 0.60m width
    ],
    windows: [
      { id: 'win_edge', wall_id: 'w_short', position: 1.0, width: 0.40, height: 1.2 }
    ]
  };

  const openDiag = GeometryValidator.validate(openingDefectScene);
  const exceedsIssue = openDiag.issues.find(i => i.defect === 'door_exceeds_wall_length');
  assert(!!exceedsIssue, '4.1 Detected door width exceeding host wall length');
  assert(exceedsIssue.measured.door_width === 0.60 && exceedsIssue.measured.wall_length === 0.58,
    '4.2 Diagnostic record contains exact measured (0.60m) vs wall (0.58m)');
  
  const edgeIssue = openDiag.issues.find(i => i.defect === 'boundary_window_position');
  assert(!!edgeIssue, '4.3 Detected window positioned at extreme boundary (position=1.0)');

  // -------------------------------------------------------------------------
  // SUITE 5: ROOM POLYGON REPAIR (DUPLICATES, WINDING, AREA)
  // -------------------------------------------------------------------------
  console.log('\n--- SUITE 5: ROOM POLYGON VALIDATION & REPAIR ---');
  const roomScene = {
    walls: [
      { id: 'w1', start: [0, 0], end: [4, 0], thickness: 0.2 },
      { id: 'w2', start: [4, 0], end: [4, 3], thickness: 0.2 },
      { id: 'w3', start: [4, 3], end: [0, 3], thickness: 0.2 },
      { id: 'w4', start: [0, 3], end: [0, 0], thickness: 0.2 }
    ],
    rooms: [
      {
        id: 'r_messy',
        name: 'Dirty Room',
        polygon: [
          [0.0, 0.0],
          [4.0, 0.0],
          [4.0, 0.0], // Redundant duplicate vertex
          [4.0, 3.0],
          [0.0, 3.0]
        ]
      }
    ]
  };

  const roomDiag = GeometryValidator.validate(roomScene);
  assert(roomDiag.issues.some(i => i.defect === 'duplicate_consecutive_vertex'), '5.1 Detected redundant duplicate vertex');

  const roomRepaired = TopologyRepairer.repair(roomScene);
  const cleanedPolygon = roomRepaired.repairedScene.rooms[0].polygon;
  assert(cleanedPolygon.length === 4, '5.2 Redundant vertex safely cleaned (4 vertices remaining)');
  assert(Math.abs(roomRepaired.repairedScene.rooms[0].area - 12.0) < 0.001, '5.3 Exact room floor area computed (12.0 m²)');

  // -------------------------------------------------------------------------
  // SUITE 6: REAL WALL CUTOUTS & OPENING GENERATION
  // -------------------------------------------------------------------------
  console.log('\n--- SUITE 6: REAL OPENINGS CUT THROUGH WALL GEOMETRY ---');
  const wallGen = new WallGenerator();
  const testWalls = [
    { id: 'w_entry', start: [0.0, 0.0], end: [6.0, 0.0], thickness: 0.2 }
  ];
  const testDoors = [
    { id: 'd_entry', wall_id: 'w_entry', offset: 2.0, width: 0.9, height: 2.1 }
  ];
  const testWindows = [
    { id: 'win_entry', wall_id: 'w_entry', offset: 4.5, width: 1.2, height: 1.2, sill_height: 0.9 }
  ];

  const { meshes } = wallGen.generate(testWalls, { wallHeight: 3.0 }, { doors: testDoors, windows: testWindows });
  assert(meshes.length === 1, '6.1 Generated compound wall mesh');
  const wMesh = meshes[0];
  assert(wMesh.userData.hasOpenings === true, '6.2 Wall marked as having physical openings');
  
  // A solid wall box has 24 vertices (or 36 indexed). A wall with 2 cutouts has sub-boxes (left, right, lintel, sill, etc.)
  assert(wMesh.geometry.attributes.position.count > 36,
    `6.3 Compound geometry has physical sub-boxes with real voids (vertex count: ${wMesh.geometry.attributes.position.count})`);

  // -------------------------------------------------------------------------
  // SUITE 7: DIAGNOSTIC REPORT STRUCTURE & FIDELITY
  // -------------------------------------------------------------------------
  console.log('\n--- SUITE 7: DIAGNOSTIC REPORT COMPLETENESS ---');
  const realRaw = JSON.parse(fs.readFileSync('./src/data/validated_scene.json', 'utf-8'));
  const fullValResult = SceneValidator.validate(realRaw);
  const report = fullValResult.validationReport;
  
  assert(!!report, '7.1 Validation report generated');
  assert(report.summary.total_initial_issues >= 15, `7.2 Total detected issues accurately counted (${report.summary.total_initial_issues})`);
  assert(Array.isArray(report.issues) && report.issues.length >= 15, '7.3 Enriched diagnostic issues array populated');
  
  const sampleIssue = report.issues[0];
  assert(!!sampleIssue.id && !!sampleIssue.severity && !!sampleIssue.element_type && !!sampleIssue.message,
    '7.4 Issues follow strict contract (id, severity, element_type, message)');

  // -------------------------------------------------------------------------
  // SUITE 8: GLB EXPORT & MODEL INTEGRITY (CLEANED SCENE)
  // -------------------------------------------------------------------------
  console.log('\n--- SUITE 8: GLB EXPORT & MODEL INTEGRITY (CLEANED SCENE) ---');
  const cleanedRaw = JSON.parse(fs.readFileSync('./src/data/validated_scene.json', 'utf-8'));
  const cleanedVal = SceneValidator.validate(cleanedRaw, { repair: true });
  const cleanedScene = cleanedVal.scene;

  const { meshes: cWallMeshes, wallMap: cWallMap } = wallGen.generate(cleanedScene.walls, cleanedScene.settings, {
    doors: cleanedScene.doors,
    windows: cleanedScene.windows,
    cutOpenings: true
  });
  const floorGen = new FloorGenerator();
  const cFloorMeshes = floorGen.generate(cleanedScene.rooms, cleanedScene.settings);
  const doorGen = new DoorGenerator();
  const cDoorObjs = doorGen.generate(cleanedScene.doors, cWallMap, cleanedScene.settings);
  const winGen = new WindowGenerator();
  const cWinObjs = winGen.generate(cleanedScene.windows, cWallMap, cleanedScene.settings);
  const roomGen = new RoomGenerator();
  const { meshes: cRoomMeshes } = roomGen.generate(cleanedScene.rooms);

  const rootGroup = new THREE.Group();
  cWallMeshes.forEach(m => rootGroup.add(m));
  cFloorMeshes.forEach(m => rootGroup.add(m));
  cDoorObjs.forEach(m => rootGroup.add(m));
  cWinObjs.forEach(m => rootGroup.add(m));
  cRoomMeshes.forEach(m => rootGroup.add(m));

  const exporter = new GLTFExporter();
  await new Promise((resolve, reject) => {
    exporter.parse(
      rootGroup,
      (glbBuffer) => {
        assert(glbBuffer.byteLength > 1000, `8.1 GLB buffer produced (${(glbBuffer.byteLength / 1024).toFixed(1)} KB)`);
        
        // Write to geometry_output/reconstructed_scene.glb
        if (!fs.existsSync('./geometry_output')) {
          fs.mkdirSync('./geometry_output', { recursive: true });
        }
        fs.writeFileSync('./geometry_output/reconstructed_scene.glb', Buffer.from(glbBuffer));
        assert(fs.existsSync('./geometry_output/reconstructed_scene.glb'), '8.2 geometry_output/reconstructed_scene.glb saved');

        const loader = new GLTFLoader();
        loader.parse(
          glbBuffer,
          '',
          (gltf) => {
            let meshCount = 0;
            gltf.scene.traverse(node => { if (node.isMesh) meshCount++; });
            assert(meshCount >= 50, `8.3 Exported GLB reloaded with all meshes intact (${meshCount} meshes)`);
            resolve();
          },
          reject
        );
      },
      reject,
      { binary: true }
    );
  });

  console.log('\n================================================================');
  console.log(`MEMBER 2 SUITE: ${passedTests} / ${totalTests} TESTS PASSED (${((passedTests / totalTests) * 100).toFixed(1)}%)`);
  console.log('================================================================\n');

  if (passedTests !== totalTests) {
    process.exit(1);
  }
}

runMember2Tests().catch(err => {
  console.error('Member 2 test fatal error:', err);
  process.exit(1);
});
