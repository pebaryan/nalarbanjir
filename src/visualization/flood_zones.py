"""Flood zone visualization component.

This module provides rendering capabilities for flood zone visualization
in the flood prediction world model.
"""

import numpy as np
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)


class FloodZoneMapper:
    """Mapper for flood zone visualization.

    Provides methods to map flood zone data for visualization purposes.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the flood zone mapper.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.color_scheme = (
            config.get("color_schemes", {})
            .get("natural", {})
            .get(
                "risk",
                {
                    "low": "#10b981",
                    "moderate": "#f59e0b",
                    "high": "#ef4444",
                    "severe": "#7f1d1d",
                },
            )
        )
        logger.info("FloodZoneMapper initialized")

    def render(
        self, terrain: Any, water_surface: np.ndarray, water_depth: np.ndarray
    ) -> Dict[str, Any]:
        """Render flood zone data.

        Args:
            terrain: Terrain model instance
            water_surface: Water surface elevation array
            water_depth: Water depth array

        Returns:
            Rendered flood zone data
        """
        # Get flood zones from terrain model
        flood_zones_dict = terrain.get_flood_zones(water_depth)

        # Prepare rendering data for each risk level
        zones_data = {}
        for risk_level in ["low_risk", "moderate_risk", "high_risk", "severe_risk"]:
            if risk_level in flood_zones_dict:
                # Convert list of (i,j) tuples to a mask
                mask = np.zeros_like(water_depth, dtype=bool)
                for i, j in flood_zones_dict[risk_level]:
                    if 0 <= i < water_depth.shape[0] and 0 <= j < water_depth.shape[1]:
                        mask[i, j] = True
                zones_data[risk_level] = mask.tolist()
            else:
                zones_data[risk_level] = []

        # Prepare rendering data
        render_data = {
            "type": "flood_zones",
            "zones": zones_data,
            "colors": {
                "low_risk": self.color_scheme.get("low", "#10b981"),
                "moderate_risk": self.color_scheme.get("moderate", "#f59e0b"),
                "high_risk": self.color_scheme.get("high", "#ef4444"),
                "severe_risk": self.color_scheme.get("severe", "#7f1d1d"),
            },
            "zones_present": list(flood_zones_dict.keys()),
        }

        return render_data

    def get_legend(self) -> Dict[str, Any]:
        """Get legend information for flood zones.

        Returns:
            Legend dictionary
        """
        return {
            "type": "flood_zones",
            "label": "Flood Risk Zones",
            "colors": self.color_scheme,
            "units": "risk level",
            "values": ["low", "moderate", "high", "severe"],
        }


class FloodZoneAnalyzer:
    """Analyzer for flood zone characteristics.

    Provides methods to analyze flood zone data for features and patterns.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the flood zone analyzer.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def analyze_zones(self, terrain: Any, water_depth: np.ndarray) -> Dict[str, Any]:
        """Analyze flood zone characteristics.

        Args:
            terrain: Terrain model instance
            water_depth: Water depth array

        Returns:
            Analysis results dictionary
        """
        # Get flood zones from terrain model
        flood_zones_dict = terrain.get_flood_zones(water_depth)

        total_cells = water_depth.size
        analysis = {
            "total_cells": int(total_cells),
            "flooded_cells": 0,
            "zone_areas": {},
            "zone_fractions": {},
            "max_risk_level": "none",
        }

        # Risk levels in order of severity
        risk_levels = ["low_risk", "moderate_risk", "high_risk", "severe_risk"]

        for risk_level in risk_levels:
            if risk_level in flood_zones_dict:
                cell_count = len(flood_zones_dict[risk_level])
                analysis["zone_areas"][risk_level] = cell_count
                analysis["zone_fractions"][risk_level] = (
                    cell_count / total_cells if total_cells > 0 else 0.0
                )
                analysis["flooded_cells"] += cell_count
            else:
                analysis["zone_areas"][risk_level] = 0
                analysis["zone_fractions"][risk_level] = 0.0

        # Determine max risk level present
        for risk_level in reversed(risk_levels):
            if analysis["zone_areas"][risk_level] > 0:
                analysis["max_risk_level"] = risk_level.replace("_risk", "")
                break

        # Overall flood fraction
        analysis["flood_fraction"] = (
            analysis["flooded_cells"] / total_cells if total_cells > 0 else 0.0
        )

        return analysis
