export class SceneValidator {
  /**
   * Validates and sanitizes scene.json data gracefully.
   * Accepts:
   * 1. Real Member 2 validated scene output with processed metric geometry (validated_scene.json)
   * 2. Synthetic blueprint Member 2 output (sample_scene.json)
   * 3. Legacy synthetic test scene (scene.json)
   * @param {Object} rawData - Incoming scene JSON
   * @returns {Object} { isValid, scene, errors, warnings }
   */
  static validate(rawData) {
    const errors = [];
    const warnings = [];

    if (!rawData || typeof rawData !== 'object') {
      return {
        isValid: false,
        scene: null,
        errors: ['Scene data is null, undefined, or not a valid JSON object.'],
        warnings: []
      };
    }

    // Preserve Member 2 validation issues if present
    if (rawData.validation && Array.isArray(rawData.validation.issues)) {
      rawData.validation.issues.forEach(issue => {
        warnings.push(`[Member 2 ${issue.severity || 'warning'}: ${issue.type}] ${issue.message}`);
      });
    }

    const units = typeof rawData.units === 'string' ? rawData.units : 'meters';
    if (rawData.units && typeof rawData.units !== 'string') {
      warnings.push(`Invalid units format '${rawData.units}'. Defaulted to 'meters'.`);
    }

    // Coordinate system ("world" or object with up_axis: "Z")
    let coordinate_system = 'world';
    if (typeof rawData.coordinate_system === 'string') {
      coordinate_system = rawData.coordinate_system;
    } else if (rawData.coordinate_system && typeof rawData.coordinate_system === 'object') {
      coordinate_system = {
        up_axis: rawData.coordinate_system.up_axis || 'Z',
        horizontal_axes: Array.isArray(rawData.coordinate_system.horizontal_axes)
          ? [...rawData.coordinate_system.horizontal_axes]
          : ['X', 'Y']
      };
    }

    // Defaults and Heights: Priority order: defaults.wall_height -> wall_height -> settings.wallHeight -> 3.0
    let wallHeight = 3.0;
    if (rawData.defaults && typeof rawData.defaults.wall_height === 'number' && rawData.defaults.wall_height > 0) {
      wallHeight = rawData.defaults.wall_height;
    } else if (typeof rawData.wall_height === 'number' && rawData.wall_height > 0) {
      wallHeight = rawData.wall_height;
    } else if (rawData.settings && typeof rawData.settings.wallHeight === 'number' && rawData.settings.wallHeight > 0) {
      wallHeight = rawData.settings.wallHeight;
    } else if (rawData.wall_height !== undefined || (rawData.defaults && rawData.defaults.wall_height !== undefined)) {
      warnings.push(`Invalid wall height. Fallback to 3.0m.`);
    }

    const doorHeightDefault = (rawData.defaults && typeof rawData.defaults.door_height === 'number')
      ? rawData.defaults.door_height
      : 2.1;
    const windowHeightDefault = (rawData.defaults && typeof rawData.defaults.window_height === 'number')
      ? rawData.defaults.window_height
      : 1.2;
    const windowSillHeightDefault = (rawData.defaults && typeof rawData.defaults.window_sill_height === 'number')
      ? rawData.defaults.window_sill_height
      : 0.9;

    // Floor Thickness
    let floorThickness = 0.1;
    if (rawData.settings && typeof rawData.settings.floorThickness === 'number' && rawData.settings.floorThickness > 0) {
      floorThickness = rawData.settings.floorThickness;
    }

    const settings = {
      wallHeight,
      doorHeight: doorHeightDefault,
      windowHeight: windowHeightDefault,
      windowSillHeight: windowSillHeightDefault,
      floorThickness
    };

    const defaults = {
      wall_height: wallHeight,
      door_height: doorHeightDefault,
      window_height: windowHeightDefault,
      window_sill_height: windowSillHeightDefault
    };

    // Walls
    const validWalls = [];
    const wallIds = new Set();
    const wallMapData = new Map();

    if (!Array.isArray(rawData.walls) || rawData.walls.length === 0) {
      warnings.push('Scene contains no walls.');
    } else {
      rawData.walls.forEach((wall, idx) => {
        const id = wall.id || `w_auto_${idx}`;
        if (!wall.id) {
          warnings.push(`Wall at index ${idx} is missing an ID. Assigned temporary '${id}'.`);
        }

        if (wallIds.has(id)) {
          warnings.push(`Duplicate wall ID '${id}'.`);
        }

        // Prefer processed metric geometry.start and geometry.end over source coordinates
        const start = (wall.geometry && Array.isArray(wall.geometry.start)) ? wall.geometry.start : wall.start;
        const end = (wall.geometry && Array.isArray(wall.geometry.end)) ? wall.geometry.end : wall.end;

        if (!Array.isArray(start) || start.length < 2 || 
            typeof start[0] !== 'number' || typeof start[1] !== 'number' ||
            isNaN(start[0]) || isNaN(start[1])) {
          errors.push(`Wall '${id}' has invalid start coordinates.`);
          return;
        }

        if (!Array.isArray(end) || end.length < 2 || 
            typeof end[0] !== 'number' || typeof end[1] !== 'number' ||
            isNaN(end[0]) || isNaN(end[1])) {
          errors.push(`Wall '${id}' has invalid end coordinates.`);
          return;
        }

        const dx = end[0] - start[0];
        const dz = end[1] - start[1];
        const calculatedLength = Math.sqrt(dx * dx + dz * dz);

        if (calculatedLength < 0.001) {
          warnings.push(`Wall '${id}' has zero length (${calculatedLength}m) and will be skipped.`);
          return;
        }

        let thickness = (wall.geometry && typeof wall.geometry.thickness === 'number')
          ? wall.geometry.thickness
          : wall.thickness;
        if (typeof thickness !== 'number' || isNaN(thickness) || thickness <= 0) {
          thickness = 0.2;
          warnings.push(`Wall '${id}' has invalid thickness. Defaulted to 0.2m.`);
        }

        const suppliedLength = (wall.geometry && typeof wall.geometry.length === 'number')
          ? wall.geometry.length
          : null;

        if (suppliedLength !== null && Math.abs(calculatedLength - suppliedLength) > 0.02) {
          warnings.push(`Wall '${id}' calculated length (${calculatedLength.toFixed(4)}m) differs from supplied length (${suppliedLength.toFixed(4)}m).`);
        }

        const wallRecord = {
          id,
          start: [start[0], start[1]],
          end: [end[0], end[1]],
          thickness,
          length: calculatedLength,
          supplied_length: suppliedLength,
          geometry: wall.geometry || null,
          source: wall.source || null
        };

        validWalls.push(wallRecord);
        wallIds.add(id);
        wallMapData.set(id, wallRecord);
      });
    }

    // Doors
    const validDoors = [];
    if (Array.isArray(rawData.doors)) {
      rawData.doors.forEach((door, idx) => {
        const id = door.id || `d_auto_${idx}`;
        if (!door.wall_id) {
          warnings.push(`Door '${id}' is missing wall_id and will be skipped.`);
          return;
        }

        if (!wallMapData.has(door.wall_id)) {
          warnings.push(`Door '${id}' references missing wall '${door.wall_id}'.`);
          return;
        }

        const parentWall = wallMapData.get(door.wall_id);
        const wallLen = parentWall.length;
        const geom = door.geometry;

        // Authoritative processed center if available
        let center = null;
        if (geom && Array.isArray(geom.center) && geom.center.length >= 2 &&
            typeof geom.center[0] === 'number' && typeof geom.center[1] === 'number') {
          center = [geom.center[0], geom.center[1]];
        }

        // Authoritative metric offset
        let offset = (geom && typeof geom.offset_from_start === 'number')
          ? geom.offset_from_start
          : door.offset;
        let position = door.position;

        if (typeof offset === 'number' && !isNaN(offset)) {
          if (offset < 0) {
            warnings.push(`Door '${id}' has negative offset (${offset}m).`);
          } else if (offset > wallLen) {
            warnings.push(`Door '${id}' offset (${offset}m) exceeds wall length (${wallLen.toFixed(2)}m).`);
          }
          position = wallLen > 0 ? offset / wallLen : 0.5;
        } else if (typeof position === 'number' && !isNaN(position)) {
          if (position < 0 || position > 1) {
            warnings.push(`Door '${id}' position outside [0, 1]. Clamped to 0.5.`);
            position = Math.max(0, Math.min(1, position));
          }
          offset = position * wallLen;
        } else if (!center) {
          position = 0.5;
          offset = 0.5 * wallLen;
          warnings.push(`Door '${id}' has missing or invalid offset/position. Defaulted to midpoint.`);
        }

        let width = (geom && typeof geom.width === 'number') ? geom.width : door.width;
        if (typeof width !== 'number' || isNaN(width) || width <= 0) {
          width = 0.9;
          warnings.push(`Door '${id}' has non-positive width. Defaulted to 0.9m.`);
        } else if (width > wallLen) {
          warnings.push(`Door '${id}' width (${width}m) exceeds wall '${door.wall_id}' length (${wallLen.toFixed(2)}m).`);
        }

        let height = (geom && typeof geom.height === 'number')
          ? geom.height
          : ((typeof door.height === 'number' && door.height > 0) ? door.height : doorHeightDefault);

        validDoors.push({
          id,
          wall_id: door.wall_id,
          center,
          offset,
          position,
          width,
          height,
          geometry: geom || null
        });
      });
    }

    // Windows
    const validWindows = [];
    if (Array.isArray(rawData.windows)) {
      rawData.windows.forEach((win, idx) => {
        const id = win.id || `win_auto_${idx}`;
        if (!win.wall_id) {
          warnings.push(`Window '${id}' is missing wall_id and will be skipped.`);
          return;
        }

        if (!wallMapData.has(win.wall_id)) {
          warnings.push(`Window '${id}' references missing wall '${win.wall_id}'.`);
          return;
        }

        const parentWall = wallMapData.get(win.wall_id);
        const wallLen = parentWall.length;
        const geom = win.geometry;

        // Authoritative processed center if available
        let center = null;
        if (geom && Array.isArray(geom.center) && geom.center.length >= 2 &&
            typeof geom.center[0] === 'number' && typeof geom.center[1] === 'number') {
          center = [geom.center[0], geom.center[1]];
        }

        let offset = (geom && typeof geom.offset_from_start === 'number')
          ? geom.offset_from_start
          : win.offset;
        let position = win.position;

        if (typeof offset === 'number' && !isNaN(offset)) {
          if (offset < 0) {
            warnings.push(`Window '${id}' has negative offset (${offset}m).`);
          } else if (offset > wallLen) {
            warnings.push(`Window '${id}' offset (${offset}m) exceeds wall length (${wallLen.toFixed(2)}m).`);
          }
          position = wallLen > 0 ? offset / wallLen : 0.5;
        } else if (typeof position === 'number' && !isNaN(position)) {
          if (position < 0 || position > 1) {
            warnings.push(`Window '${id}' position outside [0, 1]. Clamped to 0.5.`);
            position = Math.max(0, Math.min(1, position));
          }
          offset = position * wallLen;
        } else if (!center) {
          position = 0.5;
          offset = 0.5 * wallLen;
          warnings.push(`Window '${id}' has missing or invalid offset/position. Defaulted to midpoint.`);
        }

        let width = (geom && typeof geom.width === 'number') ? geom.width : win.width;
        if (typeof width !== 'number' || isNaN(width) || width <= 0) {
          width = 1.5;
          warnings.push(`Window '${id}' has non-positive width. Defaulted to 1.5m.`);
        } else if (width > wallLen) {
          warnings.push(`Window '${id}' width (${width}m) exceeds wall '${win.wall_id}' length (${wallLen.toFixed(2)}m).`);
        }

        let height = (geom && typeof geom.height === 'number')
          ? geom.height
          : ((typeof win.height === 'number' && win.height > 0) ? win.height : windowHeightDefault);

        let sillHeight = (geom && typeof geom.sill_height === 'number')
          ? geom.sill_height
          : ((typeof win.sill_height === 'number' && win.sill_height >= 0) ? win.sill_height : windowSillHeightDefault);

        validWindows.push({
          id,
          wall_id: win.wall_id,
          center,
          offset,
          position,
          width,
          height,
          sill_height: sillHeight,
          geometry: geom || null
        });
      });
    }

    // Rooms
    const validRooms = [];
    if (Array.isArray(rawData.rooms)) {
      rawData.rooms.forEach((room, idx) => {
        const id = room.id || `room_auto_${idx}`;
        const name = room.name || room.label || `Room ${idx + 1}`;
        const geom = room.geometry;

        const polygon = (geom && Array.isArray(geom.polygon)) ? geom.polygon : room.polygon;

        if (!Array.isArray(polygon) || polygon.length < 3) {
          warnings.push(`Room '${id}' has fewer than 3 vertices and will be skipped.`);
          return;
        }

        const validPolygon = [];
        let hasInvalidPt = false;
        polygon.forEach(pt => {
          if (Array.isArray(pt) && pt.length >= 2 && 
              typeof pt[0] === 'number' && !isNaN(pt[0]) && 
              typeof pt[1] === 'number' && !isNaN(pt[1])) {
            validPolygon.push([pt[0], pt[1]]);
          } else {
            hasInvalidPt = true;
          }
        });

        if (hasInvalidPt || validPolygon.length < 3) {
          warnings.push(`Room '${id}' contains invalid coordinate tuples.`);
          return;
        }

        const centroid = (geom && Array.isArray(geom.centroid) && geom.centroid.length >= 2)
          ? [geom.centroid[0], geom.centroid[1]]
          : null;
        const area = (geom && typeof geom.area === 'number')
          ? geom.area
          : null;
        const perimeter = (geom && typeof geom.perimeter === 'number')
          ? geom.perimeter
          : null;
        const bounds = (geom && Array.isArray(geom.bounds))
          ? geom.bounds
          : null;

        validRooms.push({
          id,
          name,
          label: room.label || name,
          polygon: validPolygon,
          centroid,
          area,
          perimeter,
          bounds,
          geometry: geom || null
        });
      });
    }

    const sanitizedScene = {
      version: rawData.version || '1.0',
      units,
      coordinate_system,
      wall_height: wallHeight,
      defaults,
      settings,
      scale: rawData.scale || null,
      validation: rawData.validation || { valid: true, issues: [] },
      topology_operations: rawData.topology_operations || [],
      walls: validWalls,
      doors: validDoors,
      windows: validWindows,
      rooms: validRooms,
      metadata: rawData.metadata || null
    };

    return {
      isValid: validWalls.length > 0 || validRooms.length > 0,
      scene: sanitizedScene,
      errors,
      warnings
    };
  }
}
