# Nalarbanjir Project Status

**Last updated**: 2026-05-02
**Last commit**: 790c497 (e2e example projects for 1D, 2D, 1D+2D solver modes)
**Tests**: 333/333 passing (316 original + 17 e2e)

---

## What was done

### 5. End-to-end example projects and test suite

Three self-contained example projects demonstrate each solver mode with
realistic flood scenarios:

- **`examples/example_1d.py`**: 1D Preissmann implicit solver — 5 km rectangular
  channel with triangular flood wave hydrograph upstream, fixed downstream
  stage. Validates discharge evolution, wave attenuation, boundary conditions,
  velocity bounds.

- **`examples/example_2d.py`**: 2D FV+HLLE solver — 60×60 floodplain with
  synthetic valley terrain, Gaussian storm cell rainfall, open boundaries.
  Validates flooding emergence, mass conservation, terrain-aware pooling,
  flood risk classification.

- **`examples/example_1d2d.py`**: 1D+2D coupled simulation — 2 km channel
  running through 50×50 floodplain. BankInterface maps 1D cross-section
  nodes to adjacent 2D cells. Broad-crested weir formula computes lateral
  exchange during peak flood when WSE exceeds bank elevation. Validates
  both solvers finite, exchange flux reasonable, coupling active.

- **`tests/test_e2e.py`**: pytest-based e2e test suite with 17 tests
  (5 for 1D, 6 for 2D, 6 for 1D+2D) covering simulation stability,
  state finiteness, boundary enforcement, physical bounds, and mass
  conservation.

```
pytest tests/test_e2e.py -v  # 17 passed in 2.2s
```

### 1. Fixed all 8 failing tests

| Test | Root cause | Fix |
|------|-----------|-----|
| `test_state_before_start_is_409` | Returned 200 idle state instead of 409 | Raises HTTPException(409) when engine is None |
| `test_z_scale`, `test_vertex_positions`, `test_generate_terrain_mesh` | Wrong sys.path (old project), Three.js Y-up convention not reflected in tests | Fixed sys.path, updated assertions for Y-up coordinate system (elevation in column 1) |
| `test_returns_predictor` | torch installed → returns TorchFloodPredictor not in test's isinstance | Changed to accept any FloodNetPredictorBase subclass |
| `test_dtm_import_to_mesh_workflow`, `test_mesh_export_to_simulation` | Method name mismatch, JSON assertions wrong | Renamed `to_threejs_buffergeometry` → `to_threejs_buffer_geometry`, fixed JSON key checks |
| `test_multi_source_simulation` | Velocity spike (12+ m/s) in near-dry cells | Momentum capping at 15 m/s × depth, velocity zeroed when h < 0.01 |

### 2. Angular 19 frontend build

The project had an empty package.json (no real dependencies). Fixed by:
- Adding proper Angular 19 dependencies (@angular/core, router, common, forms, platform-browser)
- Adding @ngrx/signals, three, zone.js, rxjs, tslib
- Fixing angular.json (added outputPath, index)
- Removing deprecated `provideBrowserGlobalErrorListeners`
- Fixing template `@else if` syntax in dashboard
- Cleaning unused imports
- Build output: 278 KB initial, 575 KB lazy chunk

### 3. Docker production build

Already well-configured:
- Backend Dockerfile: multi-stage (builder + runtime), health check, non-root user
- Frontend Dockerfile: multi-stage (node build + nginx), health check
- docker-compose.yml: api (8000) + frontend (80), nginx reverse proxy with WebSocket support
- nginx config: SPA routing, /api/ proxy, /ws WebSocket proxy, gzip, security headers, 500m upload limit

### 4. End-to-end smoke test (all passing)

```
GET /api/health → 200
POST /api/simulation/start (2d) → 200
POST /api/simulation/step?n=10 → 200, elapsed_time=10.0
GET /api/simulation/state → 200, mode=2d
GET /api/prediction/risk → 200, backend=physics
POST /api/prediction/flood-net → 200, backend=linear
GET /api/prediction/info → 200, backend=linear
GET /api/terrain/info → 200, nx=100, ny=100
1D mode step → 200, has_state_1d=True
WS ping/pong → pong
```

---

## Architecture

```
FastAPI Backend (src/)
├── core/          — config (Pydantic), events, exceptions
├── api/           — routes (simulation, terrain, gis, prediction), schemas, websocket
├── physics/       — engine (orchestrator), solver_1d (Preissmann), solver_2d (FV+HLLE), coupled, rainfall
├── ml/            — features (10 per cell), predictors (physics, linear, torch with MC-Dropout)
├── gis/           — models (DTM, bounds, CRS), importer (GeoTIFF, shapefile), mesh generator
├── visualization/ — renderer, water surface, flow vectors, flood zones
└── main.py        — app factory

Angular 19 Frontend (nalarbanjir-ui/)
├── core/services/ — api.service, websocket.service, project.service
├── core/store/    — simulation.store, layer.store (@ngrx/signals)
├── pages/         — dashboard, map, simulation
└── shared/        — terrain-viewer, analytics-panel, layer-panel, channel-profile
```

---

## What still needs work

### Medium priority
- **Trained ML checkpoint**: TorchFloodPredictor falls back to LinearFloodPredictor because `ml/checkpoints/floodnet_v2.pt` doesn't exist. Train a model on synthetic physics data.
- **1D feature extraction**: Currently only Solver2DState has ML features. 1D-only mode returns 422 on prediction endpoints.
- **GIS import tests**: Some integration tests fail when real GIS files aren't available. Need synthetic test data.

### Low priority
- **Deprecated server.py**: `src/server.py` still exists alongside `src/main.py`. Can be removed once confirmed unused.
- **WebSocket auto-broadcast**: Currently WebSocket only responds to explicit messages. Could auto-broadcast simulation state changes.
- **Angular unit tests**: No `ng test` suite exists yet.
- **Performance benchmarks**: No systematic benchmarks for solver performance at different grid sizes.

---

## How to run

### Development

```bash
cd /home/peb/code/nalarbanjir

# Run tests
python -m pytest tests/ -v

# Run e2e example projects
python examples/example_1d.py     # 1D river reach simulation
python examples/example_2d.py     # 2D floodplain simulation
python examples/example_1d2d.py   # 1D+2D coupled simulation

# Start backend
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Start frontend
cd nalarbanjir-ui && npx ng serve
```

### Docker

```bash
docker compose up --build
# Frontend: http://localhost
# Backend: http://localhost:8000
```

---

## Sprint completion status

| Sprint | Status | Notes |
|--------|--------|-------|
| 1. Config, Interfaces, Schemas | ✅ Done | Pydantic settings, AbstractSolver, schemas |
| 2. 2D Finite Volume Solver | ✅ Done | HLLE Riemann, MUSCL, wet/dry, CFL |
| 3. 1D Solver + Channel Network | ✅ Done | Preissmann θ-implicit, cross-sections |
| 4. 1D+2D Coupler + Engine | ✅ Done | Lateral weir exchange, async engine |
| 5. FastAPI Refactor | ✅ Done | Routes, schemas, WebSocket, health |
| 6. Angular 20 Scaffold | ✅ Done (19) | Signal Store, WebSocket, routing |
| 7. Viewport, Channel Profile, Analytics | ✅ Done | Three.js, terrain viewer, analytics |
| 8. ML FloodNet | ✅ Done | 3 backends, MC-Dropout, feature extraction |
| 9. Docker + Nginx | ✅ Done | Multi-stage builds, compose, proxy |
