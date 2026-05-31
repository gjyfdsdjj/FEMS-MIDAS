from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from services.rcf_anomaly_service import run_rcf_temperature_analysis

router = APIRouter(prefix="/api/v1/rcf", tags=["rcf"])


@router.get("/temperature/{factory_id}")
async def analyze_temperature_with_rcf(
    factory_id: int,
    limit: int = Query(default=100),
    db: AsyncSession = Depends(get_db),
):
    return await run_rcf_temperature_analysis(
        db=db,
        factory_id=factory_id,
        limit=limit,
    )