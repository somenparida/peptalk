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

  // -------------------------------------------------------------------------
  // SUITE 9: VERIFICATION OF THE SIX NOTICES & HIGH-CONFIDENCE REPAIRS
  // -------------------------------------------------------------------------
  console.log('\n--- SUITE 9: RESOLUTION OF THE SIX NOTICES & TOPOLOGY AUDIT ---');

  // 9.1 Wall w9 retained geometry
  const w9 = cleanedScene.walls.find(w => w.id === 'w9');
  assert(!!w9 && Math.abs(w9.length - 0.24) < 0.01, '9.1 Wall w9 retains exact 0.24m length without artificial stretching');

  // 9.2 Validation report w9 notices
  const w9Issues = report.issues.filter(i => i.element_id === 'w9');
  assert(w9Issues.length === 2 && w9Issues.every(i => !i.auto_repaired && i.manual_review_required),
    '9.2 Wall w9 has exactly 2 unresolved notices retained for manual architectural review');

  // 9.3 Door d1 repositioning on w8
  const cd1 = cleanedScene.doors.find(d => d.id === 'd1');
  const d1SpanStart = cd1.offset - cd1.width / 2;
  const d1SpanEnd = cd1.offset + cd1.width / 2;
  assert(cd1.wall_id === 'w8' && d1SpanStart >= 0.49 && d1SpanEnd <= 1.00,
    `9.3 Door d1 repositioned inside wall w8 (span: [${d1SpanStart.toFixed(2)}, ${d1SpanEnd.toFixed(2)}]m on 1.00m wall)`);

  // 9.4 Door d2 centering on w10
  const cd2 = cleanedScene.doors.find(d => d.id === 'd2');
  const d2SpanStart = cd2.offset - cd2.width / 2;
  const d2SpanEnd = cd2.offset + cd2.width / 2;
  assert(cd2.wall_id === 'w10' && d2SpanStart >= 0.005 && d2SpanEnd <= 0.695,
    `9.4 Door d2 centered on wall w10 (span: [${d2SpanStart.toFixed(2)}, ${d2SpanEnd.toFixed(2)}]m on 0.70m wall)`);

  // 9.5 Door d4 clearance on w14
  const cd4 = cleanedScene.doors.find(d => d.id === 'd4');
  const d4SpanEnd = cd4.offset + cd4.width / 2;
  assert(cd4.wall_id === 'w14' && d4SpanEnd <= 2.65,
    `9.5 Door d4 repositioned on wall w14 with 10cm corner casing clearance (end offset: ${d4SpanEnd.toFixed(2)}m on 2.74m wall)`);

  // 9.6 Window win1 clearance and pier separation on w3
  const cwin1 = cleanedScene.windows.find(w => w.id === 'win1');
  const cwin2 = cleanedScene.windows.find(w => w.id === 'win2');
  const win1SpanStart = cwin1.offset - cwin1.width / 2;
  const win1SpanEnd = cwin1.offset + cwin1.width / 2;
  const win2SpanEnd = cwin2.offset + cwin2.width / 2;
  const pierSeparation = win1SpanStart - win2SpanEnd;
  assert(cwin1.wall_id === 'w3' && win1SpanEnd <= 1.09 && pierSeparation >= 0.25,
    `9.6 Window win1 fits on w3 with 10cm end clearance and ${(pierSeparation * 100).toFixed(0)}cm solid pier separation from win2`);

  // 9.7 Window win2 start clearance
  const win2SpanStart = cwin2.offset - cwin2.width / 2;
  assert(cwin2.wall_id === 'w3' && win2SpanStart >= 0.09,
    `9.7 Window win2 fits on w3 with ${(win2SpanStart * 100).toFixed(0)}cm start corner clearance`);

  // 9.8 Summary issue counts
  const repSummary = cleanedVal.validationReport.summary;
  assert(repSummary.total_initial_issues === 17 && repSummary.auto_repaired === 15 && repSummary.remaining_unresolved === 2,
    `9.8 Diagnostic summary confirms: ${repSummary.total_initial_issues} initial, ${repSummary.auto_repaired} repaired, ${repSummary.remaining_unresolved} unresolved`);

  // 9.9 Idempotency of repair operations
  const secondRepair = TopologyRepairer.repair(cleanedScene);
  assert(secondRepair.operations.length === 0,
    `9.9 TopologyRepairer is strictly idempotent: 2nd pass generated 0 new operations (was: ${secondRepair.operations.length})`);

  // -------------------------------------------------------------------------
  // SUITE 10: FORENSIC VERIFICATION & RETENTION OF WALL W9 (PHASES 1-5)
  // -------------------------------------------------------------------------
  console.log('\n--- SUITE 10: WALL W9 FORENSIC CLASSIFICATION & INTEGRITY ---');

  // 10.1 Wall w9 semantic classification and status
  assert(w9.classification === 'candidate_annotation_or_transverse_stub',
    `10.1 Wall w9 has semantic classification '${w9.classification}'`);
  assert(w9.status === 'retained_pending_manual_review',
    `10.2 Wall w9 has provenance status '${w9.status}'`);

  // 10.3 Dimensional fidelity: length is exactly 0.24m and not extended to 0.30m
  assert(Math.abs(w9.length - 0.24) < 0.001 && w9.length < 0.30,
    `10.3 Wall w9 length is strictly 0.24m (was not extended to 0.30m threshold)`);
  assert(w9.start[0] === 1.44 && w9.start[1] === 3.0 && w9.end[0] === 1.68 && w9.end[1] === 3.0,
    `10.4 Wall w9 spans exactly [1.44, 3.0] to [1.68, 3.0] across West exterior envelope`);

  // 10.5 Connectivity gap: 0.80m to w11 and 1.54m to w2
  const w11 = cleanedScene.walls.find(w => w.id === 'w11');
  const w2 = cleanedScene.walls.find(w => w.id === 'w2');
  const gapToW11 = Math.abs(w11.start[1] - w9.start[1]); // 3.80 - 3.00 = 0.80m
  const gapToW2 = Math.abs(w9.start[1] - w2.end[1]);     // 3.00 - 1.46 = 1.54m
  assert(Math.abs(gapToW11 - 0.80) < 0.01,
    `10.5 Gap from w9 to nearest wall w11 is exactly ${gapToW11.toFixed(2)}m (exceeds 0.15m tolerance)`);
  assert(Math.abs(gapToW2 - 1.54) < 0.01,
    `10.6 Gap from w9 to upper wall w2 is exactly ${gapToW2.toFixed(2)}m`);

  // 10.7 Prevention of unjustified wall connections
  const snappedDist = Math.hypot(w9.end[0] - w11.start[0], w9.end[1] - w11.start[1]);
  assert(snappedDist > 0.70,
    `10.7 w9 is not arbitrarily snapped to w11 across open space (distance: ${snappedDist.toFixed(2)}m)`);

  // 10.8 Validator sub_type distinctions and actionable diagnostic guidance
  const shortIssue = report.issues.find(i => i.element_id === 'w9' && i.type === 'short_wall');
  const discoIssue = report.issues.find(i => i.element_id === 'w9' && i.type === 'disconnected_wall');
  assert(shortIssue && shortIssue.sub_type === 'indeterminate_transverse_segment' && !!shortIssue.additional_evidence_needed,
    '10.8 Short wall issue carries sub_type indeterminate_transverse_segment and notes additional evidence needed');
  assert(discoIssue && discoIssue.sub_type === 'indeterminate_network_gap' && !!discoIssue.additional_evidence_needed,
    '10.9 Disconnected wall issue carries sub_type indeterminate_network_gap and notes additional evidence needed');

  // 10.10 Idempotency: 3rd pass produces zero changes
  const thirdRepair = TopologyRepairer.repair(secondRepair.repairedScene);
  assert(thirdRepair.operations.length === 0,
    `10.10 Multi-pass idempotency confirmed: 3rd repair pass generated 0 operations`);

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
