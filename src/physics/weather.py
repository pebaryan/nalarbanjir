"""Weather simulation module for flood prediction.

This module provides weather simulation capabilities including:
- Rainfall intensity distribution models
- Wind field generation
- Storm cell tracking
- Weather time series generation
"""

import logging
import numpy as np
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from scipy.ndimage import gaussian_filter

logger = logging.getLogger(__name__)


class RainfallDistributionType(Enum):
    """Types of rainfall distribution patterns."""

    UNIFORM = "uniform"
    GRADIENT = "gradient"
    CIRCULAR = "circular"
    STORM_CELL = "storm_cell"
    FRONTAL = "frontal"


class WindPatternType(Enum):
    """Types of wind field patterns."""

    UNIFORM = "uniform"
    ROTATIONAL = "rotational"
    CONVERGENT = "convergent"
    TURBULENT = "turbulent"


@dataclass
class RainfallParameters:
    """Parameters for rainfall simulation.

    Attributes:
        intensity_mm_hr: Rainfall intensity in mm/hour
        duration_hours: Duration of rainfall event
        distribution: Type of spatial distribution
        peak_intensity_factor: Factor for peak intensity (1.0 = uniform)
        storm_center: Center coordinates for storm cells (x, y)
        storm_radius: Radius of storm cell influence
    """

    intensity_mm_hr: float = 10.0
    duration_hours: float = 24.0
    distribution: RainfallDistributionType = RainfallDistributionType.UNIFORM
    peak_intensity_factor: float = 2.0
    storm_center: Tuple[float, float] = field(default_factory=lambda: (0.5, 0.5))
    storm_radius: float = 0.2
    temporal_pattern: str = "constant"  # constant, increasing, decreasing, peak


@dataclass
class WindParameters:
    """Parameters for wind field simulation.

    Attributes:
        speed_ms: Wind speed in m/s
        direction_degrees: Wind direction in degrees (0 = North, 90 = East)
        pattern: Type of wind pattern
        turbulence_intensity: Level of turbulence (0.0 - 1.0)
        gust_factor: Factor for wind gusts
    """

    speed_ms: float = 5.0
    direction_degrees: float = 0.0
    pattern: WindPatternType = WindPatternType.UNIFORM
    turbulence_intensity: float = 0.1
    gust_factor: float = 1.5


@dataclass
class WeatherState:
    """Current weather state at a point in time.

    Attributes:
        time_hours: Time in hours from start
        rainfall_intensity: Current rainfall intensity (mm/hr)
        wind_speed: Current wind speed (m/s)
        wind_direction: Current wind direction (degrees)
        cumulative_rainfall: Total rainfall so far (mm)
    """

    time_hours: float = 0.0
    rainfall_intensity: float = 0.0
    wind_speed: float = 0.0
    wind_direction: float = 0.0
    cumulative_rainfall: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "time_hours": self.time_hours,
            "rainfall_intensity": self.rainfall_intensity,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "cumulative_rainfall": self.cumulative_rainfall,
        }


