"""
Physics module — hydraulic solvers and terrain modeling.

New architecture (v2):
  solver_2d/   — Finite-volume 2D solver (HLLE Riemann)
  solver_1d/   — Preissmann implicit 1D solver
  coupled/     — 1D+2D lateral weir coupler
  state.py     — SimulationState dataclasses
  base.py      — AbstractSolver protocol

Legacy (deprecated — kept for reference only):
  shallow_water.py  — replaced by solver_2d/
"""
