"""Tests for weather simulation module."""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from physics.weather import (
    WeatherSimulator,
    RainfallDistributionType,
    WindPatternType,
    RainfallParameters,
    WindParameters,
    WeatherState,
)


class TestWeatherSimulator:
    """Test suite for WeatherSimulator class."""

    def test_initialization(self):
        """Test basic initialization."""
        sim = WeatherSimulator(grid_size=(50, 50))
        assert sim.nx == 50
        assert sim.ny == 50
        assert sim.rainfall_params is None
        assert sim.wind_params is None

    def test_setup_rainfall(self):
        """Test rainfall configuration."""
        sim = WeatherSimulator(grid_size=(50, 50))
        sim.setup_rainfall(
            intensity_mm_hr=25.0, duration_hours=12.0, distribution="uniform"
        )

        assert sim.rainfall_params.intensity_mm_hr == 25.0
        assert sim.rainfall_params.duration_hours == 12.0
        assert sim.rainfall_params.distribution == RainfallDistributionType.UNIFORM

    def test_setup_wind(self):
        """Test wind configuration."""
        sim = WeatherSimulator(grid_size=(50, 50))
        sim.setup_wind(speed_ms=10.0, direction_degrees=45.0, pattern="uniform")

        assert sim.wind_params.speed_ms == 10.0
        assert sim.wind_params.direction_degrees == 45.0
        assert sim.wind_params.pattern == WindPatternType.UNIFORM

    def test_uniform_rainfall_field(self):
        """Test uniform rainfall field generation."""
        sim = WeatherSimulator(grid_size=(50, 50))
        sim.setup_rainfall(intensity_mm_hr=10.0, distribution="uniform")

        field = sim.get_rainfall_field(time_hours=0)
        assert field.shape == (50, 50)
        assert np.all(field >= 0)
        assert np.abs(np.mean(field) - 10.0) < 1.0  # Approximately 10 mm/hr

    def test_storm_cell_rainfall_field(self):
        """Test storm cell rainfall field."""
        sim = WeatherSimulator(grid_size=(100, 100))
        sim.setup_rainfall(
            intensity_mm_hr=20.0,
            distribution="storm_cell",
            storm_center=(0.5, 0.5),
            storm_radius=0.2,
        )

        field = sim.get_rainfall_field(time_hours=0)
        assert field.shape == (100, 100)

        # Center should have higher intensity
        center = field[50, 50]
        edge = field[0, 0]
        assert center > edge

    def test_uniform_wind_field(self):
        """Test uniform wind field."""
        sim = WeatherSimulator(grid_size=(50, 50))
        sim.setup_wind(speed_ms=5.0, direction_degrees=0.0)

        u, v = sim.get_wind_field()
        assert u.shape == (50, 50)
        assert v.shape == (50, 50)

        # North wind should have positive v component
        assert np.mean(v) > 0

    def test_wind_field_patterns(self):
        """Test different wind patterns."""
        sim = WeatherSimulator(grid_size=(50, 50))
        sim.setup_wind(speed_ms=5.0, pattern="rotational")

        u, v = sim.get_wind_field()
        speed = np.sqrt(u**2 + v**2)
        assert np.all(speed >= 0)

    def test_temporal_patterns(self):
        """Test temporal rainfall patterns."""
        sim = WeatherSimulator(grid_size=(50, 50))
        sim.setup_rainfall(
            intensity_mm_hr=10.0, duration_hours=24.0, temporal_pattern="peak"
        )

        # Start should be low
        field_start = sim.get_rainfall_field(time_hours=0)
        # Middle should be high
        field_mid = sim.get_rainfall_field(time_hours=12)
        # End should be low
        field_end = sim.get_rainfall_field(time_hours=24)

        assert np.mean(field_mid) > np.mean(field_start)
        assert np.mean(field_mid) > np.mean(field_end)

    def test_cumulative_rainfall(self):
        """Test cumulative rainfall calculation."""
        sim = WeatherSimulator(grid_size=(50, 50))
        sim.setup_rainfall(intensity_mm_hr=10.0, duration_hours=6.0)

        cumulative = sim.get_cumulative_rainfall(time_hours=6.0)
        assert cumulative.shape == (50, 50)
        assert np.all(cumulative >= 0)
        # Approximately 60mm total (10 mm/hr * 6 hr)
        assert 50 < np.mean(cumulative) < 70

    def test_step_simulation(self):
        """Test simulation stepping."""
        sim = WeatherSimulator(grid_size=(50, 50))
        sim.setup_rainfall(intensity_mm_hr=10.0)

        initial_time = sim.current_time
        sim.step(dt_hours=0.5)

        assert sim.current_time == initial_time + 0.5
        assert len(sim.weather_history) == 1

    def test_weather_state_to_dict(self):
        """Test WeatherState conversion to dict."""
        state = WeatherState(
            time_hours=1.0,
            rainfall_intensity=10.0,
            wind_speed=5.0,
            wind_direction=90.0,
            cumulative_rainfall=10.0,
        )

        data = state.to_dict()
        assert data["time_hours"] == 1.0
        assert data["rainfall_intensity"] == 10.0
        assert data["wind_speed"] == 5.0

    def test_export_weather_data(self):
        """Test weather data export."""
        sim = WeatherSimulator(grid_size=(50, 50))
        sim.setup_rainfall(intensity_mm_hr=10.0)
        sim.setup_wind(speed_ms=5.0)
        sim.step(dt_hours=1.0)

        data = sim.export_weather_data()
        assert "grid_size" in data
        assert "rainfall" in data
        assert "wind" in data
        assert "history" in data

    def test_invalid_distribution(self):
        """Test handling of invalid distribution type."""
        sim = WeatherSimulator(grid_size=(50, 50))
        sim.setup_rainfall(intensity_mm_hr=10.0, distribution="invalid")

        # Should fall back to uniform
        assert sim.rainfall_params.distribution == RainfallDistributionType.UNIFORM

    def test_runoff_coefficient(self):
        """Test runoff coefficient calculation."""
        sim = WeatherSimulator(grid_size=(10, 10))

        # Create simple land use array
        land_use = np.zeros((10, 10), dtype=int)
        land_use[0:5, :] = 1  # Urban
        land_use[5:, :] = 2  # Forest

        coeff = sim.get_runoff_coefficient(land_use)

        # Urban should have higher runoff
        assert np.mean(coeff[0:5, :]) > np.mean(coeff[5:, :])
        assert np.all((coeff >= 0) & (coeff <= 1))


class TestRainfallParameters:
    """Test RainfallParameters dataclass."""

    def test_defaults(self):
        """Test default parameter values."""
        params = RainfallParameters()
        assert params.intensity_mm_hr == 10.0
        assert params.distribution == RainfallDistributionType.UNIFORM

    def test_custom_values(self):
        """Test custom parameter values."""
        params = RainfallParameters(
            intensity_mm_hr=50.0,
            duration_hours=6.0,
            distribution=RainfallDistributionType.STORM_CELL,
        )
        assert params.intensity_mm_hr == 50.0
        assert params.duration_hours == 6.0


class TestWindParameters:
    """Test WindParameters dataclass."""

    def test_defaults(self):
        """Test default parameter values."""
        params = WindParameters()
        assert params.speed_ms == 5.0
        assert params.direction_degrees == 0.0
        assert params.pattern == WindPatternType.UNIFORM

    def test_custom_values(self):
        """Test custom parameter values."""
        params = WindParameters(
            speed_ms=15.0, direction_degrees=270.0, pattern=WindPatternType.TURBULENT
        )
        assert params.speed_ms == 15.0
        assert params.direction_degrees == 270.0