class WeatherSimulator:
    """Simulates weather conditions for flood modeling.

    Provides realistic rainfall and wind field generation with
    spatial and temporal variability.

    Example:
        >>> weather = WeatherSimulator(grid_size=(100, 100))
        >>> weather.setup_rainfall(intensity_mm_hr=25.0, distribution="storm_cell")
        >>> weather.setup_wind(speed_ms=10.0, direction_degrees=45.0)
        >>> rainfall_field = weather.get_rainfall_field(time_hours=6.0)
        >>> wind_field = weather.get_wind_field()
    """

    def __init__(
        self,
        grid_size: Tuple[int, int],
        bounds: Optional[Tuple[float, float, float, float]] = None,
    ):
        """Initialize weather simulator.

        Args:
            grid_size: Grid dimensions (nx, ny)
            bounds: Spatial bounds (min_x, min_y, max_x, max_y), default unit square
        """
        self.nx, self.ny = grid_size
        self.bounds = bounds or (0.0, 0.0, 1.0, 1.0)

        # Initialize parameter storage
        self.rainfall_params: Optional[RainfallParameters] = None
        self.wind_params: Optional[WindParameters] = None

        # Grid coordinates
        self._setup_grid()

        # State tracking
        self.current_time: float = 0.0
        self.weather_history: list = []

        logger.info(f"WeatherSimulator initialized with grid {self.nx}x{self.ny}")

    def _setup_grid(self):
        """Setup normalized grid coordinates."""
        x = np.linspace(0, 1, self.nx)
        y = np.linspace(0, 1, self.ny)
        self.X, self.Y = np.meshgrid(x, y)
        self.X = self.X.T  # Shape: (nx, ny)
        self.Y = self.Y.T

    def setup_rainfall(
        self,
        intensity_mm_hr: float = 10.0,
        duration_hours: float = 24.0,
        distribution: str = "uniform",
        **kwargs,
    ):
        """Configure rainfall parameters.

        Args:
            intensity_mm_hr: Rainfall intensity in mm/hour
            duration_hours: Duration of rainfall event
            distribution: Distribution type string
            **kwargs: Additional distribution-specific parameters
        """
        try:
            dist_type = RainfallDistributionType(distribution)
        except ValueError:
            logger.warning(f"Unknown distribution type '{distribution}', using uniform")
            dist_type = RainfallDistributionType.UNIFORM

        self.rainfall_params = RainfallParameters(
            intensity_mm_hr=intensity_mm_hr,
            duration_hours=duration_hours,
            distribution=dist_type,
            peak_intensity_factor=kwargs.get("peak_intensity_factor", 2.0),
            storm_center=kwargs.get("storm_center", (0.5, 0.5)),
            storm_radius=kwargs.get("storm_radius", 0.2),
            temporal_pattern=kwargs.get("temporal_pattern", "constant"),
        )

        logger.info(
            f"Rainfall configured: {intensity_mm_hr} mm/hr for {duration_hours} hours"
        )

    def setup_wind(
        self,
        speed_ms: float = 5.0,
        direction_degrees: float = 0.0,
        pattern: str = "uniform",
        **kwargs,
    ):
        """Configure wind parameters.

        Args:
            speed_ms: Wind speed in m/s
            direction_degrees: Wind direction (0=North, 90=East)
            pattern: Wind pattern type string
            **kwargs: Additional pattern-specific parameters
        """
        try:
            pattern_type = WindPatternType(pattern)
        except ValueError:
            logger.warning(f"Unknown wind pattern '{pattern}', using uniform")
            pattern_type = WindPatternType.UNIFORM

        self.wind_params = WindParameters(
            speed_ms=speed_ms,
            direction_degrees=direction_degrees,
            pattern=pattern_type,
            turbulence_intensity=kwargs.get("turbulence_intensity", 0.1),
            gust_factor=kwargs.get("gust_factor", 1.5),
        )

        logger.info(f"Wind configured: {speed_ms} m/s from {direction_degrees}°")

    def get_rainfall_field(self, time_hours: Optional[float] = None) -> np.ndarray:
        """Generate spatial rainfall intensity field.

        Args:
            time_hours: Time in hours (uses current time if None)

        Returns:
            2D array of rainfall intensity (mm/hr)
        """
        if self.rainfall_params is None:
            return np.zeros((self.nx, self.ny))

        t = time_hours if time_hours is not None else self.current_time

        # Get base intensity with temporal variation
        base_intensity = self._get_temporal_intensity(t)

        # Apply spatial distribution
        if self.rainfall_params.distribution == RainfallDistributionType.UNIFORM:
            field = np.full((self.nx, self.ny), base_intensity)

        elif self.rainfall_params.distribution == RainfallDistributionType.GRADIENT:
            # Linear gradient from top to bottom
            gradient = np.linspace(0.5, 1.5, self.ny).reshape(1, self.ny)
            field = base_intensity * gradient.T

        elif self.rainfall_params.distribution == RainfallDistributionType.CIRCULAR:
            # Circular gradient from center
            cx, cy = 0.5, 0.5
            dist = np.sqrt((self.X - cx) ** 2 + (self.Y - cy) ** 2)
            max_dist = np.sqrt(0.5)
            factor = 1.0 - (dist / max_dist) * 0.5
            field = base_intensity * factor

        elif self.rainfall_params.distribution == RainfallDistributionType.STORM_CELL:
            # Gaussian storm cell
            cx, cy = self.rainfall_params.storm_center
            radius = self.rainfall_params.storm_radius
            dist_sq = (self.X - cx) ** 2 + (self.Y - cy) ** 2

            # Gaussian decay from center
            factor = self.rainfall_params.peak_intensity_factor * np.exp(
                -dist_sq / (2 * radius**2)
            )
            # Ensure minimum intensity of 1.0 at center
            factor = np.maximum(factor, 1.0)
            field = base_intensity * factor

        elif self.rainfall_params.distribution == RainfallDistributionType.FRONTAL:
            # Frontal system - band of rain
            front_position = 0.5 + 0.3 * np.sin(2 * np.pi * self.X)
            dist_from_front = np.abs(self.Y - front_position)
            factor = np.exp(-dist_from_front / 0.1) * 2.0
            field = base_intensity * factor

        else:
            field = np.full((self.nx, self.ny), base_intensity)

        # Add some noise for realism
        noise = np.random.normal(0, 0.05, (self.nx, self.ny))
        field = field * (1.0 + noise)

        # Ensure non-negative
        return np.maximum(field, 0.0)

    def _get_temporal_intensity(self, time_hours: float) -> float:
        """Get rainfall intensity at a specific time with temporal variation."""
        if self.rainfall_params is None:
            return 0.0

        base = self.rainfall_params.intensity_mm_hr
        duration = self.rainfall_params.duration_hours
        pattern = self.rainfall_params.temporal_pattern

        if pattern == "constant":
            return base if time_hours <= duration else 0.0

        elif pattern == "increasing":
            if time_hours > duration:
                return 0.0
            factor = time_hours / duration
            return base * (0.3 + 0.7 * factor)

        elif pattern == "decreasing":
            if time_hours > duration:
                return 0.0
            factor = 1.0 - (time_hours / duration)
            return base * (0.3 + 0.7 * factor)

        elif pattern == "peak":
            if time_hours > duration:
                return 0.0
            # Peak in the middle
            normalized_time = time_hours / duration
            factor = np.sin(np.pi * normalized_time)
            return base * factor

        return base

    def get_wind_field(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate wind velocity field (u, v components).

        Returns:
            Tuple of (u, v) velocity components in m/s
        """
        if self.wind_params is None:
            return np.zeros((self.nx, self.ny)), np.zeros((self.nx, self.ny))

        speed = self.wind_params.speed_ms
        direction_rad = np.radians(self.wind_params.direction_degrees)

        # Base wind components
        u_base = speed * np.sin(direction_rad)  # Eastward
        v_base = speed * np.cos(direction_rad)  # Northward

        if self.wind_params.pattern == WindPatternType.UNIFORM:
            u = np.full((self.nx, self.ny), u_base)
            v = np.full((self.nx, self.ny), v_base)

        elif self.wind_params.pattern == WindPatternType.ROTATIONAL:
            # Rotational/cyclonic pattern around center
            cx, cy = 0.5, 0.5
            dx = self.X - cx
            dy = self.Y - cy
            dist = np.sqrt(dx**2 + dy**2)

            # Tangential velocity component
            max_radius = 0.4
            rotational_speed = speed * np.exp(-dist / max_radius)

            # Perpendicular to radial direction
            u = -rotational_speed * dy / (dist + 1e-10)
            v = rotational_speed * dx / (dist + 1e-10)

        elif self.wind_params.pattern == WindPatternType.CONVERGENT:
            # Converging toward center (like a low pressure system)
            cx, cy = 0.5, 0.5
            dx = self.X - cx
            dy = self.Y - cy
            dist = np.sqrt(dx**2 + dy**2)

            max_radius = 0.4
            convergence = speed * np.exp(-dist / max_radius)

            u = -convergence * dx / (dist + 1e-10)
            v = -convergence * dy / (dist + 1e-10)

        elif self.wind_params.pattern == WindPatternType.TURBULENT:
            # Turbulent flow with base direction
            u = np.full((self.nx, self.ny), u_base)
            v = np.full((self.nx, self.ny), v_base)

            # Add turbulence
            turb = self.wind_params.turbulence_intensity
            u += np.random.normal(0, speed * turb, (self.nx, self.ny))
            v += np.random.normal(0, speed * turb, (self.nx, self.ny))

        else:
            u = np.full((self.nx, self.ny), u_base)
            v = np.full((self.nx, self.ny), v_base)

        # Add gusts
        if self.wind_params.gust_factor > 1.0:
            gust_mask = np.random.random((self.nx, self.ny)) < 0.05
            gust_factor = np.where(gust_mask, self.wind_params.gust_factor, 1.0)
            u *= gust_factor
            v *= gust_factor

        return u, v

    def get_wind_speed_field(self) -> np.ndarray:
        """Get wind speed magnitude field.

        Returns:
            2D array of wind speeds in m/s
        """
        u, v = self.get_wind_field()
        return np.sqrt(u**2 + v**2)

    def step(self, dt_hours: float = 0.1):
        """Advance weather simulation by time step.

        Args:
            dt_hours: Time step in hours
        """
        self.current_time += dt_hours

        # Record current state
        rainfall_field = self.get_rainfall_field()
        avg_rainfall = float(np.mean(rainfall_field))

        wind_speed_field = self.get_wind_speed_field()
        avg_wind = float(np.mean(wind_speed_field))

        state = WeatherState(
            time_hours=self.current_time,
            rainfall_intensity=avg_rainfall,
            wind_speed=avg_wind,
            wind_direction=self.wind_params.direction_degrees
            if self.wind_params
            else 0.0,
        )

        self.weather_history.append(state)

    def get_cumulative_rainfall(self, time_hours: Optional[float] = None) -> np.ndarray:
        """Calculate cumulative rainfall depth up to given time.

        Args:
            time_hours: Time in hours (uses current time if None)

        Returns:
            2D array of cumulative rainfall in mm
        """
        t = time_hours if time_hours is not None else self.current_time

        if self.rainfall_params is None:
            return np.zeros((self.nx, self.ny))

        # For simplicity, assume constant spatial pattern and integrate temporal
        base_intensity = self.rainfall_params.intensity_mm_hr

        # Get average temporal factor
        if self.rainfall_params.temporal_pattern == "constant":
            if t <= self.rainfall_params.duration_hours:
                temporal_integral = base_intensity * t
            else:
                temporal_integral = base_intensity * self.rainfall_params.duration_hours
        elif self.rainfall_params.temporal_pattern == "peak":
            # Integral of sin(πt/T) from 0 to min(t, T)
            T = self.rainfall_params.duration_hours
            t_eff = min(t, T)
            temporal_integral = (
                base_intensity * T / np.pi * (1 - np.cos(np.pi * t_eff / T))
            )
        else:
            # Default to constant
            temporal_integral = base_intensity * min(
                t, self.rainfall_params.duration_hours
            )

        # Apply spatial distribution
        rainfall_field = self.get_rainfall_field(t)

        # Scale to match temporal integral
        current_avg = np.mean(rainfall_field)
        if current_avg > 0:
            cumulative = rainfall_field / current_avg * temporal_integral
        else:
            cumulative = np.zeros_like(rainfall_field)

        return cumulative

    def get_runoff_coefficient(self, land_use: np.ndarray) -> np.ndarray:
        """Calculate runoff coefficient based on land use.

        Args:
            land_use: 2D array of land use codes

        Returns:
            2D array of runoff coefficients (0.0 - 1.0)
        """
        # Simplified runoff coefficients
        # In practice, these would come from a lookup table
        runoff_map = {
            0: 0.05,  # Water
            1: 0.9,  # Urban
            2: 0.3,  # Forest
            3: 0.4,  # Agriculture
            4: 0.1,  # Wetland
            5: 0.6,  # Barren
        }

        # Vectorized lookup
        result = np.zeros_like(land_use, dtype=float)
        for code, coeff in runoff_map.items():
            result[land_use == code] = coeff

        return result

    def export_weather_data(self) -> Dict[str, Any]:
        """Export weather configuration and state.

        Returns:
            Dictionary with weather data
        """
        return {
            "grid_size": (self.nx, self.ny),
            "bounds": self.bounds,
            "rainfall": self.rainfall_params.__dict__ if self.rainfall_params else None,
            "wind": self.wind_params.__dict__ if self.wind_params else None,
            "current_time": self.current_time,
            "history": [s.to_dict() for s in self.weather_history],
        }
