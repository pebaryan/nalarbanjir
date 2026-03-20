# Frontend Directory

This directory contains all frontend assets for the nalarbanjir application.

## Directory Structure

```
frontend/
├── js/                    # JavaScript files (legacy)
│   ├── app.js            # Main application script
│   ├── gis_visualization.js
│   ├── proxy_tiles.js
│   ├── river_entry.js
│   ├── threejs_scene.js
│   ├── tile_streaming.js
│   ├── water_shader_manager.js
│   └── water_shaders.js
├── css/                   # CSS styles
│   ├── styles.css
│   └── visualization.css
├── templates/             # HTML templates
│   └── index.html
├── test_3d.html          # 3D test HTML file
├── test_terrain.tif       # Test terrain file
├── nginx.conf            # Nginx configuration
└── README.md            # This file
```

## Files

### JavaScript Files (js/)
- `app.js` - Main application initialization and navigation
- `gis_visualization.js` - GIS data visualization controller
- `proxy_tiles.js` - Proxy tile system for large DTMs
- `river_entry.js` - River geometry management
- `threejs_scene.js` - Three.js scene manager
- `tile_streaming.js` - Tile streaming for large terrain
- `water_shader_manager.js` - Water rendering manager
- `water_shaders.js` - Water surface shaders

### CSS Files (css/)
- `styles.css` - Main stylesheet
- `visualization.css` - Visualization-specific styles

### Templates (templates/)
- `index.html` - Main HTML template

### Test Files
- `test_3d.html` - 3D scene test page
- `test_terrain.tif` - Test DTM file

## Integration with Angular

The old JavaScript files can be loaded in Angular components or loaded separately as standalone scripts.

## TypeScript Migration

The TypeScript services and types are located in the parent `services/` and `types/` directories and can be used in Angular components.