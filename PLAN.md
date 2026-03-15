# Nalarbanjir — Implementation Plan v2.0

> Generated: 2026-03-15
> Scope: Full rebuild — 1D/2D/coupled hydraulic solvers + Angular 20 frontend
> External data connectors: deferred (not in scope)

---

## Objective

Rebuild Nalarbanjir from its current state (2D-only, np.gradient solver, vanilla JS frontend, monolithic server.py) into a production-quality system with:

1. **Three hydraulic solver modes** — 1D (Preissmann implicit), 2D (finite volume + HLLE Riemann), and 1D+2D coupled
2. **Clean layered backend** — FastAPI split into route modules, physics engine, ML service, GIS service
3. **Angular 20 frontend** — signals-based state, Three.js 3D viewport, channel profile view, analytics dashboard

---

## Architecture Summary

```
Angular 20 Frontend
  └── Signal Store ← WebSocket Service ← HTTP Services
        ↓ REST + WebSocket
FastAPI Gateway (main.py)
  ├── routes/ (simulation, terrain, gis, prediction, network)
  ├── websocket/ (manager, handlers)
  └── schemas/ (pydantic v2)
        ↓
Physics Engine (engine.py orchestrates)
  ├── solver_1d/  — Preissmann implicit, channel network graph
  ├── solver_2d/  — HLLE finite volume, MUSCL reconstruction
  └── coupled/    — lateral weir exchange, time sync
        ↓
Supporting Services
  ├── ML (FloodNet PyTorch, MC-Dropout UQ)
  └── GIS (rasterio ingest, sink-fill, LOD mesh)
```

---

## Sprint Plan

### Sprint 1 — Foundation: Config, Interfaces, Schemas
**Goal**: Establish the contracts everything else builds on.

Files to create/modify:
- `config/model_config.yaml` — restructure for multi-mode (solver_1d, solver_2d, coupling sections)
- `src/core/config.py` — Pydantic Settings loading from YAML
- `src/core/exceptions.py` — domain exceptions
- `src/core/events.py` — FastAPI lifespan hooks
- `src/physics/base.py` — AbstractSolver protocol (step(), reset(), state property)
- `src/physics/state.py` — SimulationState, Solver1DState, Solver2DState, CoupledState dataclasses
- `src/api/schemas/` — Pydantic v2 request/response models for all routes

Acceptance criteria:
- [ ] Config loads cleanly with Pydantic validation
- [ ] AbstractSolver protocol defines the interface all three solvers implement
- [ ] State dataclasses cover all fields needed by frontend

---

### Sprint 2 — 2D Finite Volume Solver (replaces np.gradient)
**Goal**: Replace the current non-conservative explicit FD solver with a proper FV solver.

**Why this is the most critical sprint**: The current `np.gradient` approach is not mass-conservative and will produce wrong flood extents on real terrain.

Files to create:
- `src/physics/solver_2d/riemann.py` — HLLE Riemann solver
  - Wave speed estimates: s_L = min(u_L - c_L, u_R - c_R), s_R = max(u_L + c_L, u_R + c_R)
  - HLLE flux: F = (s_R·F_L - s_L·F_R + s_L·s_R·(U_R - U_L)) / (s_R - s_L)
- `src/physics/solver_2d/reconstruction.py` — MUSCL + minmod slope limiter
  - Extrapolates cell-center values to cell faces (2nd-order accuracy)
- `src/physics/solver_2d/wet_dry.py` — Wet/dry front treatment
  - Zero flux when h < ε = 0.001m
  - Hydrostatic reconstruction for bed slope source term (preserves C-property)
- `src/physics/solver_2d/finite_volume.py` — Main FV solver implementing AbstractSolver
  - CFL-adaptive time stepping: Δt = CFL·Δx / max(|u|+√(gh))
  - Operator splitting: hyperbolic step + source terms
  - Friction: pointwise implicit update
- `src/physics/solver_2d/boundary.py` — Reflective, open (Neumann), inflow BCs
- `src/physics/rainfall.py` — Rainfall source term (uniform, storm-cell Gaussian, frontal)

