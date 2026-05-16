from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from backend.services.readonly_service import get_readonly_data


router = APIRouter(prefix="/api/v1/readonly", tags=["readonly"])


@router.get("/{token}")
async def get_readonly_factory_info(token: str, db: AsyncSession = Depends(get_db)):
    result = await get_readonly_data(db, token)

    if isinstance(result, JSONResponse):
        return result

    return {
        "success": True,
        "message": "ok",
        "data": result,
    }
