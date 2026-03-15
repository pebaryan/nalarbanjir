"""Terrain modeling for flood prediction.

This module provides terrain representation and interaction capabilities
for the flood prediction world model, including elevation modeling,
land use classification, and flood zone identification.
"""

import logging
import numpy as np
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import math

logger = logging.getLogger(__name__)


class LandUseType(Enum):
    """Land use classification types."""

    WATER = "water"
    URBAN = "urban"
    AGRICULTURAL = "agricultural"
    FOREST = "forest"
    WETLAND = "wetland"
    OPEN_LAND = "open_land"


@dataclass
class TerrainFeature:
    """Represents a terrain feature with its properties."""

    # Feature type
    feature_type: LandUseType

    # Elevation (m above sea level)
    elevation: float

    # Permeability coefficient (0-1, higher = more permeable)
    permeability: float

    # Flood vulnerability rating (1-5, higher = more vulnerable)
    vulnerability: int

    # Name/description
    description: str


class TerrainModel:
    """Terrain model for flood prediction.

    Provides terrain representation, analysis, and interaction capabilities
    for understanding flood dynamics and risk assessment.
    """

    def __init__(self, config: Dict, resolution: Tuple[int, int] = (100, 100)):
        """Initialize the terrain model.

        Args:
            config: Configuration dictionary with terrain parameters
            resolution: Grid resolution (rows, columns)
        """
        self.config = config
        self.resolution = resolution
        self.nx, self.ny = resolution

        # Initialize terrain properties
        self.elevation = self._init_elevation()
        self.land_use = self._init_land_use()
        self.permeability = self._init_permeability()

        # Flood characteristics
        self.flood_thresholds = config.get(
            "flood_thresholds",
            {"minor": 1.0, "moderate": 2.0, "major": 3.0, "severe": 5.0},
        )

        # Initialize terrain features
        self.features = self._identify_terrain_features()

        logger.info(f"Terrain model initialized: {self.nx}x{self.ny} grid")
        logger.info(
            f"  Elevation range: {np.min(self.elevation):.2f}m to {np.max(self.elevation):.2f}m"
        )
        # Safely log flood thresholds
        thresholds = self.flood_thresholds
        threshold_str = (
            f"minor={thresholds.get('minor', 'N/A')}m, "
            f"moderate={thresholds.get('moderate', 'N/A')}m, "
            f"major={thresholds.get('major', 'N/A')}m, "
            f"severe={thresholds.get('severe', 'N/A')}m"
        )
        logger.info(f"  Flood thresholds: {threshold_str}")

    def _init_elevation(self) -> np.ndarray:
        """Initialize elevation data.

        Returns:
            Elevation array (meters above sea level)
        """
        elevation = np.zeros((self.ny, self.nx))

        # Generate realistic terrain using combined features
        for i in range(self.ny):
            for j in range(self.nx):
                # Base terrain from sinusoidal patterns
                x = j / self.nx
                y = i / self.ny

                # Multi-scale terrain features
                elevation[i, j] = (
                    self._generate_hills(x, y)
                    + self._generate_valleys(x, y)
                    + self._generate_plateaus(x, y)
                )

        # Ensure non-negative elevation
        elevation = np.maximum(elevation, 0)

        return elevation

    def _generate_hills(self, x: float, y: float) -> float:
        """Generate hill features.

        Args:
            x: Normalized x coordinate
            y: Normalized y coordinate

        Returns:
            Hill elevation contribution
        """
        # Primary hill pattern
        hill1 = 5.0 * np.sin(2 * np.pi * x) * np.cos(2 * np.pi * y)

        # Secondary hill pattern
        hill2 = 3.0 * np.sin(4 * np.pi * x) * np.sin(2 * np.pi * y)

        return np.maximum(0, hill1 + hill2)

    def _generate_valleys(self, x: float, y: float) -> float:
        """Generate valley features.

        Args:
            x: Normalized x coordinate
            y: Normalized y coordinate

        Returns:
            Valley elevation contribution (negative values)
        """
        # Primary valley pattern
        valley1 = -4.0 * np.cos(2 * np.pi * x) * np.sin(2 * np.pi * y)

        # Secondary valley pattern
        valley2 = -2.0 * np.cos(4 * np.pi * x) * np.cos(2 * np.pi * y)

        return valley1 + valley2

    def _generate_plateaus(self, x: float, y: float) -> float:
        """Generate plateau features.

        Args:
            x: Normalized x coordinate
            y: Normalized y coordinate

        Returns:
            Plateau elevation contribution
        """
        # Plateau pattern
        plateau = 2.0 * (np.exp(-10 * (x - 0.5) ** 2) * np.exp(-10 * (y - 0.5) ** 2))

        return plateau

    def _init_land_use(self) -> np.ndarray:
        """Initialize land use classification.

        Returns:
            Land use classification array
        """
        land_use = np.zeros((self.ny, self.nx), dtype=int)

        # Create mapping from LandUseType to integer codes
        land_use_mapping = {
            LandUseType.WATER: 0,
            LandUseType.URBAN: 1,
            LandUseType.AGRICULTURAL: 2,
            LandUseType.FOREST: 3,
            LandUseType.WETLAND: 4,
            LandUseType.OPEN_LAND: 5,
        }

        for i in range(self.ny):
            for j in range(self.nx):
                land_use_type = self._classify_land_use(i, j, self.elevation[i, j])
                land_use[i, j] = land_use_mapping[land_use_type]

        return land_use

    def _classify_land_use(self, i: int, j: int, elevation: float) -> LandUseType:
        """Classify land use based on location and elevation.

        Args:
            i: Row index
            j: Column index
            elevation: Terrain elevation

        Returns:
            Classified land use type
        """
        # Land use classification thresholds
        if elevation < 1.0:
            return LandUseType.WATER

        elif elevation < 3.0:
            if self._is_urban_area(i, j):
                return LandUseType.URBAN
            else:
                return LandUseType.AGRICULTURAL

        elif elevation < 6.0:
            if self._is_forested_area(i, j):
                return LandUseType.FOREST
            else:
                return LandUseType.WETLAND

        else:
            return LandUseType.OPEN_LAND

    def _is_urban_area(self, i: int, j: int) -> bool:
        """Check if location is in urban area.

        Args:
            i: Row index
            j: Column index

        Returns:
            True if urban area
        """
        # Urban areas typically near center or along main corridors
        center_distance = math.sqrt((i - self.ny / 2) ** 2 + (j - self.nx / 2) ** 2)

        return center_distance < self.ny * 0.3

    def _is_forested_area(self, i: int, j: int) -> bool:
        """Check if location is in forested area.

        Args:
            i: Row index
            j: Column index

        Returns:
            True if forested area
        """
        # Forested areas in elevated regions
        elevation = self.elevation[i, j]

        return elevation > 4.0

    def _init_permeability(self) -> np.ndarray:
        """Initialize permeability data.

        Returns:
            Permeability coefficient array
        """
        permeability = np.ones((self.ny, self.nx))

        # Create mapping from integer codes to LandUseType
        integer_to_land_use = {
            0: LandUseType.WATER,
            1: LandUseType.URBAN,
            2: LandUseType.AGRICULTURAL,
            3: LandUseType.FOREST,
            4: LandUseType.WETLAND,
            5: LandUseType.OPEN_LAND,
        }

        for i in range(self.ny):
            for j in range(self.nx):
                land_use_code = self.land_use[i, j]
                land_use_type = integer_to_land_use.get(
                    land_use_code, LandUseType.OPEN_LAND
                )

                # Permeability based on land use type
                if land_use_type == LandUseType.URBAN:
                    permeability[i, j] = 0.3  # Impermeable surfaces
                elif land_use_type == LandUseType.WATER:
                    permeability[i, j] = 0.1  # Water bodies
                elif land_use_type == LandUseType.FOREST:
                    permeability[i, j] = 0.7  # High permeability
                elif land_use_type == LandUseType.WETLAND:
                    permeability[i, j] = 0.8  # Very high permeability
                elif land_use_type == LandUseType.AGRICULTURAL:
                    permeability[i, j] = 0.6  # Moderate permeability
                else:
                    permeability[i, j] = 0.5  # Open land

        return permeability

    def _identify_terrain_features(self) -> List[TerrainFeature]:
        """Identify significant terrain features.

        Returns:
            List of identified terrain features
        """
        features = []

        # Identify high-elevation areas
        high_elevation_mask = self.elevation > np.percentile(self.elevation, 75)

        # Identify low-lying areas (potential flood zones)
        low_lying_mask = self.elevation < np.percentile(self.elevation, 25)

        # Create features from identified areas
        features.append(
            TerrainFeature(
                feature_type=LandUseType.URBAN,
                elevation=float(np.mean(self.elevation[high_elevation_mask])),
                permeability=0.4,
                vulnerability=2,
                description="Urban highland areas",
            )
        )

        features.append(
            TerrainFeature(
                feature_type=LandUseType.WETLAND,
                elevation=float(np.mean(self.elevation[low_lying_mask])),
                permeability=0.7,
                vulnerability=4,
                description="Low-lying wetland flood zones",
            )
        )

        return features

    def get_flood_zones(
        self, water_depth: np.ndarray
    ) -> Dict[str, List[Tuple[int, int]]]:
        """Identify flood zones based on water depth and terrain.

        Args:
            water_depth: Water depth array

        Returns:
            Dictionary of flood zones by risk level
        """
        zones = {
            "low_risk": [],
            "moderate_risk": [],
            "high_risk": [],
            "severe_risk": [],
        }

        # Classify each grid cell based on flood risk
        for i in range(self.ny):
            for j in range(self.nx):
                depth = water_depth[i, j]
                elevation = self.elevation[i, j]

                # Calculate flood risk index
                risk_index = self._calculate_risk_index(
                    depth, elevation, self.permeability[i, j]
                )

                # Assign to appropriate zone
                zone = self._assign_zone(risk_index)
                zones[zone].append((i, j))

        return zones

    def _calculate_risk_index(
        self, depth: float, elevation: float, permeability: float
    ) -> float:
        """Calculate flood risk index for a location.

        Args:
            depth: Water depth
            elevation: Terrain elevation
            permeability: Permeability coefficient

        Returns:
            Flood risk index (higher = higher risk)
        """
        # Risk components
        flood_potential = depth / (elevation + 1.0)
        drainage_efficiency = permeability * 10

        # Combined risk index
        risk_index = flood_potential / drainage_efficiency

        return risk_index

    def _assign_zone(self, risk_index: float) -> str:
        """Assign flood risk zone based on risk index.

        Args:
            risk_index: Calculated risk index

        Returns:
            Zone name
        """
        if risk_index < 0.3:
            return "low_risk"
        elif risk_index < 0.6:
            return "moderate_risk"
        elif risk_index < 1.0:
            return "high_risk"
        else:
            return "severe_risk"

    def export_terrain_data(self) -> Dict:
        """Export terrain data for analysis or visualization.

        Returns:
            Dictionary containing complete terrain information
        """
        return {
            "resolution": {"nx": self.nx, "ny": self.ny},
            "elevation": {
                "min": float(np.min(self.elevation)),
                "max": float(np.max(self.elevation)),
                "mean": float(np.mean(self.elevation)),
                "data": self.elevation,
            },
            "land_use": {
                "classification": self.land_use,
                "types": [t.value for t in LandUseType],
            },
            "permeability": {
                "min": float(np.min(self.permeability)),
                "max": float(np.max(self.permeability)),
                "mean": float(np.mean(self.permeability)),
                "data": self.permeability,
            },
            "flood_thresholds": self.flood_thresholds,
            "features": [
                {
                    "type": f.feature_type.value,
                    "elevation": f.elevation,
                    "permeability": f.permeability,
                    "vulnerability": f.vulnerability,
                    "description": f.description,
                }
                for f in self.features
            ],
        }
