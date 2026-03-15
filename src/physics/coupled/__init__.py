"""
1D+2D coupling layer.

Provides:
  - BankInterface: maps 1D network nodes to 2D grid cells
  - compute_exchange: broad-crested weir lateral flux
"""
from src.physics.coupled.interface import BankInterface, InterfacePoint
from src.physics.coupled.coupler import compute_exchange

__all__ = ["BankInterface", "InterfacePoint", "compute_exchange"]