Files to modify:
- `src/physics/shallow_water.py` — deprecate (keep for reference, route to new solver)

Acceptance criteria:
- [ ] Mass conservation check: Σh·dx·dy at t=0 + Σ(rainfall·dt) = Σh·dx·dy at t=T ± 0.1%
- [ ] Dam-break test: matches Ritter analytical solution within 5%
- [ ] Wet/dry: no negative water depths after 1000 steps on dry terrain
- [ ] CFL stability: no blowup at CFL=0.9

---

### Sprint 3 — 1D Solver + Channel Network
**Goal**: Implement the Preissmann implicit scheme for river channels.

Files to create:
- `src/physics/solver_1d/cross_section.py` — Cross-section geometry
  - Survey points (y, z) → lookup tables for A(h), P(h), T(h), R(h)
  - Integration by trapezoidal rule
- `src/physics/solver_1d/network.py` — Channel network as directed graph
  - Nodes: cross-sections with chainage (distance along reach)
  - Edges: reaches
  - Junctions: mass balance Q_in = Σ Q_out
  - Boundary nodes: upstream Q(t) hydrograph, downstream h(t) stage
- `src/physics/solver_1d/preissmann.py` — Preissmann θ-implicit scheme
  - θ = 0.6 (stability), builds block-tridiagonal system
  - Thomas algorithm (double-sweep) for O(N) solve
  - Handles sub/supercritical transitions via Froude number check
- `src/physics/solver_1d/boundary.py` — Q(t) and h(t) boundary condition applicators
- `src/physics/solver_1d/routing.py` — Muskingum-Cunge for simple reaches (fallback)

Acceptance criteria:
- [ ] Mass conservation along a single reach
- [ ] Backwater curve: matches analytical M1/M2 profiles within 2%
- [ ] Stability at Δt = 60s on a 100-node network
- [ ] Junction balance: inflow = outflow at all junctions

---

### Sprint 4 — 1D+2D Coupler + SimulationEngine
**Goal**: Wire all three solvers behind a single orchestrating engine.

Files to create:
- `src/physics/coupled/interface.py` — Bank interface nodes
  - Maps 1D cross-section bank nodes to 2D floodplain cells
  - Stores bank elevation z_bank per interface segment
- `src/physics/coupled/coupler.py` — Exchange loop
  - Broad-crested weir formula: Q_ex = C_w · L · √(2g) · (Δh)^1.5
  - Applies Q_ex as lateral sink to 1D, point source to 2D
  - Bidirectional: both overtopping and return flow
- `src/physics/engine.py` — SimulationEngine
  - `mode: Literal['1d', '2d', '1d2d']`
  - `async def run(steps) -> AsyncIterator[SimulationState]`
  - Runs solver in thread pool (not blocking event loop)
  - Yields state every N steps (configurable broadcast_interval)
  - Handles pause/resume/reset

Files to modify:
- `src/physics/base.py` — finalize AbstractSolver with pause/resume

Acceptance criteria:
- [ ] 2D-only mode: same results as Sprint 2 solver
- [ ] 1D-only mode: same results as Sprint 3 solver
- [ ] Coupled mode: mass globally conserved (1D + 2D + exchange)
- [ ] Engine yields state at correct intervals without blocking

---

### Sprint 5 — FastAPI Refactor
**Goal**: Decompose the 1,945-line server.py into clean route modules.

Files to create:
- `src/main.py` — App factory, lifespan (startup/shutdown), CORS, router mount
- `src/api/router.py` — Aggregates all sub-routers under /api/v1
- `src/api/routes/simulation.py` — POST /run, GET /state, POST /reset, POST /pause
- `src/api/routes/prediction.py` — POST /predict, GET /prediction/history
- `src/api/routes/terrain.py` — GET /terrain, GET /tiles/{z}/{x}/{y}
- `src/api/routes/network.py` — GET /network, POST /network/cross-section, PUT /network
- `src/api/routes/gis.py` — POST /import, GET /mesh/{id}, GET /layers
- `src/api/websocket/manager.py` — Connection pool, broadcast, heartbeat
- `src/api/websocket/handlers.py` — Routes WS messages to engine actions

