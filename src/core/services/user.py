import logging
import re
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import UUID, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config.hashing import get_password_hash
from src.data.models.postgres.refresh_token import RefreshToken
from src.data.models.postgres.role import Role
from src.data.models.postgres.user import User
from src.data.repositories.generic_crud import (
    bulk_get_instance,
    commit_transaction,
    get_instance_by_any,
    get_instance_by_id,
    insert_instance,
)
from src.data.repositories.users import (
    get_all_providers,
    get_all_providers_repo,
    get_patient_by_id_repo,
    get_patients,
    get_providers_by_type_repo,
    get_user_by_id_repo,
    insert_patient_profile,
    insert_provider_profile,
    insert_user,
    update_user_with_profile_repo,
)
from src.schemas.user import ProviderCreate, UserCreate, UserUpdate
from src.utils.to_uuid import to_uuid

logger = logging.getLogger(__name__)


def is_email(value: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, value))


async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    logger.info("Creating user", extra={"email": user_data.email})
    try:
        hashed_password = get_password_hash(user_data.password)
        user_dict = user_data.model_dump(exclude={"patient_profile"})
        user_dict["password"] = hashed_password

        user_id = await insert_user(db, user_dict)

        if user_data.patient_profile:
            profile_data = user_data.patient_profile.model_dump()
            await insert_patient_profile(db, user_id, profile_data)
            logger.info("Patient profile inserted", extra={"user_id": user_id})

        await db.commit()
        user = await get_instance_by_id(db=db, model=User, id=user_id)
        logger.info("User created successfully", extra={"user_id": user_id, "email": user_data.email})
        return user
    except Exception as e:
        logger.error("Failed to create user", extra={"email": user_data.email, "error": str(e)})
        await db.rollback()
        raise


async def create_provider_service(db: AsyncSession, provider_data: ProviderCreate) -> User:
    logger.info("Creating provider", extra={"email": provider_data.email})
    try:
        hashed_password = get_password_hash(provider_data.password)
        user_dict = provider_data.model_dump(exclude={"provider_profile", "patient_profile"})
        user_dict["password"] = hashed_password

        user_id = await insert_user(db, user_dict)

        if provider_data.provider_profile:
            profile_data = provider_data.provider_profile.model_dump()
            await insert_provider_profile(db=db, user_id=user_id, profile_data=profile_data)
            logger.info("Provider profile inserted", extra={"user_id": user_id})

        await db.commit()

        result = await db.execute(
            select(User)
            .options(selectinload(User.provider_profile))
            .where(User.id == user_id)
        )
        provider = result.scalar_one()
        logger.info(
            "Provider created successfully",
            extra={"user_id": user_id, "email": provider_data.email},
        )
        return provider
    except Exception as e:
        logger.error(
            "Failed to create provider",
            extra={"email": provider_data.email, "error": str(e)},
        )
        await db.rollback()
        raise


async def get_user_by_email(email: str, db: AsyncSession) -> User | None:
    logger.info("Fetching user by email", extra={"email": email})
    try:
        user = await get_instance_by_any(db=db, model=User, data={"email": email})
        if not user:
            logger.warning("No user found for email", extra={"email": email})
        return user
    except Exception as e:
        logger.error("Failed to fetch user by email", extra={"email": email, "error": str(e)})
        raise


async def get_user_by_phone(phone_no: str, db: AsyncSession) -> User | None:
    logger.info("Fetching user by phone", extra={"phone_no": phone_no})
    try:
        user = await get_instance_by_any(db=db, model=User, data={"phone_no": phone_no})
        if not user:
            logger.warning("No user found for phone", extra={"phone_no": phone_no})
        return user
    except Exception as e:
        logger.error(
            "Failed to fetch user by phone",
            extra={"phone_no": phone_no, "error": str(e)},
        )
        raise


async def get_user(identifier: str, db: AsyncSession) -> User | None:
    logger.info("Resolving user by identifier", extra={"identifier": identifier})
    try:
        if is_email(identifier):
            user = await get_user_by_email(identifier, db)
        else:
            user = await get_user_by_phone(identifier, db)
        return user
    except Exception as e:
        logger.error(
            "Failed to resolve user by identifier",
            extra={"identifier": identifier, "error": str(e)},
        )
        raise


async def is_revoked(jti: UUID, db: AsyncSession) -> bool:
    logger.info("Checking token revocation status", extra={"jti": str(jti)})
    try:
        refresh_token = await get_instance_by_any(
            model=RefreshToken, db=db, data={"token_id": jti}
        )

        if not refresh_token:
            logger.warning("Refresh token not found — treating as revoked", extra={"jti": str(jti)})
            return True

        if refresh_token.is_revoked:
            logger.warning("Refresh token is already revoked", extra={"jti": str(jti)})
            return True

        if refresh_token.expire_at < datetime.now(UTC):
            logger.warning("Refresh token has expired — marking as revoked", extra={"jti": str(jti)})
            refresh_token.is_revoked = True
            await commit_transaction(db=db)
            return True

        logger.info("Refresh token is valid", extra={"jti": str(jti)})
        return False
    except Exception as e:
        logger.error(
            "Failed to check token revocation status",
            extra={"jti": str(jti), "error": str(e)},
        )
        raise


