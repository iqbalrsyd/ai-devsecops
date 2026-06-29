from fastapi import APIRouter

from app.api.pipeline import router as pipeline_router

router = APIRouter(prefix="/api")
router.include_router(pipeline_router)