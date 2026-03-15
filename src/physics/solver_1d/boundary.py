"""
Boundary condition applicators for the 1D Preissmann solver.

At each time step, boundary nodes are treated as known values:
  - Upstream DISCHARGE node: Q is prescribed → h is solved
  - Downstream STAGE node:   h is prescribed → Q is solved

These are applied by modifying the first/last rows of the
block-tridiagonal system assembled in preissmann.py.
"""
from __future__ import annotations

import numpy as np

from src.physics.solver_1d.network import ChannelNetwork, BCType1D, NodeType


def apply_boundary_conditions(
    h: np.ndarray,
    Q: np.ndarray,
    node_ids: list[str],
    network: ChannelNetwork,
    t: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply boundary conditions by overwriting h or Q at boundary nodes.

    This is called after the implicit solve to enforce prescribed values.
    The Preissmann assembly (preissmann.py) handles BC incorporation into
    the matrix; this function is a post-solve correction for robustness.

    Args:
        h:        Water surface elevation array [m], shape (n_nodes,)
        Q:        Discharge array [m³/s], shape (n_nodes,)
        node_ids: Ordered list of node IDs matching h and Q indices
        network:  ChannelNetwork
        t:        Current simulation time [s]

    Returns:
        h, Q — with boundary values enforced.
    """
    for i, nid in enumerate(node_ids):
        node = network.get_node(nid)
        if node.node_type != NodeType.BOUNDARY or node.boundary_condition is None:
            continue
        bc = node.boundary_condition
        value = bc.get_value(t)
        if bc.bc_type == BCType1D.DISCHARGE:
            Q[i] = value
        elif bc.bc_type == BCType1D.STAGE:
            h[i] = value
    return h, Q
