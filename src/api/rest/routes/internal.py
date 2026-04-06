from fastapi import APIRouter, Depends, HTTPException, Query
from src.schemas.user import UserResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.rest.dependencies import get_db
from src.core.services.user import get_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal"])


@router.get("/users/by-identifier", response_model=UserResponse)
async def get_user_by_identifier(
    identifier: str = Query(..., description="Email or phone number"),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_user(identifier, db)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Internal user lookup failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Internal lookup failed")

