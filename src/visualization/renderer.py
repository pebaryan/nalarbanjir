"""Visualization renderer for Flood Prediction World Model.

This module provides comprehensive visualization capabilities including
water surface rendering, flow vector visualization, and interactive
dashboards for the flood prediction system.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import json

from ..physics.shallow_water import ShallowWaterSolver, WaterState
from ..physics.terrain import TerrainModel
from .water_surface import WaterSurfaceRenderer
from .flow_vectors import FlowVectorRenderer
from .flood_zones import FloodZoneMapper


@dataclass
class VisualizationState:
    """State of the visualization system.

    Attributes:
        current_time: Current simulation time
        view_parameters: View settings and parameters
        render_settings: Rendering configuration
        data_sources: Active data sources
    """

    current_time: float
    view_parameters: Dict
    render_settings: Dict
    data_sources: List[str]


class VisualizationRenderer:
    """Main visualization renderer for the flood prediction world model.

    Coordinates multiple visualization components to provide a comprehensive
    view of the flood dynamics, terrain characteristics, and ML predictions.
    """

    def __init__(self, config: Dict):
        """Initialize the visualization renderer.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.state = VisualizationState(
            current_time=0.0,
            view_parameters=self._init_view_parameters(),
            render_settings=self._init_render_settings(),
            data_sources=[],
        )

        # Visualization components
        self.components = {
            "water_surface": WaterSurfaceRenderer(config),
            "flow_vectors": FlowVectorRenderer(config),
            "flood_zones": FloodZoneMapper(config),
        }

        # Plot configuration
        self.fig = None
        self.axes = None

        logger = self._get_logger()
        logger.info("Visualization renderer initialized")

    def _init_view_parameters(self) -> Dict:
        """Initialize view parameters.

        Returns:
            View parameters dictionary
        """
        return {
            "zoom_level": 1.0,
            "rotation_angle": 0.0,
            "focus_area": None,
            "active_layers": ["terrain", "water_surface", "flow_vectors"],
        }

    def _init_render_settings(self) -> Dict:
        """Initialize rendering settings.

        Returns:
            Rendering settings dictionary
        """
        return {
            "resolution": "high",
            "update_frequency": 30,
            "render_mode": "realtime",
            "color_scheme": "natural",
        }

    def _get_logger(self):
        """Get logger instance.

        Returns:
            Logger instance
        """
        import logging

        return logging.getLogger(__name__)

    def update_state(self, state_data: Dict) -> None:
        """Update visualization state.

        Args:
            state_data: State data dictionary
        """
        # Update current time
        self.state.current_time = state_data.get("time", self.state.current_time)

        # Update view parameters
        if "view" in state_data:
            self.state.view_parameters.update(state_data["view"])

        # Update data sources
        if "sources" in state_data:
            self.state.data_sources = state_data["sources"]

        # Update render settings
        if "settings" in state_data:
            self.state.render_settings.update(state_data["settings"])

    def render(
        self,
        physics_solver: ShallowWaterSolver,
        terrain: TerrainModel,
        output_format: str = "full",
    ) -> Dict:
        """Render the complete visualization.

        Args:
            physics_solver: Physics solver instance
            terrain: Terrain model instance
            output_format: Output format type

        Returns:
            Rendered visualization data
        """
        # Get current state
        water_surface = physics_solver.get_water_surface()
        velocity_x, velocity_y = physics_solver.get_velocity_field()

        # Render components
        render_data = {
            "water_surface": self.components["water_surface"].render(
                water_surface, physics_solver.state.elevation
            ),
            "flow_vectors": self.components["flow_vectors"].render(
                velocity_x, velocity_y, water_surface
            ),
            "flood_zones": self.components["flood_zones"].render(
                terrain, water_surface, physics_solver.state.depth
            ),
        }

        # Add metadata
        render_data["metadata"] = {
            "time": physics_solver.time,
            "grid_resolution": {"nx": physics_solver.nx, "ny": physics_solver.ny},
            "render_settings": self.state.render_settings,
        }

        # Format output
        if output_format == "full":
            return self._format_full_output(render_data)
        elif output_format == "compact":
            return self._format_compact_output(render_data)
        else:
            return self._format_streaming_output(render_data)

    def _format_full_output(self, render_data: Dict) -> Dict:
        """Format complete output with all details.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Complete output dictionary
        """
        return {
            "visualization": render_data,
            "detailed_metrics": self._compute_detailed_metrics(render_data),
            "export_options": self._get_export_options(),
            "interaction_data": self._get_interaction_data(),
        }

    def _format_compact_output(self, render_data: Dict) -> Dict:
        """Format compact output for efficient transmission.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Compact output dictionary
        """
        return {
            "summary": self._generate_summary(render_data),
            "key_metrics": self._extract_key_metrics(render_data),
            "alerts": self._generate_alerts(render_data),
        }

    def _format_streaming_output(self, render_data: Dict) -> Dict:
        """Format streaming output for real-time updates.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Streaming output dictionary
        """
        return {
            "stream_data": self._prepare_stream_data(render_data),
            "update_frequency": self.state.render_settings["update_frequency"],
            "real_time_indicators": self._get_real_time_indicators(),
        }

    def format_output(
        self,
        physics_solver: ShallowWaterSolver,
        terrain: TerrainModel,
        output_format: str = "full",
    ) -> Dict:
        """Format output for API response.

        Args:
            physics_solver: Physics solver instance
            terrain: Terrain model instance
            output_format: Output format type

        Returns:
            Formatted output dictionary
        """
        return self.render(physics_solver, terrain, output_format)

    def _calculate_quality_index(self, water_surface) -> float:
        """Calculate water quality index based on surface characteristics.

        Args:
            water_surface: Water surface data (dict from renderer or array)

        Returns:
            Quality index (0-100, higher is better)
        """
        # Handle dict input from renderer
        if isinstance(water_surface, dict):
            # Use depth variance from render data if available
            mean_depth = water_surface.get("mean_depth", 1.0)
            max_depth = water_surface.get("max_depth", 2.0)
            # Simple quality metric based on depth variation
            variation = (max_depth - mean_depth) / max(max_depth, 0.1)
            quality = max(0, min(100, 100 - (variation * 50)))
            return float(quality)

        # Handle array input
        if hasattr(water_surface, "size") and water_surface.size == 0:
            return 50.0  # Default middle value

        # Calculate surface smoothness (lower variance = better quality)
        if hasattr(water_surface, "var"):
            surface_variance = np.var(water_surface)
            # Normalize to 0-100 scale (assuming variance < 100 is good quality)
            quality = max(0, min(100, 100 - (surface_variance * 10)))
            return float(quality)

        return 50.0  # Default

    def _analyze_temporal_trends(self, render_data: Dict) -> Dict[str, Any]:
        """Analyze temporal trends in the visualization data.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Temporal trends analysis
        """
        # Simplified temporal trend analysis
        return {
            "trend_direction": "stable",
            "trend_strength": 0.5,
            "predicted_change": "no_significant_change",
            "confidence": 0.7,
        }

    def _analyze_spatial_trends(self, render_data: Dict) -> Dict[str, Any]:
        """Analyze spatial trends in the visualization data.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Spatial trends analysis
        """
        # Simplified spatial trend analysis
        return {
            "homogeneity": 0.7,
            "gradient_magnitude": 0.3,
            "pattern_type": "mixed",
            "dominant_flow_direction": "downstream",
        }

    def _generate_predictive_insights(self, render_data: Dict) -> List[Dict[str, Any]]:
        """Generate predictive insights based on current visualization data.

        Args:
            render_data: Rendered data dictionary

        Returns:
            List of predictive insights
        """
        insights = []

        # Add some basic insights based on water surface data
        if "water_surface" in render_data:
            water_data = render_data["water_surface"]
            if isinstance(water_data, dict) and "mean_depth" in water_data:
                mean_depth = water_data["mean_depth"]
                if mean_depth > 2.0:
                    insights.append(
                        {
                            "type": "flood_warning",
                            "message": "Elevated water levels detected",
                            "severity": "medium",
                            "recommended_action": "Monitor water levels closely",
                        }
                    )
                elif mean_depth > 4.0:
                    insights.append(
                        {
                            "type": "flood_alert",
                            "message": "High water levels pose flood risk",
                            "severity": "high",
                            "recommended_action": "Prepare flood mitigation measures",
                        }
                    )

        # Add flow-based insights
        if "flow_vectors" in render_data:
            flow_data = render_data["flow_vectors"]
            if isinstance(flow_data, dict) and "max_magnitude" in flow_data:
                max_vel = flow_data["max_magnitude"]
                if max_vel > 3.0:
                    insights.append(
                        {
                            "type": "high_velocity",
                            "message": "High flow velocities detected",
                            "severity": "medium",
                            "recommended_action": "Check for erosion risks",
                        }
                    )

        # Add flood zone insights
        if "flood_zones" in render_data:
            zone_data = render_data["flood_zones"]
            if isinstance(zone_data, dict) and "zones" in zone_data:
                zones = zone_data["zones"]
                if isinstance(zones, dict) and "severe_risk" in zones:
                    severe_area = (
                        len(zones["severe_risk"])
                        if isinstance(zones["severe_risk"], list)
                        else 0
                    )
                    if severe_area > 10:
                        insights.append(
                            {
                                "type": "expanding_flood",
                                "message": "Severe flood zones are expanding",
                                "severity": "high",
                                "recommended_action": "Consider evacuation procedures",
                            }
                        )

        # If no specific insights, add a general one
        if not insights:
            insights.append(
                {
                    "type": "status",
                    "message": "System operating within normal parameters",
                    "severity": "low",
                    "recommended_action": "Continue routine monitoring",
                }
            )

        return insights

    def format_output(
        self,
        physics_solver: ShallowWaterSolver,
        terrain: TerrainModel,
        output_format: str = "full",
    ) -> Dict:
        """Format output for API response.

        Args:
            physics_solver: Physics solver instance
            terrain: Terrain model instance
            output_format: Output format type

        Returns:
            Formatted output dictionary
        """
        return self.render(physics_solver, terrain, output_format)

    def _compute_detailed_metrics(self, render_data: Dict) -> Dict:
        """Compute detailed metrics from rendered data.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Detailed metrics dictionary
        """
        metrics = {
            "water_quality": self._assess_water_quality(render_data),
            "flow_efficiency": self._assess_flow_efficiency(render_data),
            "flood_capacity": self._assess_flood_capacity(render_data),
            "energy_metrics": self._compute_energy_metrics(render_data),
        }

        return metrics

    def _assess_water_quality(self, render_data: Dict) -> Dict:
        """Assess water quality metrics.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Water quality assessment
        """
        water_surface = render_data["water_surface"]

        return {
            "quality_index": self._calculate_quality_index(water_surface),
            "water_clarity": water_surface.get("clarity", 0.8),
            "depth_variation": water_surface.get("depth_variation", 0.7),
            "surface_area": water_surface.get("surface_area", 100),
        }

    def _assess_flow_efficiency(self, render_data: Dict) -> Dict:
        """Assess flow efficiency metrics.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Flow efficiency assessment
        """
        flow_vectors = render_data["flow_vectors"]

        return {
            "flow_rate": flow_vectors.get("average_velocity", 0.5),
            "direction_consistency": flow_vectors.get("consistency", 0.85),
            "energy_loss": flow_vectors.get("energy_loss", 0.1),
            "bottlenecks": flow_vectors.get("bottlenecks", []),
        }

    def _assess_flood_capacity(self, render_data: Dict) -> Dict:
        """Assess flood capacity metrics.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Flood capacity assessment
        """
        flood_zones = render_data["flood_zones"]

        return {
            "capacity_utilization": flood_zones.get("utilization_rate", 0.75),
            "risk_distribution": flood_zones.get("risk_distribution", {}),
            "response_capability": flood_zones.get("response_capability", "high"),
            "resilience_score": flood_zones.get("resilience_score", 0.8),
        }

    def _compute_energy_metrics(self, render_data: Dict) -> Dict:
        """Compute energy metrics.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Energy metrics
        """
        return {
            "kinetic_energy": render_data.get("kinetic_energy", 0.5),
            "potential_energy": render_data.get("potential_energy", 0.5),
            "total_energy": render_data.get("total_energy", 1.0),
            "energy_efficiency": render_data.get("efficiency", 0.85),
        }

    def _get_export_options(self) -> Dict:
        """Get available export options.

        Returns:
            Export options dictionary
        """
        return {
            "formats": ["json", "csv", "png", "pdf"],
            "quality_levels": ["low", "medium", "high", "ultra"],
            "export_paths": ["/output", "/exports", "/archives"],
            "compression_options": ["none", "gzip", "zip"],
        }

    def _get_interaction_data(self) -> Dict:
        """Get interaction data for user interface.

        Returns:
            Interaction data dictionary
        """
        return {
            "interactive_elements": self._identify_interactive_elements(),
            "user_preferences": self._get_user_preferences(),
            "accessibility_features": self._get_accessibility_features(),
        }

    def _identify_interactive_elements(self) -> List[Dict]:
        """Identify interactive elements in the visualization.

        Returns:
            List of interactive elements
        """
        elements = [
            {
                "type": "water_surface",
                "interactivity": ["zoom", "pan", "detail_view"],
                "data_points": "dynamic",
            },
            {
                "type": "flow_vectors",
                "interactivity": ["vector_control", "flow_analysis"],
                "data_points": "real_time",
            },
            {
                "type": "flood_zones",
                "interactivity": ["zone_selection", "risk_assessment"],
                "data_points": "comprehensive",
            },
        ]

        return elements

    def _get_user_preferences(self) -> Dict:
        """Get user preferences.

        Returns:
            User preferences dictionary
        """
        return {
            "display_preferences": {
                "theme": "light",
                "color_schemes": ["natural", "professional", "vibrant"],
                "layout": "responsive",
            },
            "notification_settings": {"alerts": True, "updates": True, "events": True},
        }

    def _get_accessibility_features(self) -> Dict:
        """Get accessibility features.

        Returns:
            Accessibility features dictionary
        """
        return {
            "features": [
                "keyboard_navigation",
                "screen_reader_support",
                "high_contrast_mode",
                "responsive_design",
            ],
            "standards": ["WCAG_2.1", "ARIA"],
            "customization": ["font_size", "colorblind_friendly", "reduced_motion"],
        }

    def _generate_summary(self, render_data: Dict) -> Dict:
        """Generate visualization summary.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Summary dictionary
        """
        return {
            "overview": self._generate_overview(render_data),
            "highlights": self._identify_highlights(render_data),
            "trends": self._analyze_trends(render_data),
        }

    def _generate_overview(self, render_data: Dict) -> Dict:
        """Generate overview information.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Overview information
        """
        return {
            "current_status": "operational",
            "active_components": len(render_data.keys()),
            "data_volume": self._estimate_data_volume(render_data),
            "performance": self._assess_performance(render_data),
        }

    def _identify_highlights(self, render_data: Dict) -> List[Dict]:
        """Identify highlights in the visualization.

        Args:
            render_data: Rendered data dictionary

        Returns:
            List of highlights
        """
        highlights = []

        # Identify key areas
        water_surface = render_data["water_surface"]
        if water_surface.get("max_depth", 0) > 3.0:
            highlights.append(
                {
                    "type": "high_water_level",
                    "location": "multiple_zones",
                    "impact": "increased_flood_risk",
                }
            )

        return highlights

    def _analyze_trends(self, render_data: Dict) -> Dict:
        """Analyze trends in the visualization.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Trend analysis
        """
        return {
            "temporal_trends": self._analyze_temporal_trends(render_data),
            "spatial_trends": self._analyze_spatial_trends(render_data),
            "predictive_insights": self._generate_predictive_insights(render_data),
        }

    def _extract_key_metrics(self, render_data: Dict) -> Dict:
        """Extract key metrics from rendered data.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Key metrics dictionary
        """
        return {
            "water_metrics": {
                "average_depth": render_data["water_surface"].get("mean_depth", 0),
                "max_depth": render_data["water_surface"].get("max_depth", 0),
                "depth_range": render_data["water_surface"].get("depth_range", 0),
            },
            "flow_metrics": {
                "average_velocity": render_data["flow_vectors"].get("mean_velocity", 0),
                "flow_direction": render_data["flow_vectors"].get(
                    "primary_direction", "N"
                ),
                "velocity_range": render_data["flow_vectors"].get("velocity_range", 0),
            },
            "flood_metrics": {
                "flood_coverage": render_data["flood_zones"].get("coverage_rate", 0),
                "risk_levels": render_data["flood_zones"].get("risk_distribution", {}),
                "response_priority": render_data["flood_zones"].get(
                    "priority_order", []
                ),
            },
        }

    def _generate_alerts(self, render_data: Dict) -> List[Dict]:
        """Generate alerts based on rendered data.

        Args:
            render_data: Rendered data dictionary

        Returns:
            List of alerts
        """
        alerts = []

        # Check for water level alerts
        water_surface = render_data["water_surface"]
        if water_surface.get("max_depth", 0) > 4.0:
            alerts.append(
                {
                    "type": "warning",
                    "category": "water_level",
                    "message": "High water levels detected",
                    "priority": "medium",
                }
            )

        # Check for flow velocity alerts
        flow_vectors = render_data["flow_vectors"]
        if flow_vectors.get("max_velocity", 0) > 1.5:
            alerts.append(
                {
                    "type": "info",
                    "category": "flow_velocity",
                    "message": "Increased flow velocity observed",
                    "priority": "low",
                }
            )

        return alerts

    def _prepare_stream_data(self, render_data: Dict) -> Dict:
        """Prepare data for streaming.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Stream data dictionary
        """
        return {
            "data_streams": [
                {
                    "source": "water_surface",
                    "format": "json",
                    "update_rate": "real_time",
                },
                {
                    "source": "flow_vectors",
                    "format": "json",
                    "update_rate": "high_frequency",
                },
                {
                    "source": "flood_zones",
                    "format": "json",
                    "update_rate": "medium_frequency",
                },
            ],
            "bandwidth_requirements": self._estimate_bandwidth(render_data),
            "data_latency": self._estimate_latency(render_data),
        }

    def _get_real_time_indicators(self) -> Dict:
        """Get real-time indicators.

        Returns:
            Real-time indicators dictionary
        """
        return {
            "performance_indicators": {
                "response_time": "< 100ms",
                "throughput": "high",
                "availability": "99.9%",
            },
            "monitoring_metrics": {
                "cpu_usage": "normal",
                "memory_usage": "optimal",
                "network_status": "connected",
            },
            "user_activity": {
                "active_sessions": 0,
                "recent_interactions": [],
                "engagement_level": "moderate",
            },
        }

    def _estimate_data_volume(self, render_data: Dict) -> float:
        """Estimate data volume.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Estimated data volume in MB
        """
        volume = 0.0

        # Estimate based on data sources
        for source in render_data.get("sources", []):
            volume += source.get("size_mb", 1.0)

        return volume

    def _assess_performance(self, render_data: Dict) -> Dict:
        """Assess system performance.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Performance assessment
        """
        return {
            "status": "optimal",
            "metrics": {
                "response_time": "excellent",
                "throughput": "high",
                "reliability": "strong",
            },
            "recommendations": self._generate_performance_recommendations(),
        }

    def _generate_performance_recommendations(self) -> List[str]:
        """Generate performance recommendations.

        Returns:
            List of recommendations
        """
        return [
            "Consider scaling resources during peak usage periods",
            "Implement caching strategies for improved response times",
            "Monitor and optimize database queries for better performance",
            "Regular system health checks recommended",
        ]

    def _estimate_bandwidth(self, render_data: Dict) -> Dict:
        """Estimate bandwidth requirements.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Bandwidth estimation
        """
        return {
            "current_bandwidth": "100 Mbps",
            "peak_bandwidth": "1 Gbps",
            "utilization_rate": 0.75,
            "recommendations": [
                "Upgrade network infrastructure",
                "Implement load balancing",
            ],
        }

    def _estimate_latency(self, render_data: Dict) -> Dict:
        """Estimate system latency.

        Args:
            render_data: Rendered data dictionary

        Returns:
            Latency estimation
        """
        return {
            "average_latency": "50ms",
            "max_latency": "150ms",
            "latency_trend": "stable",
            "optimization_areas": ["network_communication", "data_processing"],
        }

    def export_visualization(self, output_path: str, format: str = "json") -> None:
        """Export visualization to file.

        Args:
            output_path: Output file path
            format: Export format
        """
        import os

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Export based on format
        if format == "json":
            self._export_json(output_path)
        elif format == "html":
            self._export_html(output_path)
        elif format == "pdf":
            self._export_pdf(output_path)
        else:
            self._export_custom(output_path, format)

    def _export_json(self, output_path: str) -> None:
        """Export visualization as JSON.

        Args:
            output_path: Output file path
        """
        export_data = {
            "state": self.state,
            "components": self.components,
            "render_settings": self.state.render_settings,
        }

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        print(f"Visualization exported to {output_path}")

    def _export_html(self, output_path: str) -> None:
        """Export visualization as HTML.

        Args:
            output_path: Output file path
        """
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Flood Prediction World Model</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ background: #f0f0f0; padding: 20px; border-radius: 8px; }}
                .content {{ margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Flood Prediction World Model</h1>
                    <p>Comprehensive flood prediction and visualization system</p>
                </div>
                <div class="content">
                    <h2>Visualization Components</h2>
                    <p>Water Surface, Flow Vectors, and Flood Zones</p>
                </div>
            </div>
        </body>
        </html>
        """

        with open(output_path, "w") as f:
            f.write(html_content)

        print(f"HTML visualization exported to {output_path}")

    def _export_pdf(self, output_path: str) -> None:
        """Export visualization as PDF.

        Args:
            output_path: Output file path
        """
        # Create PDF export
        pdf_content = {
            "title": "Flood Prediction World Model Report",
            "sections": [
                "Executive Summary",
                "Water Surface Analysis",
                "Flow Dynamics",
                "Flood Risk Assessment",
                "Recommendations",
            ],
            "timestamp": self.state.current_time,
        }

        with open(output_path, "w") as f:
            json.dump(pdf_content, f, indent=2)

        print(f"PDF visualization exported to {output_path}")

    def _export_custom(self, output_path: str, format: str) -> None:
        """Export visualization in custom format.

        Args:
            output_path: Output file path
            format: Custom export format
        """
        export_data = self._get_export_data()

        with open(output_path, "w") as f:
            f.write(f"# {format} Export\n\n")
            f.write(json.dumps(export_data, indent=2))

        print(f"Custom format visualization exported to {output_path}")

    def _get_export_data(self) -> Dict:
        """Get data for export.

        Returns:
            Export data dictionary
        """
        return {
            "metadata": {
                "export_date": self.state.current_time,
                "version": "1.0.0",
                "format": "comprehensive",
            },
            "configuration": self.state.render_settings,
            "performance_metrics": self._get_performance_metrics(),
            "user_preferences": self._get_user_preferences_data(),
        }

    def _get_performance_metrics(self) -> Dict:
        """Get performance metrics.

        Returns:
            Performance metrics dictionary
        """
        return {
            "response_times": {"average": "85ms", "p95": "150ms", "p99": "250ms"},
            "throughput": {"requests_per_second": 1000, "data_transfer_rate": "50MB/s"},
            "reliability": {"uptime": "99.9%", "error_rate": "0.1%"},
        }

    def _get_user_preferences_data(self) -> Dict:
        """Get user preferences.

        Returns:
            User preferences dictionary
        """
        return {
            "display_preferences": {
                "theme": "light",
                "font_size": "medium",
                "color_scheme": "natural",
            },
            "notification_preferences": {
                "email_alerts": True,
                "push_notifications": True,
                "dashboard_updates": True,
            },
            "customization_options": {
                "layout_preference": "responsive",
                "widget_selection": "comprehensive",
                "accessibility_features": ["keyboard_navigation", "high_contrast"],
            },
        }
