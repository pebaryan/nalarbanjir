"""Flow vector visualization component.

This module provides rendering capabilities for flow vector visualization
in the flood prediction world model.
"""

import numpy as np
from typing import Dict, Any, Tuple, List
import logging

logger = logging.getLogger(__name__)


class FlowVectorRenderer:
    """Renderer for flow vector visualization.

    Provides methods to render flow vector data for visualization purposes.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the flow vector renderer.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.vector_color = (
            config.get("color_schemes", {}).get("natural", {}).get("water", "#3b82f6")
        )
        self.vector_density = (
            config.get("components", {})
            .get("flow_vectors", {})
            .get("vector_density", 0.5)
        )
        self.max_vector_length = (
            config.get("components", {})
            .get("flow_vectors", {})
            .get("max_vector_length", 50.0)
        )
        logger.info("FlowVectorRenderer initialized")

    def render(
        self, velocity_x: np.ndarray, velocity_y: np.ndarray, water_surface: np.ndarray
    ) -> Dict[str, Any]:
        """Render flow vector data.

        Args:
            velocity_x: X-component of velocity array
            velocity_y: Y-component of velocity array
            water_surface: Water surface elevation array (for masking)

        Returns:
            Rendered flow vector data
        """
        # Calculate vector magnitudes
        magnitude = np.sqrt(velocity_x**2 + velocity_y**2)

        # Apply water mask (only show vectors where there's water)
        water_mask = (
            water_surface > 0.01
        )  # Only show vectors where there's meaningful water

        # Sample vectors based on density
        ny, nx = velocity_x.shape
        step_y = max(1, int(1 / self.vector_density))
        step_x = max(1, int(1 / self.vector_density))

        vectors = []
        for i in range(0, ny, step_y):
            for j in range(0, nx, step_x):
                if water_mask[i, j]:
                    # Scale vector for visualization
                    scale = min(
                        self.max_vector_length, magnitude[i, j] * 10
                    )  # Scale factor
                    if scale > 0.1:  # Only show significant vectors
                        vectors.append(
                            {
                                "x": float(j),
                                "y": float(i),
                                "u": float(velocity_x[i, j] * scale),
                                "v": float(velocity_y[i, j] * scale),
                                "magnitude": float(magnitude[i, j]),
                                "scale_factor": scale,
                            }
                        )

        # Prepare rendering data
        render_data = {
            "type": "flow_vectors",
            "vectors": vectors,
            "color": self.vector_color,
            "density": self.vector_density,
            "max_magnitude": float(np.max(magnitude)) if magnitude.size > 0 else 0.0,
            "mean_magnitude": float(np.mean(magnitude)) if magnitude.size > 0 else 0.0,
            "vector_count": len(vectors),
        }

        return render_data

    def get_legend(self) -> Dict[str, Any]:
        """Get legend information for flow vectors.

        Returns:
            Legend dictionary
        """
        return {
            "type": "flow_vectors",
            "label": "Flow Velocity (m/s)",
            "color": self.vector_color,
            "unit": "m/s",
            "min_value": 0.0,
            "max_value": 5.0,  # Default max, can be configured
        }


class FlowAnalyzer:
    """Analyzer for flow characteristics.

    Provides methods to analyze flow data for features and patterns.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the flow analyzer.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def analyze_flow(
        self, velocity_x: np.ndarray, velocity_y: np.ndarray, water_surface: np.ndarray
    ) -> Dict[str, Any]:
        """Analyze flow characteristics.

        Args:
            velocity_x: X-component of velocity array
            velocity_y: Y-component of velocity array
            water_surface: Water surface elevation array

        Returns:
            Analysis results dictionary
        """
        # Calculate vector magnitudes
        magnitude = np.sqrt(velocity_x**2 + velocity_y**2)

        # Apply water mask
        water_mask = water_surface > 0.01

        if np.any(water_mask):
            masked_magnitude = magnitude[water_mask]

            # Basic statistics
            stats = {
                "max_velocity": float(np.max(masked_magnitude)),
                "mean_velocity": float(np.mean(masked_magnitude)),
                "min_velocity": float(np.min(masked_magnitude)),
                "std_velocity": float(np.std(masked_magnitude)),
                "velocity_variance": float(np.var(masked_magnitude)),
            }

            # Flow direction statistics
            # Calculate angles where velocity is significant
            significant_mask = water_mask & (magnitude > 0.01)
            if np.any(significant_mask):
                angles = np.arctan2(
                    velocity_y[significant_mask], velocity_x[significant_mask]
                )
                # Convert to degrees for easier interpretation
                angles_deg = np.degrees(angles)
                stats["mean_flow_direction"] = float(np.mean(angles_deg))
                stats["direction_std"] = float(np.std(angles_deg))
            else:
                stats["mean_flow_direction"] = 0.0
                stats["direction_std"] = 0.0

            # Vorticity (curl of velocity field)
            if velocity_x.shape[0] > 1 and velocity_x.shape[1] > 1:
                # Calculate curl: dv/dx - du/dy
                dv_dx = np.gradient(velocity_y, axis=1)
                du_dy = np.gradient(velocity_x, axis=0)
                vorticity = dv_dx - du_dy
                masked_vorticity = vorticity[water_mask]
                stats["max_vorticity"] = float(np.max(np.abs(masked_vorticity)))
                stats["mean_vorticity"] = float(np.mean(np.abs(masked_vorticity)))
            else:
                stats["max_vorticity"] = 0.0
                stats["mean_vorticity"] = 0.0

        else:
            # No water present
            stats = {
                "max_velocity": 0.0,
                "mean_velocity": 0.0,
                "min_velocity": 0.0,
                "std_velocity": 0.0,
                "velocity_variance": 0.0,
                "mean_flow_direction": 0.0,
                "direction_std": 0.0,
                "max_vorticity": 0.0,
                "mean_vorticity": 0.0,
            }

        return stats
