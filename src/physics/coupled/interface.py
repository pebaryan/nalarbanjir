"""
Bank interface: maps 1D network nodes to 2D grid cells.

Each InterfacePoint is a location where the 1D channel can overflow onto
(or receive return flow from) the 2D floodplain.  The bank_elevation acts
as the weir crest that controls when exchange begins.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.physics.state import Solver1DState, Solver2DState
from src.physics.solver_1d.network import ChannelNetwork


@dataclass
class InterfacePoint:
    """One coupling point between a 1D node and a 2D grid cell."""
    node_id: str          # 1D network node identifier
    node_index: int       # index in the 1D state arrays
    i: int                # 2D grid row (x) index
    j: int                # 2D grid column (y) index
    bank_elevation: float # z_bank [m a.s.l.] — weir crest height


@dataclass
class BankInterface:
    """
    Collection of 1D↔2D coupling points along a channel bank.

    Provides helpers to extract water-surface elevations at all interface
    points from both solver states, ready for the weir flux computation.
    """
    points: list[InterfacePoint] = field(default_factory=list)

    @property
    def n_points(self) -> int:
        return len(self.points)

    def extract_wse_1d(self, state_1d: Solver1DState) -> np.ndarray:
        """Water surface elevation [m] at each interface point from the 1D state."""
        return np.array([
            float(state_1d.water_surface_elev[p.node_index])
            for p in self.points
        ])

    def extract_wse_2d(self, state_2d: Solver2DState) -> np.ndarray:
        """Water surface elevation η = z + h [m] at each adjacent 2D cell."""
        return np.array([
            float(state_2d.bed_elevation[p.i, p.j] + state_2d.water_depth[p.i, p.j])
            for p in self.points
        ])

    def bank_elevations(self) -> np.ndarray:
        """Array of bank crest elevations [m] at each interface point."""
        return np.array([p.bank_elevation for p in self.points])

    @classmethod
    def from_reach(
        cls,
        network: ChannelNetwork,
        reach_id: str,
        nx: int,
        ny: int,
        dx: float,
        dy: float,
        bank_elevation: float = 3.0,
        bank_side: str = "left",   # "left" or "right"
    ) -> "BankInterface":
        """
        Build a bank interface by projecting 1D cross-section nodes onto the 2D grid.

        Assumes the channel runs along the y-axis of the 2D grid, centred at
        x = nx//2.  Cross-sections are mapped to j-indices proportionally to
        their chainage / reach length.
        """
        reach_nodes = network.get_reach_nodes(reach_id)
        node_ids_in_reach = network.edges[reach_id].node_ids

        # Only interior cross-section nodes have geometry
        cs_nodes = [n for n in reach_nodes if n.cross_section is not None]
        if not cs_nodes:
            return cls(points=[])

        total_length = reach_nodes[-1].chainage
        if total_length <= 0:
            return cls(points=[])

        i_channel = nx // 2
        i_bank = (i_channel - 1) if bank_side == "left" else (i_channel + 1)
        i_bank = max(0, min(nx - 1, i_bank))

        points: list[InterfacePoint] = []
        for node in cs_nodes:
            j = int(round(node.chainage / total_length * (ny - 1)))
            j = max(0, min(ny - 1, j))
            node_index = list(node_ids_in_reach).index(node.id)
            points.append(InterfacePoint(
                node_id=node.id,
                node_index=node_index,
                i=i_bank,
                j=j,
                bank_elevation=bank_elevation,
            ))

        return cls(points=points)
