"""Topological wall graph representation and connectivity analysis."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set, Tuple

import networkx as nx

from src.models import Point2D, WallEdge


class WallGraph:
    """
    Undirected geometric graph of junctions (nodes) and wall segments (edges).
    Junction nodes are keyed by rounded 2D coordinates.
    """

    def __init__(self, tolerance: float = 0.05) -> None:
        self.tolerance = tolerance
        self.graph = nx.Graph()
        self.walls_by_id: Dict[str, WallEdge] = {}
        self._node_coords: Dict[Tuple[float, float], Point2D] = {}

    def _coord_key(self, pt: Point2D) -> Tuple[float, float]:
        dec = 3 if self.tolerance >= 0.01 else 4
        return (round(pt.x, dec), round(pt.y, dec))

    def add_wall(self, wall: WallEdge) -> None:
        """Add wall edge and its start/end junction nodes."""
        self.walls_by_id[wall.id] = wall
        u = self._coord_key(wall.start)
        v = self._coord_key(wall.end)

        self._node_coords[u] = wall.start
        self._node_coords[v] = wall.end

        self.graph.add_node(u, point=wall.start)
        self.graph.add_node(v, point=wall.end)
        self.graph.add_edge(u, v, wall_id=wall.id, length=wall.length)

    def build_from_walls(self, walls: List[WallEdge]) -> None:
        self.graph.clear()
        self.walls_by_id.clear()
        self._node_coords.clear()
        for w in walls:
            self.add_wall(w)

    @property
    def junctions(self) -> List[Point2D]:
        """All unique junction points."""
        return list(self._node_coords.values())

    def get_junction_degree(self, pt: Point2D) -> int:
        k = self._coord_key(pt)
        return self.graph.degree(k) if self.graph.has_node(k) else 0

    def get_junction_degrees(self) -> Dict[str, int]:
        """Classify junction nodes by degree (dead_ends, corners, T-junctions, cross-junctions)."""
        counts = {"dead_end": 0, "corner": 0, "t_junction": 0, "cross_junction": 0, "complex": 0}
        for node in self.graph.nodes:
            deg = self.graph.degree(node)
            if deg == 1:
                counts["dead_end"] += 1
            elif deg == 2:
                counts["corner"] += 1
            elif deg == 3:
                counts["t_junction"] += 1
            elif deg == 4:
                counts["cross_junction"] += 1
            else:
                counts["complex"] += 1
        return counts

    def get_dead_end_endpoints(self) -> List[Tuple[str, Point2D]]:
        """Return list of (wall_id, endpoint) for all degree-1 dead ends."""
        dead_ends: List[Tuple[str, Point2D]] = []
        for node in self.graph.nodes:
            if self.graph.degree(node) == 1:
                # Find incident edge
                for neighbor in self.graph.neighbors(node):
                    edge_data = self.graph.get_edge_data(node, neighbor)
                    wall_id = edge_data.get("wall_id", "") if edge_data else ""
                    pt = self._node_coords.get(node, Point2D(node[0], node[1]))
                    dead_ends.append((wall_id, pt))
        return dead_ends

    def get_isolated_walls(self) -> List[WallEdge]:
        """Return walls where both endpoints are dead ends (degree 1 on both ends)."""
        isolated: List[WallEdge] = []
        for u, v, data in self.graph.edges(data=True):
            if self.graph.degree(u) == 1 and self.graph.degree(v) == 1:
                wid = data.get("wall_id", "")
                if wid in self.walls_by_id:
                    isolated.append(self.walls_by_id[wid])
        return isolated

    def get_connected_components(self) -> List[List[WallEdge]]:
        """Return connected subgraphs of walls."""
        components = []
        for comp_nodes in nx.connected_components(self.graph):
            comp_subgraph = self.graph.subgraph(comp_nodes)
            wall_ids = {data["wall_id"] for _, _, data in comp_subgraph.edges(data=True)}
            comp_walls = [self.walls_by_id[wid] for wid in wall_ids if wid in self.walls_by_id]
            if comp_walls:
                components.append(comp_walls)
        return components
