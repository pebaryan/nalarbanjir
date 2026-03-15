"""
Nalarbanjir API layer.

The public surface of this package is the FastAPI application created in
src.main.  Route modules and schemas live in sub-packages:

  src.api.routes.*          — HTTP route modules (APIRouter instances)
  src.api.websocket.*       — WebSocket manager + endpoint
  src.api.schemas.*         — Pydantic v2 request/response models
  src.api.serializers       — physics state → schema converters
  src.api.dependencies      — FastAPI Depends helpers
"""
