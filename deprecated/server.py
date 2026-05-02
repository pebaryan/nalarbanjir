"""Flood Prediction World Model - Backend Server.

This module provides the FastAPI-based backend server that handles:
- Shallow water wave equation computation
- Machine learning model inference
- Real-time data streaming
- REST API endpoints for frontend communication
"""

import uvicorn
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    UploadFile,
    File,
    Form,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, List, Optional, AsyncGenerator
import asyncio
import json
import logging
import os
import numpy as np
import tempfile
import shutil
import time
import threading
import uuid
from pathlib import Path
import uuid

from .physics.shallow_water import ShallowWaterSolver, WavePropagationAnalyzer
from .physics.terrain import TerrainModel, LandUseType
from .physics.weather import WeatherSimulator
from .physics.flood_physics_3d import FloodPhysicsEngine3D, FloodState
from .ml.model import MLModel, ModelConfig
from .ml.training import TrainingPipeline
from .visualization.renderer import VisualizationRenderer
from .gis.importer import GISImporter, GISImportError
from .gis.mesh_generator import (
    TerrainMeshGenerator,
    WaterSurfaceMeshGenerator,
    generate_terrain_mesh,
    generate_water_mesh,
)
from .gis.tile_manager import TerrainTileManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FloodWorldServer:
    """Main server class for the Flood Prediction World Model.

    Coordinates the physics engine, ML models, and visualization components
    to provide a comprehensive flood prediction system.
    """

    def __init__(self, config_path: str):
        """Initialize the flood world server.

        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.app = FastAPI(
            title="Flood Prediction World Model",
            description="A comprehensive world model for flood prediction based on shallow water wave equations",
            version="1.0.0",
        )

        # Initialize components
        self.physics_solver = ShallowWaterSolver(
            config=self.config["physics"],
            grid_resolution=(self.config["grid"]["nx"], self.config["grid"]["ny"]),
        )

        self.terrain = TerrainModel(
            config=self.config["terrain"],
            resolution=(self.config["grid"]["nx"], self.config["grid"]["ny"]),
        )

        self.ml_model = MLModel(config=ModelConfig.from_dict(self.config["ml"]))

        self.renderer = VisualizationRenderer(config=self.config["visualization"])

        # Initialize API routes
        self._setup_routes()

        # WebSocket manager
        self.websocket_manager = WebSocketManager()

        # Storage for uploaded GIS files and generated meshes
        self._gis_storage: Dict[str, Dict] = {}
        self._mesh_storage: Dict[str, Dict] = {}
        self._upload_dir = Path(tempfile.gettempdir()) / "flood_prediction_uploads"
        self._upload_dir.mkdir(exist_ok=True)

        # Initialize GIS components
        self.gis_importer = GISImporter()
        self.terrain_mesh_gen = TerrainMeshGenerator()
        self.water_mesh_gen = None  # Will be initialized when bounds are available

        # Initialize tile manager for large DTM streaming
        self.tile_manager = TerrainTileManager(max_tile_pixels=200, max_cache_size=50)
        self._tiled_dtms: Dict[str, List[str]] = {}  # file_id -> list of tile_ids

        # Async tiling progress tracking
        self._tiling_tasks: Dict[str, Dict] = {}  # task_id -> progress info
        self._tiling_thread = None

        # Initialize weather and flood physics (Phases 6 & 7)
        self.weather_sim = None
        self.flood_engine = None
        self.current_flood_state = None

        logger.info("Flood World Server initialized")

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration dictionary
        """
        import yaml

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        return config

    def _setup_routes(self):
        """Set up API routes and WebSocket endpoints."""
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Mount static files
        static_dir = Path(__file__).parent.parent / "frontend" / "static"
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        # API routes
        self.app.add_api_route("/api/simulate", self.simulate, methods=["POST"])
        self.app.add_api_route("/api/state", self.get_state, methods=["GET"])
        self.app.add_api_route("/api/terrain", self.get_terrain_data, methods=["GET"])
        self.app.add_api_route("/api/predict", self.make_predictions, methods=["POST"])
        self.app.add_api_route("/api/history", self.get_history, methods=["GET"])

        # GIS routes
        self.app.add_api_route(
            "/api/gis/upload", self.upload_gis_file, methods=["POST"]
        )
        self.app.add_api_route(
            "/api/gis/mesh/{mesh_id}", self.get_mesh_data, methods=["GET"]
        )
        self.app.add_api_route(
            "/api/gis/generate_terrain_mesh",
            self.generate_terrain_mesh_endpoint,
            methods=["POST"],
        )

        # Tile streaming routes for large DTM handling
        self.app.add_api_route(
            "/api/gis/tile-dtm",
            self.tile_dtm_endpoint,
            methods=["POST"],
        )
        self.app.add_api_route(
            "/api/gis/tile/{tile_id}",
            self.get_tile_endpoint,
            methods=["GET"],
        )
        self.app.add_api_route(
            "/api/gis/visible-tiles",
            self.get_visible_tiles_endpoint,
            methods=["POST"],
        )
        self.app.add_api_route(
            "/api/gis/files",
            self.list_uploaded_files,
            methods=["GET"],
        )

        # Async tiling routes
        self.app.add_api_route(
            "/api/gis/tile-async",
            self.start_async_tiling,
            methods=["POST"],
        )
        self.app.add_api_route(
            "/api/gis/tiling-progress/{task_id}",
            self.get_tiling_progress,
            methods=["GET"],
        )
        self.app.add_api_route(
            "/api/gis/tiling-cancel/{task_id}",
            self.cancel_tiling_task,
            methods=["POST"],
        )

        # Weather routes (Phase 6)
        self.app.add_api_route(
            "/api/weather/configure",
            self.configure_weather,
            methods=["POST"],
        )
        self.app.add_api_route(
            "/api/weather/rainfall",
            self.get_rainfall_field,
            methods=["GET"],
        )
        self.app.add_api_route(
            "/api/weather/wind",
            self.get_wind_field,
            methods=["GET"],
        )
        self.app.add_api_route(
            "/api/weather/cumulative",
            self.get_cumulative_rainfall,
            methods=["GET"],
        )

        # Flood physics routes (Phase 7)
        self.app.add_api_route(
            "/api/flood/initialize",
            self.initialize_flood_simulation,
            methods=["POST"],
        )
        self.app.add_api_route(
            "/api/flood/step",
            self.step_flood_simulation,
            methods=["POST"],
        )
        self.app.add_api_route(
            "/api/flood/state",
            self.get_flood_state,
            methods=["GET"],
        )
        self.app.add_api_route(
            "/api/flood/add-source",
            self.add_flood_source,
            methods=["POST"],
        )
        self.app.add_api_route(
            "/api/flood/run",
            self.run_flood_simulation,
            methods=["POST"],
        )

        # WebSocket endpoint
        self.app.add_websocket_route("/ws", self.websocket_endpoint)

        # Health check
        self.app.add_api_route("/health", self.health_check, methods=["GET"])

        # Frontend interface
        self.app.add_api_route("/", self.frontend_interface, methods=["GET"])

    async def simulate(self, params: Dict):
        """Execute simulation with provided parameters.

        Args:
            params: Simulation parameters

        Returns:
            Simulation results
        """
        try:
            # Extract parameters
            steps = params.get("steps", 100)
            output_format = params.get("output_format", "full")

            # Run simulation
            states = self.physics_solver.evolve(steps=steps)

            # Analyze results
            analyzer = WavePropagationAnalyzer(self.physics_solver)
            wave_analysis = analyzer.analyze_wave_propagation(states[-1])

            # Identify flood zones
            flood_zones = self.terrain.get_flood_zones(self.physics_solver.state.depth)

            # Prepare response
            result = {
                "status": "success",
                "simulation": {
                    "total_steps": steps,
                    "final_time": self.physics_solver.state.time,
                    "wave_propagation": wave_analysis,
                },
                "flood_zones": flood_zones,
                "output": self.renderer.format_output(
                    self.physics_solver, self.terrain, output_format
                ),
            }

            return JSONResponse(content=result)
        except Exception as e:
            logger.error(f"Simulation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_state(self) -> JSONResponse:
        """Get current system state.

        Returns:
            Current system state
        """
        state = {
            "physics": self.physics_solver.export_state(),
            "terrain": self.terrain.export_terrain_data(),
            "ml": self.ml_model.get_model_state(),
        }

        return JSONResponse(content=state)

    async def get_terrain_data(self) -> JSONResponse:
        """Get terrain data for visualization.

        Returns:
            Terrain data including elevation, land use, and flood zones
        """
        # Get current water depth
        water_depth = self.physics_solver.state.depth

        # Identify flood zones
        flood_zones = self.terrain.get_flood_zones(water_depth)

        # Extract key metrics
        metrics = {
            "total_area": self.physics_solver.nx * self.physics_solver.ny,
            "mean_depth": float(self.physics_solver.state.depth.mean()),
            "max_depth": float(self.physics_solver.state.depth.max()),
            "flood_risk": self.physics_solver.compute_flood_risk().tolist(),
        }

        return JSONResponse(
            content={
                "terrain": self.terrain.export_terrain_data(),
                "flood_zones": flood_zones,
                "metrics": metrics,
            }
        )

    async def make_predictions(self, input_data: Dict) -> JSONResponse:
        """Make predictions using ML model.

        Args:
            input_data: Input data for prediction

        Returns:
            ML predictions and recommendations
        """
        try:
            # Prepare input
            prediction_type = input_data.get("prediction_type", "flood_risk")
            forecast_horizon = input_data.get("forecast_horizon", 24)

            # Make prediction
            predictions = self.ml_model.predict(
                prediction_type=prediction_type, horizon=forecast_horizon
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(predictions)

            return JSONResponse(
                content={
                    "predictions": predictions,
                    "recommendations": recommendations,
                    "confidence": self.ml_model.get_prediction_confidence(),
                }
            )

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def _generate_recommendations(self, predictions: Dict) -> List[Dict]:
        """Generate actionable recommendations based on predictions.

        Args:
            predictions: ML prediction results

        Returns:
            List of recommendations
        """
        recommendations = []

        # Analyze flood risk predictions
        if "flood_risk" in predictions:
            risk_levels = predictions["flood_risk"]

            if risk_levels.get("severe_risk", 0) > 0.3:
                recommendations.append(
                    {
                        "type": "flood_mitigation",
                        "priority": "high",
                        "action": "Activate emergency flood response protocols",
                        "details": "High-risk zones require immediate attention",
                    }
                )

        # Analyze flow dynamics
        if "flow_dynamics" in predictions:
            flow_patterns = predictions["flow_dynamics"]

            if flow_patterns.get("high_velocity", 0) > 0.5:
                recommendations.append(
                    {
                        "type": "flow_optimization",
                        "priority": "medium",
                        "action": "Optimize flow channels and drainage systems",
                        "details": "High velocity areas may benefit from flow regulation",
                    }
                )

        return recommendations

    async def get_history(self) -> JSONResponse:
        """Get historical simulation data.

        Returns:
            Historical data and trends
        """
        # Get historical trends
        history = {
            "trends": self._analyze_trends(),
            "events": self._get_recent_events(),
            "statistics": self._compute_statistics(),
        }

        return JSONResponse(content=history)

    def _analyze_trends(self) -> Dict:
        """Analyze simulation trends.

        Returns:
            Trend analysis results
        """
        return {
            "water_level_trend": "stable"
            if self.physics_solver.state.depth.mean() > 1.0
            else "rising",
            "flow_pattern": "laminar"
            if self.physics_solver.state.velocity_x.mean() < 0.5
            else "turbulent",
            "flood_risk_trend": self._assess_flood_risk_trend(),
        }

    def _get_recent_events(self) -> List[Dict]:
        """Get recent simulation events.

        Returns:
            List of recent events
        """
        events = []

        # Simulated events based on current state
        if self.physics_solver.state.depth.max() > 3.0:
            events.append(
                {
                    "type": "flood_alert",
                    "timestamp": self.physics_solver.time,
                    "message": "High water levels detected in multiple zones",
                }
            )

        return events

    def _compute_statistics(self) -> Dict:
        """Compute simulation statistics.

        Returns:
            Computed statistics
        """
        depth = self.physics_solver.state.depth

        return {
            "depth_statistics": {
                "mean": float(depth.mean()),
                "std": float(depth.std()),
                "min": float(depth.min()),
                "max": float(depth.max()),
            },
            "velocity_statistics": {
                "mean_x": float(self.physics_solver.state.velocity_x.mean()),
                "mean_y": float(self.physics_solver.state.velocity_y.mean()),
                "max_x": float(self.physics_solver.state.velocity_x.max()),
                "max_y": float(self.physics_solver.state.velocity_y.max()),
            },
        }

    def _assess_flood_risk_trend(self) -> str:
        """Assess flood risk trend.

        Returns:
            Risk trend description
        """
        risk = self.physics_solver.compute_flood_risk()

        if risk.mean() > 1.5:
            return "increasing"
        elif risk.mean() < 1.0:
            return "decreasing"
        else:
            return "stable"

    async def websocket_endpoint(self, websocket: WebSocket):
        """Handle WebSocket connections for real-time communication.

        Args:
            websocket: WebSocket connection
        """
        await self.websocket_manager.connect(websocket)

        try:
            while True:
                # Receive data from client
                data = await websocket.receive_json()

                # Process message
                if data["type"] == "simulation_control":
                    await self._handle_simulation_control(data)
                elif data["type"] == "visualization_update":
                    await self._handle_visualization_update(data)
                elif data["type"] == "ml_request":
                    await self._handle_ml_request(data)

                # Send response
                response = {
                    "type": "acknowledgment",
                    "timestamp": self.physics_solver.time,
                    "status": "success",
                }

                await websocket.send_json(response)

        except WebSocketDisconnect:
            logger.info("WebSocket connection closed")
            self.websocket_manager.disconnect(websocket)

    async def _handle_simulation_control(self, data: Dict) -> None:
        """Handle simulation control commands.

        Args:
            data: Control command data
        """
        command = data.get("command")

        if command == "start":
            logger.info("Starting simulation")
            self.physics_solver.time = 0.0
        elif command == "pause":
            logger.info("Pausing simulation")
        elif command == "resume":
            logger.info("Resuming simulation")
        elif command == "reset":
            logger.info("Resetting simulation")
            self.physics_solver = ShallowWaterSolver(
                config=self.config["physics"],
                grid_resolution=(self.config["grid"]["nx"], self.config["grid"]["ny"]),
            )

    async def _handle_visualization_update(self, data: Dict) -> None:
        """Handle visualization updates.

        Args:
            data: Visualization update data
        """
        update_type = data.get("update_type")

        if update_type == "render":
            # Trigger visualization refresh
            await self._refresh_visualization(data.get("params", {}))
        elif update_type == "export":
            # Export visualization data
            await self._export_visualization(data.get("params", {}))

    async def _handle_ml_request(self, data: Dict) -> None:
        """Handle ML model requests.

        Args:
            data: ML request data
        """
        request_type = data.get("request_type")

        if request_type == "predict":
            # Make prediction request
            predictions = await self.make_predictions(data.get("input", {}))
            await self.websocket_manager.send_message(
                data["websocket"], predictions.json()
            )
        elif request_type == "train":
            # Initiate training
            await self._initiate_training(data.get("params", {}))

    async def _refresh_visualization(self, params: Dict) -> None:
        """Refresh visualization with current state.

        Args:
            params: Visualization parameters
        """
        # Get current visualization state
        state = await self.get_state()

        # Update renderer
        self.renderer.update_state(state)

    async def _export_visualization(self, params: Dict) -> None:
        """Export visualization data.

        Args:
            params: Export parameters
        """
        export_path = params.get("path", "output/export.json")

        # Export to file
        state = await self.get_state()

        with open(export_path, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"Visualization exported to {export_path}")

    async def _initiate_training(self, params: Dict) -> None:
        """Initiate ML model training.

        Args:
            params: Training parameters
        """
        training_config = {
            "epochs": params.get("epochs", 100),
            "batch_size": params.get("batch_size", 32),
            "learning_rate": params.get("learning_rate", 1e-3),
        }

        # Start training
        pipeline = TrainingPipeline(self.ml_model, training_config)
        results = await pipeline.train()

        logger.info(f"Training completed: {results}")

    async def health_check(self) -> JSONResponse:
        """Perform health check.

        Returns:
            Health status
        """
        health = {
            "status": "healthy",
            "timestamp": self.physics_solver.time,
            "components": {
                "physics_engine": "operational",
                "ml_model": "operational",
                "visualization": "operational",
                "data_pipeline": "operational",
            },
        }

        # Check component health
        try:
            # Test physics solver
            self.physics_solver.get_water_surface()
        except Exception as e:
            health["components"]["physics_engine"] = f"unhealthy: {str(e)}"

        return JSONResponse(content=health)

    async def frontend_interface(self) -> HTMLResponse:
        """Serve the frontend web interface.

        Returns:
            HTML response with web interface
        """
        template_path = (
            Path(__file__).parent.parent / "frontend" / "templates" / "index.html"
        )

        with open(template_path, "r") as f:
            template = f.read()

        return HTMLResponse(content=template)

    async def upload_gis_file(
        self,
        file: UploadFile = File(...),
        target_crs: Optional[int] = Form(None),
    ) -> JSONResponse:
        """Upload and process a GIS file.

        Args:
            file: Uploaded GIS file (GeoTIFF, Shapefile, GeoJSON)
            target_crs: Optional target CRS for reprojection

        Returns:
            File metadata and processing results
        """
        try:
            # Generate unique ID for this upload
            file_id = str(uuid.uuid4())

            # Save uploaded file temporarily
            file_ext = Path(file.filename).suffix.lower()
            temp_path = self._upload_dir / f"{file_id}{file_ext}"

            with open(temp_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

            # Process based on file type
            if file_ext in [".tif", ".tiff", ".asc"]:
                # Import raster data (DTM)
                dtm = self.gis_importer.import_raster(
                    filepath=temp_path,
                    target_crs=target_crs,
                )

                result = {
                    "file_id": file_id,
                    "filename": file.filename,
                    "type": "raster",
                    "format": file_ext,
                    "bounds": {
                        "min_x": dtm.bounds.min_x,
                        "min_y": dtm.bounds.min_y,
                        "max_x": dtm.bounds.max_x,
                        "max_y": dtm.bounds.max_y,
                    },
                    "crs": dtm.crs.epsg_code
                    if hasattr(dtm.crs, "epsg_code")
                    else dtm.crs,
                    "resolution": dtm.resolution,
                    "dimensions": {
                        "width": dtm.width,
                        "height": dtm.height,
                    },
                    "elevation_stats": {
                        "min": float(dtm.elevation_data.min()),
                        "max": float(dtm.elevation_data.max()),
                        "mean": float(dtm.elevation_data.mean()),
                        "std": float(dtm.elevation_data.std()),
                    },
                }

                # Store DTM for later use
                self._gis_storage[file_id] = {
                    "type": "dtm",
                    "data": dtm,
                    "filename": file.filename,
                }

            elif file_ext in [".shp", ".geojson", ".json", ".gpkg"]:
                # Import vector data
                vector_data = self.gis_importer.import_vector(
                    filepath=temp_path,
                    target_crs=target_crs,
                )

                result = {
                    "file_id": file_id,
                    "filename": file.filename,
                    "type": "vector",
                    "format": file_ext,
                    "feature_count": vector_data.feature_count,
                    "crs": vector_data.crs
                    if isinstance(vector_data.crs, int)
                    else getattr(vector_data.crs, "epsg_code", None),
                    "geometry_types": vector_data.geometry_types,
                    "attributes": list(vector_data.geodataframe.columns)[:10]
                    if hasattr(vector_data, "geodataframe")
                    else [],
                }

                # Store vector data
                self._gis_storage[file_id] = {
                    "type": "vector",
                    "data": vector_data,
                    "filename": file.filename,
                }

            else:
                raise HTTPException(
                    status_code=400, detail=f"Unsupported file format: {file_ext}"
                )

            logger.info(f"Successfully uploaded and processed {file.filename}")
            return JSONResponse(content=result)

        except GISImportError as e:
            logger.error(f"GIS import error: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Upload error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_mesh_data(self, mesh_id: str) -> JSONResponse:
        """Get mesh data by ID.

        Args:
            mesh_id: Unique mesh identifier

        Returns:
            Mesh data in Three.js compatible format
        """
        try:
            if mesh_id not in self._mesh_storage:
                raise HTTPException(
                    status_code=404, detail=f"Mesh not found: {mesh_id}"
                )

            mesh_info = self._mesh_storage[mesh_id]
            mesh_data = mesh_info["data"]

            # Return in Three.js BufferGeometry format
            result = {
                "mesh_id": mesh_id,
                "type": mesh_info["type"],
                "threejs_geometry": mesh_data.to_threejs_buffergeometry(),
                "metadata": {
                    "vertex_count": len(mesh_data.vertices)
                    if mesh_data.vertices is not None
                    else 0,
                    "face_count": len(mesh_data.faces)
                    if mesh_data.faces is not None
                    else 0,
                    "has_normals": mesh_data.normals is not None,
                    "has_uvs": mesh_data.uvs is not None,
                    "has_vertex_colors": mesh_data.colors is not None,
                },
            }

            return JSONResponse(content=result)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving mesh: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def generate_terrain_mesh_endpoint(self, params: Dict) -> JSONResponse:
        """Generate terrain mesh from uploaded DTM.

        Args:
            params: Generation parameters including:
                - file_id: ID of uploaded DTM file
                - lod_level: Level of detail (1-5, default 3)
                - simplification: Simplification ratio (0.0-1.0)

        Returns:
            Generated mesh ID and metadata
        """
        try:
            file_id = params.get("file_id")
            if not file_id or file_id not in self._gis_storage:
                raise HTTPException(
                    status_code=400, detail="Invalid or missing file_id"
                )

            stored_data = self._gis_storage[file_id]
            if stored_data["type"] != "dtm":
                raise HTTPException(status_code=400, detail="File is not a raster DTM")

            dtm = stored_data["data"]

            # Check file size - for large files, use proxy + async tiling
            total_pixels = dtm.width * dtm.height
            MAX_PIXELS = 500000  # Threshold for proxy tiles

            if total_pixels > MAX_PIXELS:
                logger.info(
                    f"Large DTM detected ({total_pixels:,} pixels), using proxy + async tiling"
                )

                # Step 1: Generate a quick proxy mesh (1% resolution) for immediate display
                proxy_simplification = 0.01  # 1% for instant load
                proxy_mesh = generate_terrain_mesh(
                    dtm=dtm,
                    simplification=proxy_simplification,
                    z_scale=1.0,
                )

                # Store proxy mesh
                proxy_mesh_id = str(uuid.uuid4())
                self._mesh_storage[proxy_mesh_id] = {
                    "type": "terrain",
                    "data": proxy_mesh,
                    "source_file": file_id,
                    "params": {**params, "is_proxy": True},
                }

                # Step 2: Start async tiling in background
                estimated_tiles = max(1, (dtm.width * dtm.height) // 40000)
                task_id = str(uuid.uuid4())

                self._tiling_tasks[task_id] = {
                    "file_id": file_id,
                    "status": "starting",
                    "progress": 0,
                    "total_tiles": estimated_tiles,
                    "completed_tiles": 0,
                    "message": "Initializing tiling process...",
                    "tile_ids": [],
                    "started_at": time.time(),
                }

                # Start background tiling thread
                def do_async_tiling():
                    try:
                        self._tiling_tasks[task_id]["status"] = "processing"
                        self._tiling_tasks[task_id]["message"] = "Creating tiles..."

                        tile_ids = self.tile_manager.create_tiles_from_dtm(dtm)
                        self._tiled_dtms[file_id] = tile_ids

                        self._tiling_tasks[task_id].update(
                            {
                                "status": "completed",
                                "progress": 100,
                                "completed_tiles": len(tile_ids),
                                "total_tiles": len(tile_ids),
                                "tile_ids": tile_ids,
                                "message": f"Tiling complete! Created {len(tile_ids)} tiles",
                                "completed_at": time.time(),
                            }
                        )

                        logger.info(
                            f"Async tiling complete for {file_id}: {len(tile_ids)} tiles"
                        )
                    except Exception as e:
                        logger.error(f"Async tiling error: {e}")
                        self._tiling_tasks[task_id].update(
                            {"status": "error", "message": str(e)}
                        )

                thread = threading.Thread(target=do_async_tiling)
                thread.daemon = True
                thread.start()

                logger.info(f"Started async tiling task {task_id} for {file_id}")

                # Return immediately with proxy mesh info
                return JSONResponse(
                    content={
                        "status": "proxy",
                        "file_id": file_id,
                        "proxy_mesh_id": proxy_mesh_id,
                        "task_id": task_id,
                        "total_pixels": total_pixels,
                        "estimated_tiles": estimated_tiles,
                        "message": f"Proxy mesh ready! Detailed tiling in progress ({estimated_tiles} tiles estimated).",
                        "use_proxy": True,
                        "crs": "EPSG:4326"
                        if isinstance(dtm.crs, int)
                        else str(dtm.crs),
                        "bounds": {
                            "min_x": float(dtm.bounds.min_x),
                            "min_y": float(dtm.bounds.min_y),
                            "max_x": float(dtm.bounds.max_x),
                            "max_y": float(dtm.bounds.max_y),
                        },
                    }
                )

            simplification = params.get("simplification", 0.5)
            z_scale = params.get("z_scale", 1.0)

            # Generate terrain mesh
            mesh = generate_terrain_mesh(
                dtm=dtm,
                simplification=simplification,
                z_scale=z_scale,
            )

            # Store mesh
            mesh_id = str(uuid.uuid4())
            self._mesh_storage[mesh_id] = {
                "type": "terrain",
                "data": mesh,
                "source_file": file_id,
                "params": params,
            }

            result = {
                "mesh_id": mesh_id,
                "type": "terrain",
                "file_id": file_id,
                "metadata": {
                    "vertex_count": len(mesh.vertices)
                    if mesh.vertices is not None
                    else 0,
                    "face_count": len(mesh.faces) if mesh.faces is not None else 0,
                    "bounds": {
                        "min_x": float(dtm.bounds.min_x),
                        "min_y": float(dtm.bounds.min_y),
                        "max_x": float(dtm.bounds.max_x),
                        "max_y": float(dtm.bounds.max_y),
                    },
                    "simplification": simplification,
                    "z_scale": z_scale,
                },
            }

            logger.info(
                f"Generated terrain mesh {mesh_id} from {stored_data['filename']}"
            )
            return JSONResponse(content=result)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Mesh generation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def tile_dtm_endpoint(self, params: Dict) -> JSONResponse:
        """Create tiles from a large DTM for streaming.

        Args:
            params: Parameters including file_id and max_tile_size

        Returns:
            List of tile IDs created
        """
        try:
            file_id = params.get("file_id")
            max_tile_size = params.get("max_tile_size", 200)

            if not file_id or file_id not in self._gis_storage:
                raise HTTPException(
                    status_code=400, detail="Invalid or missing file_id"
                )

            stored_data = self._gis_storage[file_id]
            if stored_data["type"] != "dtm":
                raise HTTPException(status_code=400, detail="File is not a raster DTM")

            dtm = stored_data["data"]

            # Create tiles
            tile_ids = self.tile_manager.create_tiles_from_dtm(dtm)
            self._tiled_dtms[file_id] = tile_ids

            logger.info(f"Created {len(tile_ids)} tiles for DTM {file_id}")

            return JSONResponse(
                content={
                    "file_id": file_id,
                    "tile_count": len(tile_ids),
                    "tiles": tile_ids,
                    "stats": self.tile_manager.get_stats(),
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Tile creation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_tile_endpoint(self, tile_id: str) -> JSONResponse:
        """Get a specific tile's mesh data.

        Args:
            tile_id: Tile identifier

        Returns:
            Tile mesh data
        """
        try:
            tile = self.tile_manager.get_tile_by_id(tile_id)
            if not tile:
                raise HTTPException(
                    status_code=404, detail=f"Tile not found: {tile_id}"
                )

            # Return with LOD 0 (full detail) by default
            from .gis.tile_manager import LODLevel

            mesh_data = tile.lod_meshes.get(LODLevel.L0, {})

            return JSONResponse(
                content={
                    "tile_id": tile_id,
                    "bounds": {
                        "min_x": tile.bounds.min_x,
                        "min_y": tile.bounds.min_y,
                        "max_x": tile.bounds.max_x,
                        "max_y": tile.bounds.max_y,
                    },
                    "resolution": tile.resolution,
                    "vertices": mesh_data.get("data", {})
                    .get("attributes", {})
                    .get("position", {})
                    .get("array", []),
                    "indices": mesh_data.get("data", {})
                    .get("index", {})
                    .get("array", []),
                    "normals": mesh_data.get("data", {})
                    .get("attributes", {})
                    .get("normal", {})
                    .get("array", []),
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get tile error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_visible_tiles_endpoint(self, params: Dict) -> JSONResponse:
        """Get tiles visible from camera position.

        Args:
            params: Camera position and view distance

        Returns:
            List of visible tile IDs
        """
        try:
            camera_pos = params.get("camera_position", [0, 0, 0])
            view_distance = params.get("view_distance", 2000)

            visible_tiles = self.tile_manager.get_visible_tiles(
                camera_pos=tuple(camera_pos), view_distance=view_distance
            )

            tile_ids = [tile.tile_id for tile in visible_tiles]

            return JSONResponse(
                content={
                    "visible_tiles": tile_ids,
                    "count": len(tile_ids),
                    "camera_position": camera_pos,
                    "view_distance": view_distance,
                }
            )

        except Exception as e:
            logger.error(f"Get visible tiles error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def list_uploaded_files(self) -> JSONResponse:
        """List all uploaded GIS files available for use.

        Returns:
            List of uploaded files with metadata
        """
        try:
            files = []
            for file_id, data in self._gis_storage.items():
                file_info = {
                    "file_id": file_id,
                    "filename": data.get("filename", "unknown"),
                    "type": data.get("type", "unknown"),
                }

                # Add type-specific metadata
                if data["type"] == "dtm":
                    dtm = data["data"]
                    file_info["dimensions"] = {"width": dtm.width, "height": dtm.height}
                    file_info["total_pixels"] = dtm.width * dtm.height
                    file_info["bounds"] = {
                        "min_x": dtm.bounds.min_x,
                        "min_y": dtm.bounds.min_y,
                        "max_x": dtm.bounds.max_x,
                        "max_y": dtm.bounds.max_y,
                    }

                files.append(file_info)

            return JSONResponse(content={"files": files, "count": len(files)})

        except Exception as e:
            logger.error(f"Error listing files: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def start_async_tiling(self, params: Dict) -> JSONResponse:
        """Start async tiling process for large DTM.

        Returns immediately with task_id, processing continues in background.

        Args:
            params: Parameters including file_id

        Returns:
            Task ID for polling progress
        """
        try:
            import threading
            import uuid

            file_id = params.get("file_id")
            if not file_id or file_id not in self._gis_storage:
                raise HTTPException(
                    status_code=400, detail="Invalid or missing file_id"
                )

            stored_data = self._gis_storage[file_id]
            if stored_data["type"] != "dtm":
                raise HTTPException(status_code=400, detail="File is not a raster DTM")

            # Generate task ID
            task_id = str(uuid.uuid4())

            # Initialize progress tracking
            dtm = stored_data["data"]
            estimated_tiles = max(1, (dtm.width * dtm.height) // 40000)

            self._tiling_tasks[task_id] = {
                "file_id": file_id,
                "status": "starting",
                "progress": 0,
                "total_tiles": estimated_tiles,
                "completed_tiles": 0,
                "message": "Initializing tiling process...",
                "tile_ids": [],
                "started_at": time.time(),
            }

            # Start tiling in background thread
            def do_tiling():
                try:
                    self._tiling_tasks[task_id]["status"] = "processing"
                    self._tiling_tasks[task_id]["message"] = "Creating tiles..."

                    # Progress callback to update task status
                    def progress_callback(current, total, message):
                        progress = (
                            int((current / max(total, 1)) * 100) if total > 0 else 0
                        )
                        self._tiling_tasks[task_id].update(
                            {
                                "completed_tiles": current,
                                "total_tiles": total,
                                "progress": progress,
                                "message": message,
                            }
                        )
                        logger.info(
                            f"Tiling progress [{task_id}]: {current}/{total} - {message}"
                        )

                    # Create tiles with progress updates
                    tile_ids = self.tile_manager.create_tiles_from_dtm(
                        dtm, progress_callback=progress_callback
                    )

                    # Store result
                    self._tiled_dtms[file_id] = tile_ids

                    # Update task status
                    self._tiling_tasks[task_id].update(
                        {
                            "status": "completed",
                            "progress": 100,
                            "completed_tiles": len(tile_ids),
                            "total_tiles": len(tile_ids),
                            "tile_ids": tile_ids,
                            "message": f"Tiling complete! Created {len(tile_ids)} tiles",
                            "completed_at": time.time(),
                        }
                    )

                    logger.info(
                        f"Async tiling complete for {file_id}: {len(tile_ids)} tiles"
                    )

                except Exception as e:
                    logger.error(f"Async tiling error: {e}")
                    import traceback

                    logger.error(traceback.format_exc())
                    self._tiling_tasks[task_id].update(
                        {"status": "error", "message": str(e)}
                    )

            # Start background thread
            thread = threading.Thread(target=do_tiling)
            thread.daemon = True
            thread.start()

            logger.info(f"Started async tiling task {task_id} for file {file_id}")

            return JSONResponse(
                {
                    "task_id": task_id,
                    "status": "started",
                    "message": "Tiling started in background. Poll /api/gis/tiling-progress/{task_id} for updates.",
                    "estimated_tiles": estimated_tiles,
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Start async tiling error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_tiling_progress(self, task_id: str) -> JSONResponse:
        """Get progress of async tiling task.

        Args:
            task_id: Task ID from start_async_tiling

        Returns:
            Progress information
        """
        try:
            if task_id not in self._tiling_tasks:
                raise HTTPException(status_code=404, detail="Task not found")

            task = self._tiling_tasks[task_id].copy()

            # Calculate elapsed time
            if "started_at" in task:
                task["elapsed_seconds"] = time.time() - task["started_at"]

            return JSONResponse(content=task)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get tiling progress error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def cancel_tiling_task(self, task_id: str) -> JSONResponse:
        """Cancel an async tiling task.

        Args:
            task_id: Task ID to cancel

        Returns:
            Cancellation status
        """
        try:
            if task_id not in self._tiling_tasks:
                raise HTTPException(status_code=404, detail="Task not found")

            # Mark task as cancelled
            self._tiling_tasks[task_id]["status"] = "cancelled"
            self._tiling_tasks[task_id]["message"] = "Task cancelled by user"
            self._tiling_tasks[task_id]["cancelled_at"] = time.time()

            logger.info(f"Cancelled tiling task {task_id}")

            return JSONResponse(
                {
                    "task_id": task_id,
                    "status": "cancelled",
                    "message": "Tiling task has been cancelled",
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Cancel tiling error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the backend server.

        Args:
            host: Host address
            port: Port number
        """
        logger.info(f"Starting server on {host}:{port}")

        uvicorn.run(self.app, host=host, port=port, log_level="info")

    # =========================================================================
    # Weather Simulation Endpoints (Phase 6)
    # =========================================================================

    async def configure_weather(self, params: Dict) -> JSONResponse:
        """Configure weather simulation parameters.

        Args:
            params: Weather configuration including rainfall and wind settings

        Returns:
            Configuration confirmation
        """
        try:
            grid_size = params.get("grid_size", (100, 100))
            bounds = params.get("bounds", (0.0, 0.0, 1.0, 1.0))

            # Initialize weather simulator
            self.weather_sim = WeatherSimulator(grid_size=grid_size, bounds=bounds)

            # Configure rainfall if provided
            rainfall_config = params.get("rainfall")
            if rainfall_config:
                self.weather_sim.setup_rainfall(
                    intensity_mm_hr=rainfall_config.get("intensity_mm_hr", 10.0),
                    duration_hours=rainfall_config.get("duration_hours", 24.0),
                    distribution=rainfall_config.get("distribution", "uniform"),
                    peak_intensity_factor=rainfall_config.get(
                        "peak_intensity_factor", 2.0
                    ),
                    storm_center=rainfall_config.get("storm_center", (0.5, 0.5)),
                    storm_radius=rainfall_config.get("storm_radius", 0.2),
                    temporal_pattern=rainfall_config.get(
                        "temporal_pattern", "constant"
                    ),
                )

            # Configure wind if provided
            wind_config = params.get("wind")
            if wind_config:
                self.weather_sim.setup_wind(
                    speed_ms=wind_config.get("speed_ms", 5.0),
                    direction_degrees=wind_config.get("direction_degrees", 0.0),
                    pattern=wind_config.get("pattern", "uniform"),
                    turbulence_intensity=wind_config.get("turbulence_intensity", 0.1),
                    gust_factor=wind_config.get("gust_factor", 1.5),
                )

            logger.info("Weather simulation configured successfully")

            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Weather simulation configured",
                    "grid_size": grid_size,
                    "has_rainfall": rainfall_config is not None,
                    "has_wind": wind_config is not None,
                }
            )

        except Exception as e:
            logger.error(f"Weather configuration error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_rainfall_field(
        self, time_hours: Optional[float] = None
    ) -> JSONResponse:
        """Get rainfall field at specified time.

        Args:
            time_hours: Time in hours (uses current time if None)

        Returns:
            Rainfall intensity field
        """
        try:
            if self.weather_sim is None:
                raise HTTPException(
                    status_code=400, detail="Weather simulation not configured"
                )

            t = time_hours if time_hours is not None else self.weather_sim.current_time
            field = self.weather_sim.get_rainfall_field(t)

            return JSONResponse(
                content={
                    "time_hours": t,
                    "field": field.tolist(),
                    "mean_intensity": float(np.mean(field)),
                    "max_intensity": float(np.max(field)),
                    "grid_size": (self.weather_sim.nx, self.weather_sim.ny),
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rainfall field error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_wind_field(self) -> JSONResponse:
        """Get current wind field.

        Returns:
            Wind velocity components
        """
        try:
            if self.weather_sim is None:
                raise HTTPException(
                    status_code=400, detail="Weather simulation not configured"
                )

            u, v = self.weather_sim.get_wind_field()
            speed = self.weather_sim.get_wind_speed_field()

            return JSONResponse(
                content={
                    "u_component": u.tolist(),
                    "v_component": v.tolist(),
                    "speed": speed.tolist(),
                    "mean_speed": float(np.mean(speed)),
                    "max_speed": float(np.max(speed)),
                    "grid_size": (self.weather_sim.nx, self.weather_sim.ny),
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Wind field error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_cumulative_rainfall(
        self, time_hours: Optional[float] = None
    ) -> JSONResponse:
        """Get cumulative rainfall depth.

        Args:
            time_hours: Time in hours (uses current time if None)

        Returns:
            Cumulative rainfall field
        """
        try:
            if self.weather_sim is None:
                raise HTTPException(
                    status_code=400, detail="Weather simulation not configured"
                )

            t = time_hours if time_hours is not None else self.weather_sim.current_time
            cumulative = self.weather_sim.get_cumulative_rainfall(t)

            return JSONResponse(
                content={
                    "time_hours": t,
                    "cumulative_rainfall": cumulative.tolist(),
                    "mean_depth": float(np.mean(cumulative)),
                    "max_depth": float(np.max(cumulative)),
                    "total_volume_factor": float(np.sum(cumulative)),
                    "grid_size": (self.weather_sim.nx, self.weather_sim.ny),
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Cumulative rainfall error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # =========================================================================
    # Flood Physics Endpoints (Phase 7)
    # =========================================================================

    async def initialize_flood_simulation(self, params: Dict) -> JSONResponse:
        """Initialize flood simulation with terrain and parameters.

        Args:
            params: Simulation parameters including grid size, terrain, and physics settings

        Returns:
            Initialization confirmation
        """
        try:
            grid_size = params.get("grid_size", (100, 100))
            dx = params.get("dx", 10.0)
            gravity = params.get("gravity", 9.81)
            manning_n = params.get("manning_n", 0.03)

            # Initialize flood physics engine
            self.flood_engine = FloodPhysicsEngine3D(
                grid_size=grid_size,
                dx=dx,
                gravity=gravity,
                manning_n=manning_n,
            )

            # Set terrain if provided
            terrain_data = params.get("terrain")
            if terrain_data:
                elevation = np.array(terrain_data)
                self.flood_engine.set_terrain(elevation)

            # Set boundary conditions
            boundary_type = params.get("boundary_type", "wall")
            self.flood_engine.set_boundary_conditions(boundary_type)

            # Connect with weather if available
            if self.weather_sim and self.weather_sim.rainfall_params:
                # Convert cumulative rainfall to intensity for initial conditions
                rainfall_field = self.weather_sim.get_rainfall_field(0.0)
                self.flood_engine.set_rainfall(rainfall_field)

            logger.info(
                f"Flood simulation initialized: {grid_size[0]}x{grid_size[1]} grid"
            )

            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Flood simulation initialized",
                    "grid_size": grid_size,
                    "dx": dx,
                    "gravity": gravity,
                    "manning_n": manning_n,
                    "boundary_type": boundary_type,
                }
            )

        except Exception as e:
            logger.error(f"Flood simulation initialization error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def add_flood_source(self, params: Dict) -> JSONResponse:
        """Add water source to flood simulation.

        Args:
            params: Source parameters (x, y, depth, radius, shape)

        Returns:
            Source addition confirmation
        """
        try:
            if self.flood_engine is None:
                raise HTTPException(
                    status_code=400, detail="Flood simulation not initialized"
                )

            x = params.get("x", 0)
            y = params.get("y", 0)
            depth = params.get("depth", 1.0)
            radius = params.get("radius", 5)
            shape = params.get("shape", "circular")

            self.flood_engine.add_initial_water_source(x, y, depth, radius, shape)

            return JSONResponse(
                content={
                    "status": "success",
                    "message": f"Water source added at ({x}, {y})",
                    "depth": depth,
                    "radius": radius,
                    "current_max_depth": self.flood_engine.get_maximum_depth(),
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Add flood source error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def step_flood_simulation(self, params: Dict) -> JSONResponse:
        """Advance flood simulation by one or more timesteps.

        Args:
            params: Step parameters (num_steps, dt)

        Returns:
            Current simulation state
        """
        try:
            if self.flood_engine is None:
                raise HTTPException(
                    status_code=400, detail="Flood simulation not initialized"
                )

            num_steps = params.get("num_steps", 1)
            dt = params.get("dt")

            # Update rainfall if weather simulation is running
            if self.weather_sim:
                rainfall_field = self.weather_sim.get_rainfall_field(
                    self.flood_engine.time / 3600.0
                )
                self.flood_engine.set_rainfall(rainfall_field)

            # Run simulation steps
            for _ in range(num_steps):
                self.current_flood_state = self.flood_engine.step(dt)

            return JSONResponse(
                content={
                    "status": "success",
                    "timestep": self.flood_engine.timestep,
                    "time_seconds": self.flood_engine.time,
                    "time_hours": self.flood_engine.time / 3600.0,
                    "max_depth": self.flood_engine.get_maximum_depth(),
                    "total_volume": self.flood_engine.get_total_volume(),
                    "flood_extent": self.flood_engine.get_flood_extent(),
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Flood step error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_flood_state(self) -> JSONResponse:
        """Get current flood simulation state.

        Returns:
            Current state including water depth and velocities
        """
        try:
            if self.flood_engine is None:
                raise HTTPException(
                    status_code=400, detail="Flood simulation not initialized"
                )

            state = self.flood_engine.get_state()

            return JSONResponse(
                content={
                    "time_seconds": state.time,
                    "time_hours": state.time / 3600.0,
                    "water_depth": state.water_depth.tolist(),
                    "velocity_u": state.velocity_u.tolist(),
                    "velocity_v": state.velocity_v.tolist(),
                    "max_depth": self.flood_engine.get_maximum_depth(),
                    "total_volume": self.flood_engine.get_total_volume(),
                    "flood_extent": self.flood_engine.get_flood_extent(),
                    "max_velocity": float(
                        np.max(self.flood_engine.get_velocity_magnitude())
                    ),
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get flood state error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def run_flood_simulation(self, params: Dict) -> JSONResponse:
        """Run flood simulation for a specified duration.

        Args:
            params: Run parameters (duration_hours, output_interval)

        Returns:
            Simulation results and statistics
        """
        try:
            if self.flood_engine is None:
                raise HTTPException(
                    status_code=400, detail="Flood simulation not initialized"
                )

            duration_hours = params.get("duration_hours", 1.0)
            output_interval = params.get("output_interval", 0.1)  # hours

            duration_seconds = duration_hours * 3600.0
            output_interval_seconds = output_interval * 3600.0

            start_time = self.flood_engine.time
            end_time = start_time + duration_seconds

            outputs = []
            next_output_time = start_time

            while self.flood_engine.time < end_time:
                # Update rainfall
                if self.weather_sim:
                    rainfall_field = self.weather_sim.get_rainfall_field(
                        self.flood_engine.time / 3600.0
                    )
                    self.flood_engine.set_rainfall(rainfall_field)

                # Step simulation
                self.current_flood_state = self.flood_engine.step()

                # Record output if interval reached
                if self.flood_engine.time >= next_output_time:
                    outputs.append(
                        {
                            "time_hours": self.flood_engine.time / 3600.0,
                            "max_depth": self.flood_engine.get_maximum_depth(),
                            "total_volume": self.flood_engine.get_total_volume(),
                            "flood_extent": self.flood_engine.get_flood_extent(),
                        }
                    )
                    next_output_time += output_interval_seconds

            # Export final results
            results = self.flood_engine.export_results()

            return JSONResponse(
                content={
                    "status": "success",
                    "duration_hours": duration_hours,
                    "total_steps": self.flood_engine.timestep,
                    "final_time_hours": self.flood_engine.time / 3600.0,
                    "outputs": outputs,
                    "final_results": results,
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Run flood simulation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


class WebSocketManager:
    """Manages WebSocket connections for real-time communication.

    Handles multiple client connections and message routing.
    """

    def __init__(self):
        """Initialize the WebSocket manager."""
        self.connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Establish WebSocket connection.

        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        self.connections.append(websocket)
        logger.info(f"WebSocket connection established")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove WebSocket connection.

        Args:
            websocket: WebSocket connection to remove
        """
        if websocket in self.connections:
            self.connections.remove(websocket)
            logger.info(f"WebSocket connection removed")

    async def send_message(self, websocket: WebSocket, message: Dict) -> None:
        """Send message through WebSocket.

        Args:
            websocket: Target WebSocket
            message: Message to send
        """
        await websocket.send_json(message)

    async def broadcast(self, message: Dict) -> None:
        """Broadcast message to all connected clients.

        Args:
            message: Message to broadcast
        """
        for connection in self.connections:
            try:
                await self.send_message(connection, message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")


# Main entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Flood Prediction World Model Server")
    parser.add_argument(
        "--config",
        type=str,
        default="config/model_config.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Server host address"
    )
    parser.add_argument("--port", type=int, default=8000, help="Server port number")

    args = parser.parse_args()

    # Initialize and run server
    server = FloodWorldServer(config_path=args.config)
    server.run(host=args.host, port=args.port)


# Create module-level app instance for uvicorn
# This allows running with: uvicorn src.server:app
config_path = os.environ.get("FLOOD_CONFIG", "config/model_config.yaml")
try:
    _server_instance = FloodWorldServer(config_path=config_path)
    app = _server_instance.app
except Exception as e:
    logger.error(f"Failed to initialize server: {e}")
    # Create a minimal app for health checks
    app = FastAPI(title="Flood Prediction World Model - Error State")

    @app.get("/health")
    async def error_health():
        return {"status": "error", "message": str(e)}

    async def reimport_existing_file(self, file_id: str) -> JSONResponse:
        """Re-import a file that exists in upload directory but not in memory.

        Args:
            file_id: The file ID (UUID)

        Returns:
            File metadata
        """
        try:
            import os

            filepath = Path("/tmp/flood_prediction_uploads") / f"{file_id}.tif"

            if not filepath.exists():
                raise HTTPException(
                    status_code=404, detail=f"File not found: {file_id}"
                )

            # Re-import the file
            dtm = self.gis_importer.import_raster(str(filepath))

            # Store in memory
            self._gis_storage[file_id] = {
                "type": "dtm",
                "data": dtm,
                "filename": f"{file_id}.tif",
            }

            return JSONResponse(
                {
                    "status": "reimported",
                    "file_id": file_id,
                    "dimensions": {"width": dtm.width, "height": dtm.height},
                    "total_pixels": dtm.width * dtm.height,
                    "message": "File re-imported successfully. You can now use it.",
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Reimport error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
