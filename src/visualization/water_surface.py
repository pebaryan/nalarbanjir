"""Water surface visualization component.

This module provides rendering capabilities for water surface visualization
in the flood prediction world model.
"""

import numpy as np
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class WaterSurfaceRenderer:
    """Renderer for water surface visualization.

    Provides methods to render water surface data for visualization purposes.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the water surface renderer.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.color_scheme = config.get("color_schemes", {}).get("natural", {})
        self.water_color = self.color_scheme.get("water", "#3b82f6")
        logger.info("WaterSurfaceRenderer initialized")

    def render(
        self, water_surface: np.ndarray, elevation: np.ndarray
    ) -> Dict[str, Any]:
        """Render water surface data.

        Args:
            water_surface: Water surface elevation array
            elevation: Terrain elevation array

        Returns:
            Rendered water surface data
        """
        # Calculate water depth (water_surface - elevation)
        water_depth = water_surface - elevation
        # Ensure non-negative depth
        water_depth = np.maximum(water_depth, 0)

        # Prepare rendering data
        render_data = {
            "type": "water_surface",
            "data": water_depth.tolist(),
            "color": self.water_color,
            "min_depth": float(np.min(water_depth)),
            "max_depth": float(np.max(water_depth)),
            "mean_depth": float(np.mean(water_depth)),
            "valid_pixels": int(np.sum(water_depth > 0)),
            "total_pixels": water_depth.size,
        }

        return render_data

    def get_legend(self) -> Dict[str, Any]:
        """Get legend information for water surface.

        Returns:
            Legend dictionary
        """
        return {
            "type": "water_surface",
            "label": "Water Depth (m)",
            "color": self.water_color,
            "unit": "m",
            "min_value": 0.0,
            "max_value": 10.0,  # Default max, can be configured
        }


class WaterSurfaceAnalyzer:
    """Analyzer for water surface characteristics.

    Provides methods to analyze water surface data for features and patterns.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the water surface analyzer.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def analyze_surface(
        self, water_surface: np.ndarray, elevation: np.ndarray
    ) -> Dict[str, Any]:
        """Analyze water surface characteristics.

        Args:
            water_surface: Water surface elevation array
            elevation: Terrain elevation array

        Returns:
            Analysis results dictionary
        """
        water_depth = np.maximum(water_surface - elevation, 0)

        # Basic statistics
        stats = {
            "min_depth": float(np.min(water_depth)),
            "max_depth": float(np.max(water_depth)),
            "mean_depth": float(np.mean(water_depth)),
            "std_depth": float(np.std(water_depth)),
            "total_water_volume": float(np.sum(water_depth)),
            "flooded_area": int(np.sum(water_depth > 0.1)),  # Consider >0.1m as flooded
            "total_area": water_depth.size,
        }

        # Flood extent
        stats["flood_fraction"] = (
            stats["flooded_area"] / stats["total_area"]
            if stats["total_area"] > 0
            else 0.0
        )

        # Wave characteristics (simplified)
        if water_depth.size > 1:
            # Calculate gradients
            grad_y, grad_x = np.gradient(water_depth)
            slope_magnitude = np.sqrt(grad_x**2 + grad_y**2)
            stats["max_slope"] = float(np.max(slope_magnitude))
            stats["mean_slope"] = float(np.mean(slope_magnitude))
        else:
            stats["max_slope"] = 0.0
            stats["mean_slope"] = 0.0

        return stats
