import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.rest.dependencies import get_db
from src.config.hashing import verify_password
from src.config.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
)
from src.config.settings import settings
from src.core.services.user import (
    create_user,
    get_user,
    insert_refresh_token,
    is_revoked,
    make_it_revoked,
)
from src.schemas.user import UserCreate, UserLogin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        await create_user(db, user_data)
        logger.info("User registered successfully", extra={"email": user_data.email})
        return {"message": "User registered successfully"}

    except IntegrityError:
        logger.warning("Duplicate email or phone", extra={"email": user_data.email})
        raise HTTPException(status_code=400, detail="Email or phone number already exists")

    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error occurred")

    except Exception:
        logger.exception("Unexpected registration error")
        raise HTTPException(status_code=500, detail="Something went wrong")


@router.post("/login")
async def login_user(
    request: Request,
    response: Response,
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_user(user_data.identifier, db)
        if not user or not verify_password(user_data.password, user.password):
            logger.warning(
                "Login failed - invalid credentials",
                extra={"identifier": user_data.identifier},
            )
            raise HTTPException(status_code=401, detail="Invalid credentials")

        payload = {
            "id": user.id,
            "email": user.email,
            "name": f"{user.first_name} {user.last_name}",
            "role_id": user.role_id,
            "phone_number": user.phone_no,
        }

        access_data = await create_access_token(payload=payload)
        refresh_data = await create_refresh_token(payload=payload)

        access_token = access_data[0]
        refresh_token = refresh_data[0]
        refresh_token_id = refresh_data[1]

        await insert_refresh_token(db, refresh_token_id)

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )

        logger.info("User logged in", extra={"user_id": user.id})

        return {
            "message": "Authentication Successful!",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "access_max_age": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "refresh_max_age": settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "Login unexpected error",
            extra={
                "identifier": user_data.identifier,
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        refresh_token = request.cookies.get("refresh_token")

        if refresh_token:
            try:
                payload = await verify_refresh_token(refresh_token)
                if payload:
                    await make_it_revoked(db=db, jti=payload.get("jti"))
                    logger.info("User logged out", extra={"user_id": payload.get("id")})
            except Exception:
                logger.warning("Logout with invalid/expired refresh token")

        response.delete_cookie(key="access_token", path="/", secure=True, samesite="none")
        response.delete_cookie(key="refresh_token", path="/", secure=True, samesite="none")

        return {"message": "Logout successful"}

    except Exception as e:
        logger.error("Logout failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Logout failed")


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        refresh_token_cookie = request.cookies.get("refresh_token")

        if not refresh_token_cookie:
            raise HTTPException(status_code=401, detail="Refresh token missing")

        payload = await verify_refresh_token(refresh_token_cookie)

        if payload is None:
            raise HTTPException(status_code=403, detail="Invalid refresh token")

        jti = payload.get("jti")

        if await is_revoked(jti=jti, db=db):
            logger.warning("Revoked refresh token used", extra={"user_id": payload.get("id")})
            raise HTTPException(status_code=403, detail="Refresh token revoked")

        await make_it_revoked(db=db, jti=jti)

        token_data = {
            "id": payload.get("id"),
            "email": payload.get("email"),
            "name": payload.get("name"),
            "phone_number": payload.get("phone_number"),
            "role_id": payload.get("role_id"),
        }

        # ── Issue a brand-new access token ─────────────────────────────────────────
        access_data = await create_access_token(payload=token_data)
        new_access_token = access_data[0]

        # ── Issue a brand-new refresh token (rotation keeps the session alive) ──────
        new_refresh_data = await create_refresh_token(payload=token_data)
        new_refresh_token = new_refresh_data[0]
        new_refresh_token_id = new_refresh_data[1]

        await insert_refresh_token(db, new_refresh_token_id)

        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )

        logger.info("Access token refreshed (refresh token rotated)", extra={"user_id": payload.get("id")})

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "refresh_token": refresh_token,
            "access_max_age": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Token refresh failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Token refresh failed")


@router.get("/verify")
async def verify_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        access_token = request.cookies.get("access_token")
        refresh_token_cookie = request.cookies.get("refresh_token")

        if access_token:
            try:
                payload = await verify_access_token(access_token)
                if payload:
                    user = {
                        "id": payload.get("id"),
                        "email": payload.get("email"),
                        "name": payload.get("name"),
                        "role_id": payload.get("role_id"),
                        "phone_number": payload.get("phone_number"),
                    }
                    return {"valid": True, "access_token": access_token, "user": user}
            except Exception:
                pass

        if not refresh_token_cookie:
            raise HTTPException(status_code=401, detail="Not authenticated")

        payload = await verify_refresh_token(refresh_token_cookie)

        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        if await is_revoked(jti=payload.get("jti"), db=db):
            raise HTTPException(status_code=401, detail="Session revoked")

        token_data = {
            "id": payload.get("id"),
            "email": payload.get("email"),
            "name": payload.get("name"),
            "phone_number": payload.get("phone_number"),
            "role_id": payload.get("role_id"),
        }

        access_data = await create_access_token(payload=token_data)
        new_access_token = access_data[0]

        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        logger.info("Silent token refresh on /verify", extra={"user_id": payload.get("id")})

        return {
            "valid": True,
            "access_token": new_access_token,
            "user": token_data,
            "refresh_token": refresh_token,
            "access_max_age": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Token verification failed", extra={"error": str(e)})
        raise HTTPException(status_code=401, detail="Verification failed")