async def make_it_revoked(db: AsyncSession, jti: str) -> None:
    logger.info("Revoking refresh token", extra={"jti": jti})
    try:
        uuid_jti = to_uuid(jti)
        refresh_token = await get_instance_by_any(
            model=RefreshToken, db=db, data={"token_id": uuid_jti}
        )

        if not refresh_token:
            logger.warning("Refresh token not found for revocation", extra={"jti": jti})
            raise HTTPException(status_code=403, detail="Token not found")

        if refresh_token.is_revoked:
            logger.warning("Refresh token already revoked — skipping", extra={"jti": jti})
            return

        refresh_token.is_revoked = True
        await commit_transaction(db=db)
        logger.info("Refresh token revoked successfully", extra={"jti": jti})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to revoke refresh token",
            extra={"jti": jti, "error": str(e)},
        )
        raise


async def insert_refresh_token(db: AsyncSession, jti: str) -> bool:
    logger.info("Inserting refresh token", extra={"jti": jti})
    try:
        uuid_jti = to_uuid(jti)
        await insert_instance(model=RefreshToken, db=db, **{"token_id": uuid_jti})
        logger.info("Refresh token inserted successfully", extra={"jti": jti})
        return True
    except Exception as e:
        logger.error(
            "Failed to insert refresh token",
            extra={"jti": jti, "error": str(e)},
        )
        raise


async def get_roles(db: AsyncSession) -> list[dict]:
    logger.info("Fetching all roles")
    try:
        roles = await bulk_get_instance(model=Role, db=db)
        result = [{"id": role.id, "name": role.role_name} for role in roles]
        logger.info("Roles fetched successfully", extra={"count": len(result)})
        return result
    except Exception as e:
        logger.error("Failed to fetch roles", extra={"error": str(e)})
        raise


async def get_all_patients(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    is_active: bool | None = None,
) -> list:
    logger.info(
        "Fetching all patients",
        extra={"page": page, "page_size": page_size, "is_active": is_active},
    )
    try:
        result = await get_patients(db=db, page=page, page_size=page_size, is_active=is_active)
        logger.info(
            "Patients fetched successfully",
            extra={"count": len(result), "page": page},
        )
        return result
    except Exception as e:
        logger.error("Failed to fetch patients", extra={"error": str(e)})
        raise


async def get_providers(
    db: AsyncSession, page: int, page_size: int, is_active: bool | None
) -> list:
    logger.info(
        "Fetching paginated providers",
        extra={"page": page, "page_size": page_size, "is_active": is_active},
    )
    try:
        providers = await get_all_providers(db, page, page_size, is_active)
        logger.info(
            "Paginated providers fetched successfully",
            extra={"count": len(providers), "page": page},
        )
        return providers
    except Exception as e:
        logger.error("Failed to fetch paginated providers", extra={"error": str(e)})
        raise


async def get_providers_by_type_service(
    db: AsyncSession, appointment_type_id: int, is_active: bool | None = None
) -> list:
    logger.info(
        "Fetching providers by appointment type",
        extra={"appointment_type_id": appointment_type_id, "is_active": is_active},
    )
    try:
        providers = await get_providers_by_type_repo(
            db=db, appointment_type_id=appointment_type_id, is_active=is_active
        )
        logger.info(
            "Providers by type fetched successfully",
            extra={"appointment_type_id": appointment_type_id, "count": len(providers)},
        )
        return providers
    except Exception as e:
        logger.error(
            "Failed to fetch providers by appointment type",
            extra={"appointment_type_id": appointment_type_id, "error": str(e)},
        )
        raise


async def get_patient_by_id_service(
    db: AsyncSession, id: int, is_active: bool | None = None
):
    logger.info("Fetching patient by ID", extra={"patient_id": id, "is_active": is_active})
    try:
        patient = await get_patient_by_id_repo(db=db, id=id, is_active=is_active)
        if not patient:
            logger.warning("Patient not found", extra={"patient_id": id})
        else:
            logger.info("Patient fetched successfully", extra={"patient_id": id})
        return patient
    except Exception as e:
        logger.error(
            "Failed to fetch patient by ID",
            extra={"patient_id": id, "error": str(e)},
        )
        raise


async def get_user_by_id_service(
    db: AsyncSession, id: int, is_active: bool | None = None
):
    logger.info("Fetching user by ID", extra={"user_id": id, "is_active": is_active})
    try:
        user = await get_user_by_id_repo(db=db, id=id, is_active=is_active)
        if not user:
            logger.warning("User not found", extra={"user_id": id})
        else:
            logger.info("User fetched successfully", extra={"user_id": id})
        return user
    except Exception as e:
        logger.error(
            "Failed to fetch user by ID",
            extra={"user_id": id, "error": str(e)},
        )
        raise


async def update_user_service(
    db: AsyncSession, user_id: int, user_data: UserUpdate
):
    logger.info("Updating user", extra={"user_id": user_id})
    try:
        data = user_data.model_dump(exclude_unset=True)

        profile_data = None
        if user_data.patient_profile is not None:
            profile_data = user_data.patient_profile.model_dump(exclude_unset=True)
            if not profile_data:
                profile_data = None

        data.pop("patient_profile", None)

        if "password" in data:
            data["password"] = get_password_hash(data["password"])

        result = await update_user_with_profile_repo(
            db=db, user_id=user_id, user_data=data, profile_data=profile_data
        )
        logger.info("User updated successfully", extra={"user_id": user_id})
        return result
    except Exception as e:
        logger.error(
            "Failed to update user",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise


async def get_all_providers_service(
    db: AsyncSession, is_active: bool | None = None
) -> list:
    logger.info("Fetching all providers", extra={"is_active": is_active})
    try:
        providers = await get_all_providers_repo(db=db, is_active=is_active)
        logger.info(
            "All providers fetched successfully",
            extra={"count": len(providers), "is_active": is_active},
        )
        return providers
    except Exception as e:
        logger.error("Failed to fetch all providers", extra={"error": str(e)})
        raise