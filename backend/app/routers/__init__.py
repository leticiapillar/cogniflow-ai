from app.routers.document import router as document_router
from app.routers.health import router as health_router
from app.routers.mind_map import router as mind_map_router
from app.routers.tutor import router as tutor_router

__all__ = ["document_router", "health_router", "mind_map_router", "tutor_router"]
