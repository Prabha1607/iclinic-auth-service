import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from src.schemas.otp import SendOtpRequest,VerifyOtpRequest
from src.api.rest.dependencies import get_db
from src.config.hashing import verify_password
from src.config.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
)
from src.config.otp_email import send_otp_email
from src.config.settings import settings
from src.core.services.otp import create_otp, verify_otp
from src.core.services.user import (
    create_user,
    get_user,
    insert_refresh_token,
    is_revoked,
    make_it_revoked,
)
from src.schemas.auth import LoginResponse, TokenRefreshResponse, UserPayload, VerifyTokenResponse
from src.schemas.user import UserCreate, UserLogin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/send-otp", status_code=status.HTTP_200_OK)
async def send_otp(body: SendOtpRequest, background_tasks: BackgroundTasks):
    """
    Generate a one-time password and dispatch it to the supplied email address.

    The OTP is created synchronously and the email is sent as a background
    task so the response is returned immediately. The response is intentionally
    ambiguous — it does not confirm whether the email address is registered —
    to prevent user enumeration.

    Args:
        body:             Request payload containing the ``email`` to send the OTP to.
        background_tasks: FastAPI background task runner used to dispatch the email
                          without blocking the response.

    Returns:
        dict: A generic confirmation message regardless of whether the email exists.
    """
    logger.info("OTP send requested", extra={"email": body.email})
    try:
        code = create_otp(body.email)
        background_tasks.add_task(send_otp_email, body.email, code)
        logger.info("OTP queued for delivery", extra={"email": body.email})
        return {"message": "If that email is valid, a verification code has been sent."}
    except Exception as e:
        logger.error("Failed to create or queue OTP", extra={"email": body.email, "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP. Please try again.",
        )


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp_route(body: VerifyOtpRequest):
    """
    Verify a one-time password submitted by the user.

    Validates the OTP against the code previously issued for the given email
    address. A successful response indicates the email is verified and the
    user may proceed to registration.

    Args:
        body: Request payload containing ``email`` and the ``otp`` code to verify.

    Returns:
        dict: Verification outcome with ``verified: True`` and a descriptive message.

    Raises:
        HTTPException 400: When the OTP is invalid, expired, or does not match.
    """
    logger.info("OTP verification requested", extra={"email": body.email})
    try:
        success, reason = verify_otp(body.email, body.otp)

        if not success:
            logger.warning(
                "OTP verification failed",
                extra={"email": body.email, "reason": reason},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=reason,
            )

        logger.info("OTP verified successfully", extra={"email": body.email})
        return {"message": reason, "verified": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error during OTP verification",
            extra={"email": body.email, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OTP verification failed. Please try again.",
        )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.

    Persists a new user record using the supplied details. This endpoint is
    intended to be called only after the user's email has been verified via
    the ``/send-otp`` and ``/verify-otp`` flow. No email is sent here.

    Args:
        user_data: Registration payload containing user details including
                   email, password, and phone number.
        db:        Async database session injected by ``get_db``.

    Returns:
        dict: ``{"message": "Registered successfully! You can now log in."}``

    Raises:
        HTTPException 400: When the email or phone number is already registered.
        HTTPException 500: When a database or unexpected error occurs.
    """
    logger.info("User registration requested", extra={"email": user_data.email})
    try:
        await create_user(db, user_data)
        logger.info("User registered successfully", extra={"email": user_data.email})
        return {"message": "Registered successfully! You can now log in."}
    except IntegrityError:
        logger.warning(
            "Registration rejected — duplicate email or phone",
            extra={"email": user_data.email},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or phone number already exists",
        )
    except SQLAlchemyError as e:
        logger.error(
            "Database error during registration",
            extra={"email": user_data.email, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred",
        )
    except Exception as e:
        logger.error(
            "Unexpected error during registration",
            extra={"email": user_data.email, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong",
        )


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login_user(
    request: Request,
    response: Response,
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate a user and issue access and refresh tokens.

    Validates the supplied credentials, generates a JWT access token and a
    refresh token, persists the refresh token ID for revocation tracking, and
    sets both tokens as ``HttpOnly`` cookies. The tokens are also returned in
    the response body for clients that cannot read cookies.

    Args:
        request:   Incoming HTTP request (reserved for future use).
        response:  HTTP response object used to attach the token cookies.
        user_data: Login payload containing ``identifier`` (email or phone)
                   and ``password``.
        db:        Async database session injected by ``get_db``.

    Returns:
        dict: Authentication result containing ``access_token``, ``refresh_token``,
              and their respective ``max_age`` values in seconds.

    Raises:
        HTTPException 401: When the identifier is not found or the password is incorrect.
        HTTPException 500: When an unexpected error occurs during login.
    """
    logger.info("Login requested", extra={"identifier": user_data.identifier})
    try:
        user = await get_user(user_data.identifier, db)

        if not user or not verify_password(user_data.password, user.password):
            logger.warning(
                "Login failed — invalid credentials",
                extra={"identifier": user_data.identifier},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        payload = {
            "id": user.id,
            "email": user.email,
            "name": f"{user.first_name} {user.last_name}",
            "role_id": user.role_id,
            "phone_number": user.phone_no,
        }

        access_token, _ = await create_access_token(payload=payload)
        refresh_token, refresh_token_id = await create_refresh_token(payload=payload)

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

        logger.info("User logged in successfully", extra={"user_id": user.id})
        return LoginResponse(
            message="Authentication Successful!",
            access_token=access_token,
            refresh_token=refresh_token,
            access_max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error during login",
            extra={"identifier": user_data.identifier, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong during login",
        )


@router.get("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Log out the current user and revoke their refresh token.

    Reads the refresh token from cookies, verifies it, and marks the
    associated JTI as revoked so it cannot be used for future token
    rotation. Both access and refresh token cookies are cleared regardless
    of whether the token is valid — an invalid or missing token still
    results in a successful logout.

    Args:
        request:  Incoming HTTP request used to read the ``refresh_token`` cookie.
        response: HTTP response object used to delete the token cookies.
        db:       Async database session injected by ``get_db``.

    Returns:
        dict: ``{"message": "Logout successful"}``

    Raises:
        HTTPException 500: When an unexpected error occurs during logout.
    """
    logger.info("Logout requested")
    try:
        refresh_token = request.cookies.get("refresh_token")

        if refresh_token:
            try:
                payload = await verify_refresh_token(refresh_token)
                if payload:
                    await make_it_revoked(db=db, jti=payload.get("jti"))
                    logger.info(
                        "Refresh token revoked on logout",
                        extra={"user_id": payload.get("id")},
                    )
            except Exception as e:
                logger.warning(
                    "Logout with invalid or expired refresh token — proceeding with cookie deletion",
                    extra={"error": str(e)},
                )

        response.delete_cookie(key="access_token", path="/", secure=True, samesite="none")
        response.delete_cookie(key="refresh_token", path="/", secure=True, samesite="none")

        logger.info("Logout completed — cookies cleared")
        return {"message": "Logout successful"}
    except Exception as e:
        logger.error("Unexpected error during logout", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed",
        )


@router.post("/refresh", response_model=TokenRefreshResponse, status_code=status.HTTP_200_OK)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Rotate the refresh token and issue a new access token.

    Implements refresh token rotation: the current refresh token is verified,
    checked against the revocation list, immediately revoked, and replaced
    with a freshly issued pair. The new tokens are set as ``HttpOnly`` cookies
    and returned in the response body.

    Args:
        request:  Incoming HTTP request used to read the ``refresh_token`` cookie.
        response: HTTP response object used to attach the new token cookies.
        db:       Async database session injected by ``get_db``.

    Returns:
        dict: New ``access_token``, ``refresh_token``, ``token_type``, and
              ``access_max_age`` in seconds.

    Raises:
        HTTPException 401: When the refresh token cookie is missing.
        HTTPException 403: When the refresh token is invalid or has been revoked.
        HTTPException 500: When an unexpected error occurs during token rotation.
    """
    logger.info("Token refresh requested")
    try:
        refresh_token_cookie = request.cookies.get("refresh_token")

        if not refresh_token_cookie:
            logger.warning("Token refresh attempted with no refresh token cookie")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token missing",
            )

        payload = await verify_refresh_token(refresh_token_cookie)
        if payload is None:
            logger.warning("Token refresh failed — invalid refresh token")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid refresh token",
            )

        jti = payload.get("jti")

        if await is_revoked(jti=jti, db=db):
            logger.warning(
                "Revoked refresh token used in rotation attempt",
                extra={"user_id": payload.get("id")},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Refresh token revoked",
            )

        await make_it_revoked(db=db, jti=jti)

        token_data = {
            "id": payload.get("id"),
            "email": payload.get("email"),
            "name": payload.get("name"),
            "phone_number": payload.get("phone_number"),
            "role_id": payload.get("role_id"),
        }

        new_access_token, _ = await create_access_token(payload=token_data)
        new_refresh_token, new_refresh_token_id = await create_refresh_token(payload=token_data)

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

        logger.info(
            "Token rotation completed successfully",
            extra={"user_id": payload.get("id")},
        )
        return TokenRefreshResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            access_max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error during token refresh", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed",
        )


@router.get("/verify", response_model=VerifyTokenResponse, status_code=status.HTTP_200_OK)
async def verify_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify the current session and silently refresh the access token if needed.

    Attempts to validate the access token cookie first. If it is valid, the
    current user payload is returned immediately with no token rotation.
    If the access token is missing or expired, the refresh token is validated
    and checked against the revocation list. On success a new access token is
    issued silently and set as a cookie, extending the session without requiring
    the user to log in again.

    Args:
        request:  Incoming HTTP request used to read the token cookies.
        response: HTTP response object used to attach the refreshed access token cookie.
        db:       Async database session injected by ``get_db``.

    Returns:
        dict: ``{"valid": True, "access_token": <token>, "user": <payload>}``
              with an optional ``access_max_age`` field when the token was silently
              refreshed.

    Raises:
        HTTPException 401: When both tokens are missing, invalid, expired, or revoked.
    """
    logger.info("Token verification requested")
    try:
        access_token = request.cookies.get("access_token")
        refresh_token_cookie = request.cookies.get("refresh_token")

        if access_token:
            try:
                payload = await verify_access_token(access_token)
                if payload:
                    logger.info(
                        "Access token verified successfully",
                        extra={"user_id": payload.get("id")},
                    )
                    return VerifyTokenResponse(
                        valid=True,
                        access_token=access_token,
                        user=UserPayload(**{
                            "id": payload.get("id"),
                            "email": payload.get("email"),
                            "name": payload.get("name"),
                            "role_id": payload.get("role_id"),
                            "phone_number": payload.get("phone_number"),
                        }),
                    )
            except Exception as e:
                logger.warning(
                    "Access token invalid — falling back to refresh token",
                    extra={"error": str(e)},
                )

        if not refresh_token_cookie:
            logger.warning("Verification failed — no valid token cookies present")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        payload = await verify_refresh_token(refresh_token_cookie)
        if payload is None:
            logger.warning("Verification failed — refresh token invalid or expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        if await is_revoked(jti=payload.get("jti"), db=db):
            logger.warning(
                "Verification failed — refresh token revoked",
                extra={"user_id": payload.get("id")},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session revoked",
            )

        token_data = {
            "id": payload.get("id"),
            "email": payload.get("email"),
            "name": payload.get("name"),
            "phone_number": payload.get("phone_number"),
            "role_id": payload.get("role_id"),
        }

        new_access_token, _ = await create_access_token(payload=token_data)

        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        logger.info(
            "Silent access token refresh completed on verify",
            extra={"user_id": payload.get("id")},
        )
        return VerifyTokenResponse(
            valid=True,
            access_token=new_access_token,
            user=UserPayload(**token_data),
            access_max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error during token verification", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verification failed",
        )
    

