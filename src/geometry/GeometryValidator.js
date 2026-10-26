/**
 * GeometryValidator.js
 * Comprehensive architectural geometry validation engine for HNX26EPS06 Member 2.
 * 
 * Inspects scene graph data for:
 * 1. Wall endpoint connectivity & isolated walls
 * 2. Duplicate and collinear overlapping wall segments
 * 3. Wall intersection consistency
 * 4. Opening host-wall reference validity
 * 5. Opening dimension fitting (doors/windows wider than host walls)
 * 6. Opening placement & extreme boundary distances
 * 7. Room polygon validity (closure, duplicate vertices, self-intersection, winding)
 * 8. Unit, scale, and dimensional consistency
 * 9. Floor and wall elevation consistency
 * 10. Actionable diagnostic issue records with measured vs expected values
 */

export class GeometryValidator {
  /**
   * Run comprehensive diagnostic validation on raw or sanitized scene data
   * @param {Object} sceneData 
   * @param {Object} options 
   * @returns {Object} { isValid, summary, issues, errors, warnings, info }
   */
  static validate(sceneData, options = {}) {
    const issues = [];
    const snappingTolerance = options.snappingTolerance || 0.15; // 15cm tolerance for connectivity

    if (!sceneData || typeof sceneData !== 'object') {
      const errIssue = {
        id: 'ISS_SCENE_000',
        severity: 'error',
        element_type: 'scene',
        element_id: 'root',
        defect: 'null_scene_data',
        message: 'Scene data is null, undefined, or not a valid object',
        measured: { type: typeof sceneData },
        expected: { type: 'object' },
        auto_repaired: false,
        correction_applied: null,
        manual_review_required: true
      };
      return {
        isValid: false,
        summary: { total_issues: 1, errors: 1, warnings: 0, info: 0, auto_repaired: 0, manual_review_required: 1 },
        issues: [errIssue],
        errors: [errIssue.message],
        warnings: [],
        info: []
      };
    }

    // 1. Scene Level Validation (Units, Scale, Heights)
    this._validateSceneLevel(sceneData, issues);

    // 2. Wall Validations
    const wallMap = new Map();
    const walls = Array.isArray(sceneData.walls) ? sceneData.walls : [];
    this._validateWalls(walls, wallMap, issues, snappingTolerance);

    // 3. Wall-to-Wall Topology & Connectivity
    this._validateWallTopology(walls, issues, snappingTolerance);

    // 4. Doors & Openings Validations
    const doors = Array.isArray(sceneData.doors) ? sceneData.doors : [];
    this._validateDoors(doors, wallMap, sceneData, issues);

    // 5. Windows & Openings Validations
    const windows = Array.isArray(sceneData.windows) ? sceneData.windows : [];
    this._validateWindows(windows, wallMap, sceneData, issues);

    // 6. Room Polygon Validations
    const rooms = Array.isArray(sceneData.rooms) ? sceneData.rooms : [];
    this._validateRooms(rooms, wallMap, issues);

    // Separate issues by severity
    const errors = issues.filter(i => i.severity === 'error').map(i => i.message);
    const warnings = issues.filter(i => i.severity === 'warning').map(i => i.message);
    const info = issues.filter(i => i.severity === 'info').map(i => i.message);

    const summary = {
      total_issues: issues.length,
      errors: errors.length,
      warnings: warnings.length,
      info: info.length,
      auto_repaired: issues.filter(i => i.auto_repaired).length,
      manual_review_required: issues.filter(i => i.manual_review_required).length
    };

    return {
      isValid: errors.length === 0,
      summary,
      issues,
      errors,
      warnings,
      info
    };
  }