WebSocket message protocol (discriminated union):
```json
{ "type": "simulation_update", "step": 42, "mode": "1d2d",
  "data": { "waterDepth": [[...]], "discharge": [...], "floodRisk": [[...]] } }
{ "type": "simulation_complete", "totalSteps": 1000, "stats": {...} }
{ "type": "error", "code": "SOLVER_DIVERGED", "message": "..." }
```

Files to deprecate:
- `src/server.py` — replaced by main.py + routes/

Acceptance criteria:
- [ ] All existing API endpoints reachable at same paths
- [ ] WebSocket streams updates with correct message schema
- [ ] Server starts cleanly via `uvicorn src.main:app`
- [ ] Health check passes at GET /health

---

### Sprint 6 — Angular 20 Frontend Scaffold
**Goal**: Angular 20 project, routing, Signal Store, WebSocket service.

Setup:
```bash
ng new nalarbanjir-ui --routing --style scss --standalone
cd nalarbanjir-ui
ng add @angular/material
npm install @ngrx/signals three @types/three leaflet @types/leaflet
```

Files to create:
- `frontend/src/app/app.config.ts` — provideRouter, provideHttpClient, provideExperimentalZonelessChangeDetection
- `frontend/src/app/app.routes.ts` — lazy-loaded routes: /dashboard, /simulation, /analytics, /gis
- `frontend/src/app/core/services/websocket.service.ts` — RxJS WebSocketSubject, typed message stream
- `frontend/src/app/core/services/simulation.service.ts` — HTTP calls for run/reset/state
- `frontend/src/app/core/services/terrain.service.ts` — DEM + tile loading
- `frontend/src/app/core/store/simulation.store.ts` — NgRx Signal Store with full state shape
- `frontend/src/app/features/dashboard/dashboard.component.ts` — 3-panel layout (controls | viewport | analytics)
- `frontend/src/app/features/controls/model-mode/model-mode.component.ts` — 1D / 2D / Coupled selector
- `frontend/src/environments/` — dev/prod API URLs

Acceptance criteria:
- [ ] `ng build` succeeds with zero errors
- [ ] App loads at localhost:4200 with dashboard layout
- [ ] WebSocket service connects and emits typed messages
- [ ] Signal Store updates trigger Angular change detection (zoneless)

---

### Sprint 7 — Viewport, Channel Profile, Analytics
**Goal**: Build the visual components that make the simulation tangible.

#### Three.js 3D Viewport
- `three-viewport.component.ts` — hosts canvas, scoped SceneService, effect() reacts to store.waterDepth
- `scene.service.ts` — WebGLRenderer, PerspectiveCamera, OrbitControls, animation loop
- `terrain-mesh.service.ts` — DTM JSON → PlaneGeometry with displacement
- `water-surface.service.ts` — animated water mesh, custom GLSL shader:
  - Vertex: displace by depth from signal, wave normal animation
  - Fragment: Fresnel transparency, depth-based color (cyan→blue→red for flood)
- `flow-arrows.service.ts` — InstancedMesh of arrows, magnitude → scale, direction → rotation

#### 2D Map View (Leaflet)
- `map-2d.component.ts` — Leaflet base map, flood depth as color-coded overlay canvas layer
- Toggleable: terrain, flood extent, risk zones, flow vectors

#### Channel Profile View (1D-specific)
- `channel-profile.component.ts` — SVG rendering of selected cross-section
  - Bed profile (surveyed z points)
  - Current water surface line (h from 1D solver state)
  - Water area shaded in blue
  - Shown only when mode = '1d' or '1d2d'

#### Analytics Panel
- `hydrograph.component.ts` — Chart.js line chart: Q(t) at selected gauge station
- `flood-chart.component.ts` — Inundated area over time
- `risk-summary.component.ts` — Current step risk stats: max depth, % area flooded by category

Acceptance criteria:
- [ ] 3D viewport renders terrain + water mesh, updates at ≥ 10fps during simulation
- [ ] Water shader shows correct depth-based coloring
- [ ] Channel profile SVG updates live during 1D simulation
- [ ] Hydrograph updates in real-time via WebSocket

