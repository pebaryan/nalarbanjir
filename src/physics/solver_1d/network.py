"""
Channel network graph for the 1D solver.

The network is a directed graph where:
  Nodes (NodeType):
    - CROSS_SECTION: interior computational node (has a CrossSection geometry)
    - JUNCTION:      confluence where multiple reaches meet
    - BOUNDARY:      upstream or downstream boundary (has a BoundaryCondition)

  Edges (reaches): directed from upstream to downstream node.
    Each edge has a length [m] and bed slope [m/m].

The Preissmann solver traverses this graph, assembling one block-tridiagonal
system per reach and resolving junctions iteratively.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

from src.physics.solver_1d.cross_section import CrossSection


class NodeType(Enum):
    CROSS_SECTION = "cross_section"
    JUNCTION      = "junction"
    BOUNDARY      = "boundary"


class BCType1D(Enum):
    DISCHARGE = "discharge"   # upstream: Q(t) hydrograph
    STAGE     = "stage"       # downstream: h(t) stage


@dataclass
class BoundaryCondition1D:
    """Time-series boundary condition for a network boundary node."""
    bc_type: BCType1D
    times: np.ndarray    # [s]
    values: np.ndarray   # [m³/s] for DISCHARGE, [m a.s.l.] for STAGE

    def get_value(self, t: float) -> float:
        """Interpolate boundary value at time t."""
        return float(np.interp(t, self.times, self.values))

    @classmethod
    def constant_discharge(cls, Q: float) -> "BoundaryCondition1D":
        return cls(BCType1D.DISCHARGE,
                   np.array([0.0, 1e9]),
                   np.array([Q, Q]))

    @classmethod
    def constant_stage(cls, h: float) -> "BoundaryCondition1D":
        return cls(BCType1D.STAGE,
                   np.array([0.0, 1e9]),
                   np.array([h, h]))


@dataclass
class NetworkNode:
    id: str
    node_type: NodeType
    chainage: float = 0.0         # position within its reach [m]
    reach_id: str = ""            # parent reach ID
    cross_section: Optional[CrossSection] = None
    boundary_condition: Optional[BoundaryCondition1D] = None


@dataclass
class NetworkEdge:
    """Directed edge representing a river reach."""
    id: str
    upstream_node_id: str
    downstream_node_id: str
    length: float                  # [m]
    slope: float                   # [m/m] mean bed slope
    node_ids: list[str] = field(default_factory=list)   # ordered node IDs in this reach


class ChannelNetwork:
    """
    Directed graph of river reaches and nodes.

    Provides methods to query neighbours, reaches, and assemble
    the node ordering needed by the Preissmann solver.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, NetworkNode] = {}
        self._edges: dict[str, NetworkEdge] = {}
        # Adjacency: node_id -> list of edge ids going downstream
        self._downstream: dict[str, list[str]] = {}
        self._upstream:   dict[str, list[str]] = {}

    # ── Building the network ──────────────────────────────────────────────

    def add_node(self, node: NetworkNode) -> None:
        self._nodes[node.id] = node
        if node.id not in self._downstream:
            self._downstream[node.id] = []
        if node.id not in self._upstream:
            self._upstream[node.id] = []

    def add_edge(self, edge: NetworkEdge) -> None:
        self._edges[edge.id] = edge
        self._downstream.setdefault(edge.upstream_node_id, []).append(edge.id)
        self._upstream.setdefault(edge.downstream_node_id, []).append(edge.id)

    # ── Queries ───────────────────────────────────────────────────────────

    @property
    def nodes(self) -> dict[str, NetworkNode]:
        return self._nodes

    @property
    def edges(self) -> dict[str, NetworkEdge]:
        return self._edges

    def get_node(self, node_id: str) -> NetworkNode:
        return self._nodes[node_id]

    def get_reach_nodes(self, reach_id: str) -> list[NetworkNode]:
        """Return ordered list of nodes in a reach (upstream → downstream)."""
        edge = self._edges[reach_id]
        return [self._nodes[nid] for nid in edge.node_ids]

    def upstream_nodes(self, node_id: str) -> list[NetworkNode]:
        return [self._nodes[self._edges[eid].upstream_node_id]
                for eid in self._upstream.get(node_id, [])]

    def downstream_nodes(self, node_id: str) -> list[NetworkNode]:
        return [self._nodes[self._edges[eid].downstream_node_id]
                for eid in self._downstream.get(node_id, [])]

    def boundary_nodes(self) -> list[NetworkNode]:
        return [n for n in self._nodes.values() if n.node_type == NodeType.BOUNDARY]

    def all_cross_section_nodes(self) -> list[NetworkNode]:
        """All computational cross-section nodes across all reaches."""
        return [n for n in self._nodes.values() if n.node_type == NodeType.CROSS_SECTION]

    # ── Factory helpers ───────────────────────────────────────────────────

    @classmethod
    def simple_reach(
        cls,
        n_cross_sections: int,
        reach_length: float,
        cross_section: CrossSection,
        slope: float = 0.001,
        upstream_Q: float = 50.0,
        downstream_h: float = 5.0,
    ) -> "ChannelNetwork":
        """
        Build a single straight reach with uniform cross-sections.
        Useful for unit tests.
        """
        net = cls()
        node_ids = []

        # Cross-sections are evenly spaced BETWEEN the boundary nodes
        # Spacing = reach_length / (n_cross_sections + 1)
        dx_cs = reach_length / (n_cross_sections + 1)
        cs_chainages = np.array([(i + 1) * dx_cs for i in range(n_cross_sections)])

        # Upstream boundary
        up_bc = BoundaryCondition1D.constant_discharge(upstream_Q)
        up_node = NetworkNode("upstream", NodeType.BOUNDARY,
                               chainage=0.0, reach_id="r0",
                               boundary_condition=up_bc)
        net.add_node(up_node)
        node_ids.append("upstream")

        # Interior cross-section nodes
        for i in range(n_cross_sections):
            ch = cs_chainages[i]
            # Bed elevation decreases downstream (positive slope = downstream lower)
            z_offset = slope * (reach_length - ch)
            cs_adjusted = CrossSection(
                y_points=cross_section.y_points.copy(),
                z_points=cross_section.z_points + z_offset,
                manning_n=cross_section.manning_n,
                bank_left_z=cross_section.bank_left_z + z_offset,
                bank_right_z=cross_section.bank_right_z + z_offset,
            )
            node = NetworkNode(
                id=f"cs_{i}",
                node_type=NodeType.CROSS_SECTION,
                chainage=float(ch),
                reach_id="r0",
                cross_section=cs_adjusted,
            )
            net.add_node(node)
            node_ids.append(f"cs_{i}")

        # Downstream boundary
        down_bc = BoundaryCondition1D.constant_stage(downstream_h)
        down_node = NetworkNode("downstream", NodeType.BOUNDARY,
                                 chainage=reach_length, reach_id="r0",
                                 boundary_condition=down_bc)
        net.add_node(down_node)
        node_ids.append("downstream")

        # Single reach edge
        edge = NetworkEdge(
            id="r0",
            upstream_node_id="upstream",
            downstream_node_id="downstream",
            length=reach_length,
            slope=slope,
            node_ids=node_ids,
        )
        net.add_edge(edge)
        return net
