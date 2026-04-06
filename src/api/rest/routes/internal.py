import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import get_db
from src.core.services.user import get_user
from src.schemas.user import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal"])


@router.get("/users/by-identifier", response_model=UserResponse)
async def get_user_by_identifier(
    identifier: str = Query(..., description="Email or phone number"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a user record by email address or phone number.

    Internal endpoint intended for service-to-service calls where a user
    needs to be resolved by a non-primary-key identifier. Not exposed to
    end users directly.

    Args:
        identifier: Email address or phone number passed as a query parameter.
        db:         Async database session injected by ``get_db``.

    Returns:
        UserResponse: Serialised user record.

    Raises:
        HTTPException 404: When no user matches the supplied identifier.
        HTTPException 500: When an unexpected error occurs during lookup.
    """
    logger.info("Internal user lookup requested", extra={"identifier": identifier})
    try:
        user = await get_user(identifier, db)

        if not user:
            logger.warning(
                "User not found for identifier",
                extra={"identifier": identifier},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        logger.info(
            "User resolved successfully",
            extra={"identifier": identifier, "user_id": user.id},
        )
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error during internal user lookup",
            extra={"identifier": identifier, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal lookup failed",
        )