---

### Sprint 8 — ML FloodNet Integration
**Goal**: Wire FloodNet into the new architecture with proper feature extraction and UQ.

Files to modify/create:
- `src/ml/features.py` — extract [h, u, v, dz/dx, dz/dy, rainfall, soil_moisture, land_use, Q_upstream, hour_sin] from SimulationState
- `src/ml/floodnet/model.py` — keep existing architecture, adapt input/output to new state schema
- `src/ml/floodnet/predictor.py` — MC-Dropout (T=50 passes), returns mean + std per cell
- `src/ml/floodnet/trainer.py` — adapt to synthetic data generator (run N random physics simulations, collect states → labels)
- `src/api/routes/prediction.py` — POST /predict accepts SimulationState, returns RiskGrid + confidence

Acceptance criteria:
- [ ] Feature extraction handles all three solver modes (1D, 2D, coupled)
- [ ] MC-Dropout produces non-degenerate uncertainty estimates
- [ ] Prediction endpoint returns within 200ms on CPU

---

### Sprint 9 — Docker + Nginx + Angular Build
**Goal**: Container-ready deployment serving Angular SPA + FastAPI backend.

Files to create/modify:
- `Dockerfile` — multi-stage: `node:22` build Angular, `python:3.11-slim` for FastAPI
- `docker-compose.yml` — backend (port 8000) + frontend-nginx (port 80) + optional ml-training
- `frontend/nginx.conf`:
  ```nginx
  location /api/  { proxy_pass http://backend:8000; }
  location /ws    { proxy_pass http://backend:8000; proxy_http_version 1.1;
                    proxy_set_header Upgrade $http_upgrade; }
  location /      { root /usr/share/nginx/html; try_files $uri /index.html; }
  ```
- `frontend/src/environments/environment.prod.ts` — API URL = '' (relative, proxied via Nginx)

Acceptance criteria:
- [ ] `docker-compose up` starts all services cleanly
- [ ] Angular SPA loads at http://localhost
- [ ] WebSocket connects through Nginx proxy
- [ ] Health check passes: GET /health returns 200

---

## File Change Summary

| File | Action | Sprint |
|------|--------|--------|
| `config/model_config.yaml` | Restructure | 1 |
| `src/core/config.py` | Create | 1 |
| `src/core/exceptions.py` | Create | 1 |
| `src/physics/base.py` | Create | 1 |
| `src/physics/state.py` | Create | 1 |
| `src/api/schemas/` | Create | 1 |
| `src/physics/shallow_water.py` | Deprecate | 2 |
| `src/physics/solver_2d/` | Create (4 files) | 2 |
| `src/physics/rainfall.py` | Create | 2 |
| `src/physics/solver_1d/` | Create (5 files) | 3 |
| `src/physics/coupled/` | Create (2 files) | 4 |
| `src/physics/engine.py` | Create | 4 |
| `src/server.py` | Deprecate | 5 |
| `src/main.py` | Create | 5 |
| `src/api/routes/` | Create (5 files) | 5 |
| `src/api/websocket/` | Create (2 files) | 5 |
| `frontend/` | Full Angular 20 rebuild | 6–7 |
| `src/ml/features.py` | Create | 8 |
| `src/ml/floodnet/` | Modify (3 files) | 8 |
| `Dockerfile` | Rebuild | 9 |
| `docker-compose.yml` | Rebuild | 9 |

---

## Testing Strategy

Each sprint includes tests in `tests/`:

| Sprint | Test file | What it checks |
|--------|-----------|----------------|
| 1 | `test_config.py` | Config loads, invalid config raises |
| 2 | `test_solver_2d.py` | Mass conservation, dam-break, wet/dry |
| 3 | `test_solver_1d.py` | Backwater curve, junction balance |
| 4 | `test_coupler.py` | Global mass conservation, exchange flux |
| 5 | `test_api.py` | All endpoints, WebSocket protocol |
| 6–7 | (Angular) | `ng test` unit tests per service/component |
| 8 | `test_prediction.py` | Feature shape, UQ non-degenerate |
| 9 | (Docker) | `docker-compose up` health checks |
