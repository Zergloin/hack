from fastapi import APIRouter

from app.api.municipalities import router as municipalities_router
from app.api.population import router as population_router
from app.api.demographics import router as demographics_router
from app.api.forecast import router as forecast_router
from app.api.map_data import router as map_router
from app.api.reports import router as reports_router
from app.api.chat import router as chat_router

api_router = APIRouter()

api_router.include_router(municipalities_router, tags=["municipalities"])
api_router.include_router(population_router, prefix="/population", tags=["population"])
api_router.include_router(demographics_router, prefix="/demographics", tags=["demographics"])
api_router.include_router(forecast_router, prefix="/forecast", tags=["forecast"])
api_router.include_router(map_router, prefix="/map", tags=["map"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
