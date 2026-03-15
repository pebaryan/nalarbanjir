#!/usr/bin/env python3
"""
Flood Prediction World Model - Simulation Runner

This script serves as the main entry point for running the flood prediction
world model simulation, integrating physics, machine learning, and visualization.
"""

import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.server import FloodWorldServer
from src.physics.shallow_water import ShallowWaterSolver, WavePropagationAnalyzer
from src.physics.terrain import TerrainModel
from src.ml.model import MLModel, ModelConfig
from src.visualization.renderer import VisualizationRenderer


def configure_logging(log_level: str, log_file: str = None):
    """Configure logging settings.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
    """
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=getattr(logging, log_level.upper()),
        handlers=[
            logging.StreamHandler(sys.stdout),
            *(
                [logging.FileHandler(log_file)]
                if log_file
                else []
            )
        ]
    )
    return logging.getLogger(__name__)


def load_configuration(config_path: str) -> dict:
    """Load configuration from YAML file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    import yaml
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        logging.info(f"Loaded configuration from {config_path}")
        return config
    except FileNotFoundError:
        logging.warning(f"Configuration file not found: {config_path}")
        logging.info("Using default configuration")
        return get_default_configuration()
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        return get_default_configuration()


def get_default_configuration() -> dict:
    """Get default configuration settings.
    
    Returns:
        Default configuration dictionary
    """
    return {
        'physics': {
            'gravity': 9.81,
            'coriolis': 0.0,
            'bottom_friction': 0.02,
            'time_step': 1.0,
            'domain_x': 10000.0,
            'domain_y': 10000.0,
            'terrain_amplitude': 2.0,
            'terrain_wavelength': 2000.0
        },
        'grid': {
            'nx': 100,
            'ny': 100,
            'batch_size': 32
        },
        'terrain': {
            'flood_thresholds': {
                'minor': 1.0,
                'moderate': 2.0,
                'major': 3.0,
                'severe': 5.0
            }
        },
        'ml': {
            'model_type': 'flood_net',
            'input_features': 10,
            'hidden_dims': [64, 128, 256],
            'output_features': 5,
            'learning_rate': 1e-3,
            'dropout_rate': 0.1,
            'batch_size': 32
        },
        'visualization': {
            'resolution': 'high',
            'update_frequency': 30,
            'render_mode': 'realtime'
        },
        'simulation': {
            'total_steps': 1000,
            'save_every': 100,
            'log_every': 10
        }
    }


def initialize_components(config: dict, logger: logging.Logger):
    """Initialize simulation components.
    
    Args:
        config: Configuration dictionary
        logger: Logger instance
        
    Returns:
        Dictionary of initialized components
    """
    # Initialize physics solver
    logger.info("Initializing physics solver...")
    physics_solver = ShallowWaterSolver(
        config=config['physics'],
        grid_resolution=(config['grid']['nx'], config['grid']['ny'])
    )
    
    # Initialize terrain model
    logger.info("Initializing terrain model...")
    terrain = TerrainModel(
        config=config['terrain'],
        resolution=(config['grid']['nx'], config['grid']['ny'])
    )
    
    # Initialize ML model
    logger.info("Initializing ML model...")
    ml_model = MLModel(
        config=ModelConfig.from_dict(config['ml'])
    )
    
    # Initialize visualization renderer
    logger.info("Initializing visualization renderer...")
    renderer = VisualizationRenderer(config=config['visualization'])
    
    # Initialize wave propagation analyzer
    logger.info("Initializing wave propagation analyzer...")
    wave_analyzer = WavePropagationAnalyzer(physics_solver)
    
    components = {
        'physics_solver': physics_solver,
        'terrain': terrain,
        'ml_model': ml_model,
        'renderer': renderer,
        'wave_analyzer': wave_analyzer
    }
    
    logger.info("All components initialized successfully")
    return components


def run_simulation(
    config: dict,
    components: dict,
    logger: logging.Logger,
    duration: int = None,
    output_dir: str = None
):
    """Run the flood prediction simulation.
    
    Args:
        config: Configuration dictionary
        components: Dictionary of initialized components
        logger: Logger instance
        duration: Simulation duration in steps (optional)
        output_dir: Output directory path
    """
    physics_solver = components['physics_solver']
    terrain = components['terrain']
    ml_model = components['ml_model']
    renderer = components['renderer']
    wave_analyzer = components['wave_analyzer']
    
    logger.info(f"Starting simulation with {config['simulation']['total_steps']} steps")
    
    # Run simulation evolution
    states = physics_solver.evolve(steps=config['simulation']['total_steps'])
    
    # Analyze wave propagation
    logger.info("Analyzing wave propagation...")
    final_state = states[-1]
    wave_analysis = wave_analyzer.analyze_wave_propagation(final_state)
    
    # Identify flood zones
    logger.info("Identifying flood zones...")
    flood_zones = terrain.get_flood_zones(physics_solver.state.depth)
    
    # Render visualization
    logger.info("Rendering visualization...")
    render_output = renderer.render(
        physics_solver=physics_solver,
        terrain=terrain,
        output_format='full'
    )
    
    # Generate ML predictions
    logger.info("Generating ML predictions...")
    predictions = ml_model.predict(
        input_data={
            'elevation': terrain.elevation.mean(),
            'permeability': terrain.permeability.mean(),
            'water_depth': physics_solver.state.depth.mean(),
            'velocity_x': physics_solver.state.velocity_x.mean(),
            'velocity_y': physics_solver.state.velocity_y.mean()
        },
        prediction_type='flood_risk'
    )
    
    # Compile simulation results
    results = {
        'simulation_time': final_state.time,
        'total_steps': len(states),
        'wave_propagation': wave_analysis,
        'flood_zones': flood_zones,
        'visualizations': render_output,
        'ml_predictions': predictions
    }
    
    # Export results
    if output_dir:
        output_path = Path(output_dir) / 'simulation_results.json'
        export_simulation_results(results, output_path, logger)
    
    # Display results summary
    display_results_summary(results, logger)
    
    return results


def export_simulation_results(
    results: dict,
    output_path: Path,
    logger: logging.Logger
):
    """Export simulation results to file.
    
    Args:
        results: Simulation results dictionary
        output_path: Path to output file
        logger: Logger instance
    """
    import json
    
    try:
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Simulation results exported to {output_path}")
    except Exception as e:
        logger.error(f"Error exporting results: {e}")


def display_results_summary(results: dict, logger: logging.Logger):
    """Display a summary of simulation results.
    
    Args:
        results: Simulation results dictionary
        logger: Logger instance
    """
    logger.info("=" * 60)
    logger.info("SIMULATION RESULTS SUMMARY")
    logger.info("=" * 60)
    
    # Simulation time
    logger.info(f"Total Simulation Time: {results['simulation_time']:.2f} seconds")
    logger.info(f"Total Steps Completed: {results['total_steps']}")
    
    # Wave propagation
    wave = results['wave_propagation']
    logger.info(f"Mean Wave Celerity: {wave['mean_celerity']:.2f} m/s")
    logger.info(f"Max Wave Celerity: {wave['max_celerity']:.2f} m/s")
    
    # Flood zones
    zones = results['flood_zones']
    total_zones = sum(len(zone) for zone in zones.values())
    logger.info(f"Total Flood Zones: {total_zones}")
    logger.info(f"Zone Distribution:")
    for zone_type, zone_list in zones.items():
        logger.info(f"  - {zone_type}: {len(zone_list)} areas")
    
    # ML predictions
    ml = results['ml_predictions']
    logger.info(f"ML Model: {ml['model_type']}")
    logger.info(f"Prediction Confidence: {ml['confidence']:.2%}")
    
    logger.info("=" * 60)


def main():
    """Main entry point for the simulation runner."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Flood Prediction World Model Simulation'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/model_config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=None,
        help='Simulation duration in steps'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='output',
        help='Output directory for results'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level'
    )
    parser.add_argument(
        '--serve',
        action='store_true',
        help='Start web server'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_file = Path(args.output) / 'simulation.log'
    logger = configure_logging(args.log_level, log_file)
    
    logger.info("Flood Prediction World Model - Simulation Runner")
    logger.info(f"Configuration: {args.config}")
    logger.info(f"Output Directory: {args.output}")
    
    try:
        # Load configuration
        config = load_configuration(args.config)
        
        # Initialize components
        components = initialize_components(config, logger)
        
        # Run simulation
        if not args.serve:
            results = run_simulation(
                config=config,
                components=components,
                logger=logger,
                duration=args.duration,
                output_dir=args.output if args.output else None
            )
            
            logger.info("Simulation completed successfully")
        else:
            # Start web server
            server = FloodWorldServer(config_path=args.config)
            server.run()
    
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user")
    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