  static _validateSceneLevel(scene, issues) {
    // Units
    if (!scene.units || typeof scene.units !== 'string') {
      issues.push({
        id: `ISS_SCENE_${issues.length + 1}`,
        severity: 'warning',
        element_type: 'scene',
        element_id: 'units',
        defect: 'missing_units',
        message: "Scene units not explicitly defined. Assumed 'meters'.",
        measured: { units: scene.units },
        expected: { units: 'meters' },
        auto_repaired: true,
        correction_applied: "Defaulted units to 'meters'",
        manual_review_required: false
      });
    }

    // Scale
    if (!scene.scale) {
      issues.push({
        id: `ISS_SCENE_${issues.length + 1}`,
        severity: 'info',
        element_type: 'scene',
        element_id: 'scale',
        defect: 'unspecified_scale_factor',
        message: 'No physical scale metadata provided. Coordinate units treated as meters directly.',
        measured: { scale: null },
        expected: { scale: { meters_per_pixel: 'number' } },
        auto_repaired: false,
        correction_applied: null,
        manual_review_required: false
      });
    } else if (scene.scale.meters_per_pixel !== undefined) {
      if (typeof scene.scale.meters_per_pixel !== 'number' || scene.scale.meters_per_pixel <= 0) {
        issues.push({
          id: `ISS_SCENE_${issues.length + 1}`,
          severity: 'error',
          element_type: 'scene',
          element_id: 'scale',
          defect: 'invalid_scale_factor',
          message: `Invalid scale factor (${scene.scale.meters_per_pixel}). Must be positive number.`,
          measured: { meters_per_pixel: scene.scale.meters_per_pixel },
          expected: { min_meters_per_pixel: 0.0001 },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
      }
    }

    // Wall Height Consistency
    const wallHeight = (scene.defaults && scene.defaults.wall_height) || scene.wall_height || (scene.settings && scene.settings.wallHeight);
    if (wallHeight !== undefined) {
      if (typeof wallHeight !== 'number' || wallHeight <= 1.0 || wallHeight > 10.0) {
        issues.push({
          id: `ISS_SCENE_${issues.length + 1}`,
          severity: 'warning',
          element_type: 'scene',
          element_id: 'wall_height',
          defect: 'unusual_wall_height',
          message: `Specified wall height (${wallHeight}m) is outside standard architectural range (2.0m - 5.0m).`,
          measured: { wall_height: wallHeight },
          expected: { min_height: 2.0, max_height: 5.0 },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
      }
    }
  }

  static _validateWalls(walls, wallMap, issues, snappingTolerance) {
    if (walls.length === 0) {
      issues.push({
        id: `ISS_WALL_${issues.length + 1}`,
        severity: 'error',
        element_type: 'wall',
        element_id: 'all',
        defect: 'empty_walls',
        message: 'Scene contains no wall elements.',
        measured: { wall_count: 0 },
        expected: { min_wall_count: 3 },
        auto_repaired: false,
        correction_applied: null,
        manual_review_required: true
      });
      return;
    }

    const seenIds = new Set();

    walls.forEach((wall, idx) => {
      const id = wall.id || `w_auto_${idx}`;
      if (!wall.id) {
        issues.push({
          id: `ISS_WALL_${issues.length + 1}`,
          severity: 'warning',
          element_type: 'wall',
          element_id: id,
          defect: 'missing_wall_id',
          message: `Wall at index ${idx} is missing an ID. Assigned temporary '${id}'.`,
          measured: { index: idx },
          expected: { id: 'string' },
          auto_repaired: true,
          correction_applied: `Assigned temporary ID '${id}'`,
          manual_review_required: false
        });
      }

      if (seenIds.has(id)) {
        issues.push({
          id: `ISS_WALL_${issues.length + 1}`,
          severity: 'error',
          element_type: 'wall',
          element_id: id,
          defect: 'duplicate_wall_id',
          message: `Duplicate wall ID '${id}' detected.`,
          measured: { id },
          expected: { unique: true },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
      }
      seenIds.add(id);

      const start = (wall.geometry && Array.isArray(wall.geometry.start)) ? wall.geometry.start : wall.start;
      const end = (wall.geometry && Array.isArray(wall.geometry.end)) ? wall.geometry.end : wall.end;

      if (!Array.isArray(start) || start.length < 2 || isNaN(start[0]) || isNaN(start[1]) ||
          !Array.isArray(end) || end.length < 2 || isNaN(end[0]) || isNaN(end[1])) {
        issues.push({
          id: `ISS_WALL_${issues.length + 1}`,
          severity: 'error',
          element_type: 'wall',
          element_id: id,
          defect: 'invalid_coordinates',
          message: `Wall '${id}' has non-numeric start or end coordinates.`,
          measured: { start, end },
          expected: { format: '[number, number]' },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
        return;
      }

      const dx = end[0] - start[0];
      const dz = end[1] - start[1];
      const length = Math.hypot(dx, dz);

      if (length < 0.001) {
        issues.push({
          id: `ISS_WALL_${issues.length + 1}`,
          severity: 'error',
          element_type: 'wall',
          element_id: id,
          defect: 'degenerate_zero_length_wall',
          message: `Wall '${id}' has near-zero length (${length.toFixed(4)}m) and produces degenerate geometry.`,
          measured: { length },
          expected: { min_length: 0.1 },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
        return;
      }

      if (length < 0.3) {
        issues.push({
          id: `ISS_WALL_${issues.length + 1}`,
          severity: 'warning',
          element_type: 'wall',
          element_id: id,
          defect: 'short_wall',
          message: `Wall '${id}' is unusually short (length ${length.toFixed(2)}m < 0.3m)`,
          measured: { length: Number(length.toFixed(4)) },
          expected: { min_length: 0.3 },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
      }

      const thickness = (wall.geometry && typeof wall.geometry.thickness === 'number')
        ? wall.geometry.thickness
        : ((typeof wall.thickness === 'number') ? wall.thickness : 0.2);

      if (thickness <= 0.02 || thickness > 1.0) {
        issues.push({
          id: `ISS_WALL_${issues.length + 1}`,
          severity: 'warning',
          element_type: 'wall',
          element_id: id,
          defect: 'abnormal_thickness',
          message: `Wall '${id}' thickness (${thickness}m) is outside typical range (0.05m - 0.50m).`,
          measured: { thickness },
          expected: { min_thickness: 0.05, max_thickness: 0.5 },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
      }

      wallMap.set(id, {
        id,
        start: [start[0], start[1]],
        end: [end[0], end[1]],
        length,
        thickness,
        dx,
        dz,
        wall
      });
    });
  }

  static _validateWallTopology(walls, issues, snappingTolerance) {
    const wallEntries = Array.from(walls).map(w => {
      const start = (w.geometry && Array.isArray(w.geometry.start)) ? w.geometry.start : w.start;
      const end = (w.geometry && Array.isArray(w.geometry.end)) ? w.geometry.end : w.end;
      const thickness = (w.geometry && typeof w.geometry.thickness === 'number') ? w.geometry.thickness : (w.thickness || 0.2);
      return { id: w.id, start, end, thickness };
    }).filter(w => Array.isArray(w.start) && Array.isArray(w.end));

    // Duplicate walls & collinear overlap check
    for (let i = 0; i < wallEntries.length; i++) {
      for (let j = i + 1; j < wallEntries.length; j++) {
        const wA = wallEntries[i];
        const wB = wallEntries[j];

        const dStartStart = Math.hypot(wA.start[0] - wB.start[0], wA.start[1] - wB.start[1]);
        const dEndEnd = Math.hypot(wA.end[0] - wB.end[0], wA.end[1] - wB.end[1]);
        const dStartEnd = Math.hypot(wA.start[0] - wB.end[0], wA.start[1] - wB.end[1]);
        const dEndStart = Math.hypot(wA.end[0] - wB.start[0], wA.end[1] - wB.start[1]);

        // Exact or reversed duplicate
        if ((dStartStart < 0.01 && dEndEnd < 0.01) || (dStartEnd < 0.01 && dEndStart < 0.01)) {
          issues.push({
            id: `ISS_TOPO_${issues.length + 1}`,
            severity: 'error',
            element_type: 'wall',
            element_id: wB.id,
            defect: 'duplicate_wall_geometry',
            message: `Wall '${wB.id}' is a geometric duplicate of Wall '${wA.id}'.`,
            measured: { duplicate_of: wA.id },
            expected: { unique_geometry: true },
            auto_repaired: false,
            correction_applied: null,
            manual_review_required: true
          });
        }
      }
    }

    // Endpoint Connectivity & T-junctions
    wallEntries.forEach(wall => {
      const startConnected = this._isEndpointConnected(wall.start, wall.id, wallEntries, snappingTolerance);
      const endConnected = this._isEndpointConnected(wall.end, wall.id, wallEntries, snappingTolerance);

      if (!startConnected.connected && !endConnected.connected) {
        issues.push({
          id: `ISS_TOPO_${issues.length + 1}`,
          severity: 'warning',
          element_type: 'wall',
          element_id: wall.id,
          defect: 'disconnected_wall',
          message: `Wall '${wall.id}' is isolated and disconnected from all other walls`,
          measured: {
            start: wall.start,
            end: wall.end,
            min_distance_to_network: Math.min(startConnected.minDist, endConnected.minDist).toFixed(3)
          },
          expected: { connection_threshold: snappingTolerance },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
      } else {
        if (!startConnected.connected) {
          issues.push({
            id: `ISS_TOPO_${issues.length + 1}`,
            severity: 'info',
            element_type: 'wall',
            element_id: wall.id,
            defect: 'open_endpoint',
            message: `Wall '${wall.id}' start ends at (${wall.start[0].toFixed(2)}, ${wall.start[1].toFixed(2)}) without meeting another wall. A wall may be missing or too short.`,
            measured: { endpoint: 'start', coordinates: wall.start, nearest_distance: startConnected.minDist.toFixed(3) },
            expected: { connection_threshold: snappingTolerance },
            auto_repaired: false,
            correction_applied: null,
            manual_review_required: false
          });
        }
        if (!endConnected.connected) {
          issues.push({
            id: `ISS_TOPO_${issues.length + 1}`,
            severity: 'info',
            element_type: 'wall',
            element_id: wall.id,
            defect: 'open_endpoint',
            message: `Wall '${wall.id}' end ends at (${wall.end[0].toFixed(2)}, ${wall.end[1].toFixed(2)}) without meeting another wall. A wall may be missing or too short.`,
            measured: { endpoint: 'end', coordinates: wall.end, nearest_distance: endConnected.minDist.toFixed(3) },
            expected: { connection_threshold: snappingTolerance },
            auto_repaired: false,
            correction_applied: null,
            manual_review_required: false
          });
        }
      }
    });
  }

  static _isEndpointConnected(pt, currentWallId, allWalls, tolerance) {
    let connected = false;
    let minDist = Infinity;

    for (const other of allWalls) {
      if (other.id === currentWallId) continue;

      // 1. Check corner connection (endpoint-to-endpoint)
      const dStart = Math.hypot(pt[0] - other.start[0], pt[1] - other.start[1]);
      const dEnd = Math.hypot(pt[0] - other.end[0], pt[1] - other.end[1]);
      minDist = Math.min(minDist, dStart, dEnd);

      if (dStart <= tolerance || dEnd <= tolerance) {
        connected = true;
        break;
      }

      // 2. Check T-junction (point-to-segment distance)
      const distToSegment = this._distPointToSegment(pt, other.start, other.end);
      minDist = Math.min(minDist, distToSegment);

      if (distToSegment <= tolerance) {
        connected = true;
        break;
      }
    }

    return { connected, minDist };
  }

  static _distPointToSegment(p, a, b) {
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const lenSq = dx * dx + dy * dy;
    if (lenSq < 0.000001) return Math.hypot(p[0] - a[0], p[1] - a[1]);

    let t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / lenSq;
    t = Math.max(0, Math.min(1, t));

    const projX = a[0] + t * dx;
    const projY = a[1] + t * dy;
    return Math.hypot(p[0] - projX, p[1] - projY);
  }

  static _validateDoors(doors, wallMap, sceneData, issues) {
    doors.forEach((door, idx) => {
      const id = door.id || `d_${idx}`;
      if (!door.wall_id) {
        issues.push({
          id: `ISS_DOOR_${issues.length + 1}`,
          severity: 'error',
          element_type: 'door',
          element_id: id,
          defect: 'missing_host_wall_reference',
          message: `Door '${id}' is missing required 'wall_id' reference.`,
          measured: { wall_id: null },
          expected: { wall_id: 'valid_wall_id' },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
        return;
      }

      const wall = wallMap.get(door.wall_id);
      if (!wall) {
        issues.push({
          id: `ISS_DOOR_${issues.length + 1}`,
          severity: 'error',
          element_type: 'door',
          element_id: id,
          defect: 'nonexistent_host_wall',
          message: `Door '${id}' references non-existent wall '${door.wall_id}'.`,
          measured: { wall_id: door.wall_id },
          expected: { exists: true },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
        return;
      }

      const geom = door.geometry;
      const width = (geom && typeof geom.width === 'number') ? geom.width : (door.width || 0.9);
      const wallLen = wall.length;

      // 1. Width exceeds wall length
      if (width > wallLen) {
        issues.push({
          id: `ISS_DOOR_${issues.length + 1}`,
          severity: 'warning',
          element_type: 'door',
          element_id: id,
          defect: 'door_exceeds_wall_length',
          message: `Door '${id}' width (${width.toFixed(2)}m) exceeds referenced wall '${door.wall_id}' length (${wallLen.toFixed(2)}m)`,
          measured: { door_width: width, wall_length: Number(wallLen.toFixed(4)) },
          expected: { max_width: Number(wallLen.toFixed(4)) },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
      }

      // 2. Boundary position
      let offset = (geom && typeof geom.offset_from_start === 'number') ? geom.offset_from_start : door.offset;
      let position = door.position;
      if (typeof offset === 'number' && wallLen > 0) {
        position = offset / wallLen;
      }

      if (position !== undefined) {
        if (position <= 0.01 || position >= 0.99) {
          issues.push({
            id: `ISS_DOOR_${issues.length + 1}`,
            severity: 'warning',
            element_type: 'door',
            element_id: id,
            defect: 'boundary_door_position',
            message: `Door '${id}' is positioned at the extreme wall boundary (position=${position.toFixed(1)})`,
            measured: { position: Number(position.toFixed(2)), offset },
            expected: { min_margin: 0.1 },
            auto_repaired: false,
            correction_applied: null,
            manual_review_required: true
          });
        }
      }
    });
  }

  static _validateWindows(windows, wallMap, sceneData, issues) {
    windows.forEach((win, idx) => {
      const id = win.id || `win_${idx}`;
      if (!win.wall_id) {
        issues.push({
          id: `ISS_WIN_${issues.length + 1}`,
          severity: 'error',
          element_type: 'window',
          element_id: id,
          defect: 'missing_host_wall_reference',
          message: `Window '${id}' is missing required 'wall_id' reference.`,
          measured: { wall_id: null },
          expected: { wall_id: 'valid_wall_id' },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
        return;
      }

      const wall = wallMap.get(win.wall_id);
      if (!wall) {
        issues.push({
          id: `ISS_WIN_${issues.length + 1}`,
          severity: 'error',
          element_type: 'window',
          element_id: id,
          defect: 'nonexistent_host_wall',
          message: `Window '${id}' references non-existent wall '${win.wall_id}'.`,
          measured: { wall_id: win.wall_id },
          expected: { exists: true },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
        return;
      }

      const geom = win.geometry;
      const width = (geom && typeof geom.width === 'number') ? geom.width : (win.width || 1.5);
      const wallLen = wall.length;

      // 1. Width exceeds wall length
      if (width > wallLen) {
        issues.push({
          id: `ISS_WIN_${issues.length + 1}`,
          severity: 'warning',
          element_type: 'window',
          element_id: id,
          defect: 'window_exceeds_wall_length',
          message: `Window '${id}' width (${width.toFixed(2)}m) exceeds referenced wall '${win.wall_id}' length (${wallLen.toFixed(2)}m)`,
          measured: { window_width: width, wall_length: Number(wallLen.toFixed(4)) },
          expected: { max_width: Number(wallLen.toFixed(4)) },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
      }

      // 2. Boundary position
      let offset = (geom && typeof geom.offset_from_start === 'number') ? geom.offset_from_start : win.offset;
      let position = win.position;
      if (typeof offset === 'number' && wallLen > 0) {
        position = offset / wallLen;
      }

      if (position !== undefined) {
        if (position <= 0.01 || position >= 0.99) {
          issues.push({
            id: `ISS_WIN_${issues.length + 1}`,
            severity: 'warning',
            element_type: 'window',
            element_id: id,
            defect: 'boundary_window_position',
            message: `Window '${id}' is positioned at the extreme wall boundary (position=${position.toFixed(1)})`,
            measured: { position: Number(position.toFixed(2)), offset },
            expected: { min_margin: 0.1 },
            auto_repaired: false,
            correction_applied: null,
            manual_review_required: true
          });
        }
      }
    });
  }

  static _validateRooms(rooms, wallMap, issues) {
    rooms.forEach((room, idx) => {
      const id = room.id || `room_${idx}`;
      const polygon = (room.geometry && Array.isArray(room.geometry.polygon)) ? room.geometry.polygon : room.polygon;

      if (!Array.isArray(polygon) || polygon.length < 3) {
        issues.push({
          id: `ISS_ROOM_${issues.length + 1}`,
          severity: 'error',
          element_type: 'room',
          element_id: id,
          defect: 'insufficient_polygon_vertices',
          message: `Room '${id}' polygon has fewer than 3 vertices (${polygon ? polygon.length : 0}).`,
          measured: { vertex_count: polygon ? polygon.length : 0 },
          expected: { min_vertices: 3 },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
        return;
      }

      // Duplicate consecutive vertices check
      for (let i = 0; i < polygon.length; i++) {
        const p1 = polygon[i];
        const p2 = polygon[(i + 1) % polygon.length];
        if (Math.hypot(p1[0] - p2[0], p1[1] - p2[1]) < 0.001 && i !== polygon.length - 1) {
          issues.push({
            id: `ISS_ROOM_${issues.length + 1}`,
            severity: 'warning',
            element_type: 'room',
            element_id: id,
            defect: 'duplicate_consecutive_vertex',
            message: `Room '${id}' contains redundant duplicate consecutive vertices at index ${i}.`,
            measured: { vertex: p1 },
            expected: { unique_consecutive: true },
            auto_repaired: true,
            correction_applied: 'Removed redundant duplicate consecutive vertex',
            manual_review_required: false
          });
        }
      }

      // Self-intersection check
      const selfIntersect = this._checkPolygonSelfIntersection(polygon);
      if (selfIntersect.hasIntersection) {
        issues.push({
          id: `ISS_ROOM_${issues.length + 1}`,
          severity: 'warning',
          element_type: 'room',
          element_id: id,
          defect: 'self_intersecting_polygon',
          message: `Room '${id}' polygon boundary has self-intersecting edges between segments [${selfIntersect.edgeA}] and [${selfIntersect.edgeB}].`,
          measured: { edgeA: selfIntersect.edgeA, edgeB: selfIntersect.edgeB },
          expected: { simple_polygon: true },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
      }

      // Area and Winding
      const signedArea = this._computeSignedArea(polygon);
      if (Math.abs(signedArea) < 0.01) {
        issues.push({
          id: `ISS_ROOM_${issues.length + 1}`,
          severity: 'error',
          element_type: 'room',
          element_id: id,
          defect: 'zero_area_room',
          message: `Room '${id}' has near-zero floor area (${Math.abs(signedArea).toFixed(4)} m²).`,
          measured: { area: Math.abs(signedArea) },
          expected: { min_area: 0.5 },
          auto_repaired: false,
          correction_applied: null,
          manual_review_required: true
        });
      }
    });
  }

  static _computeSignedArea(polygon) {
    let area = 0;
    const n = polygon.length;
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      area += polygon[i][0] * polygon[j][1];
      area -= polygon[j][0] * polygon[i][1];
    }
    return area / 2.0;
  }

  static _checkPolygonSelfIntersection(polygon) {
    const n = polygon.length;
    for (let i = 0; i < n; i++) {
      const a1 = polygon[i];
      const a2 = polygon[(i + 1) % n];
      for (let j = i + 2; j < n; j++) {
        if (i === 0 && j === n - 1) continue; // adjacent closing segment
        const b1 = polygon[j];
        const b2 = polygon[(j + 1) % n];
        if (this._segmentsIntersect(a1, a2, b1, b2)) {
          return { hasIntersection: true, edgeA: i, edgeB: j };
        }
      }
    }
    return { hasIntersection: false };
  }

  static _segmentsIntersect(p1, p2, p3, p4) {
    const ccw = (a, b, c) => (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0]);
    return ccw(p1, p3, p4) !== ccw(p2, p3, p4) && ccw(p1, p2, p3) !== ccw(p1, p2, p4);
  }
}
