# Deprecated Server

`server.py` was the original monolithic server (1945 lines) that combined
physics, ML, GIS, and API routes in a single class `FloodWorldServer`.

It was replaced by the modern modular architecture:
- `src/main.py` — FastAPI application factory
- `src/api/routes/` — modular route modules (health, simulation, terrain, prediction, gis, layers, rivers)
- `src/core/config.py` — configuration
- `src/core/events.py` — lifespan events

This folder is kept for reference only. Do not import from here in new code.
