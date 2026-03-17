import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import get_db
from src.core.services.user import get_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal"])


@router.get("/users/by-identifier")
async def get_user_by_identifier(
    identifier: str = Query(..., description="Email or phone number"),
    db: AsyncSession = Depends(get_db),
):

    try:
        user = await get_user(identifier, db)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_no": user.phone_no,
            "role_id": user.role_id,
            "is_active": user.is_active,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Internal user lookup failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Internal lookup failed")
