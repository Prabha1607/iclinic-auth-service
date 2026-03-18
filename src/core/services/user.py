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


def is_email(value: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, value))


async def create_user(db: AsyncSession, user_data: UserCreate):
    try:
        hashed_password = get_password_hash(user_data.password)
        user_dict = user_data.model_dump(exclude={"patient_profile"})
        user_dict["password"] = hashed_password
        user_id = await insert_user(db, user_dict)

        if user_data.patient_profile:
            profile_data = user_data.patient_profile.model_dump()
            await insert_patient_profile(db, user_id, profile_data)

        await db.commit()
        user = await get_instance_by_id(db=db, model=User, id=user_id)
        return user

    except Exception as e:
        await db.rollback()
        raise e


async def create_provider_service(db: AsyncSession, provider_data: ProviderCreate):
    try:
        hashed_password = get_password_hash(provider_data.password)

        user_dict = provider_data.model_dump(
            exclude={"provider_profile", "patient_profile"}
        )
        user_dict["password"] = hashed_password

        user_id = await insert_user(db, user_dict)

        if provider_data.provider_profile:
            profile_data = provider_data.provider_profile.model_dump()
            await insert_provider_profile(
                db=db, user_id=user_id, profile_data=profile_data
            )

        await db.commit()

        result = await db.execute(
            select(User)
            .options(selectinload(User.provider_profile))
            .where(User.id == user_id)
        )
        provider = result.scalar_one()

        return provider

    except Exception as e:
        await db.rollback()
        raise e


async def get_user_by_email(email: str, db: AsyncSession):
    try:
        user = await get_instance_by_any(db=db, model=User, data={"email": email})
        return user
    except Exception:
        raise Exception("Failed to fetch user by email")


async def get_user_by_phone(phone_no: str, db: AsyncSession):
    try:
        user = await get_instance_by_any(db=db, model=User, data={"phone_no": phone_no})
        return user
    except Exception:
        raise Exception("Failed to fetch user by phone")


async def get_user(identifier: str, db: AsyncSession):
    try:
        if is_email(identifier):
            user = await get_user_by_email(identifier, db)
        else:
            user = await get_user_by_phone(identifier, db)
        return user
    except Exception:
        raise Exception("Failed to fetch user")


async def is_revoked(jti: UUID, db: AsyncSession):
    try:
        refresh_token = await get_instance_by_any(
            model=RefreshToken, db=db, data={"token_id": jti}
        )
        if not refresh_token:
            return True
        if refresh_token.is_revoked:
            return True
        if refresh_token.expire_at < datetime.now(UTC):
            refresh_token.is_revoked = True
            await commit_transaction(db=db)
            return True
        return False
    except Exception:
        raise Exception("Token validation failed")


async def make_it_revoked(db: AsyncSession, jti: str):
    try:
        uuid_jti = to_uuid(jti)
        refresh_token = await get_instance_by_any(
            model=RefreshToken, db=db, data={"token_id": uuid_jti}
        )
        if not refresh_token:
            raise HTTPException(status_code=403, detail="Token not found")
        if refresh_token.is_revoked:
            return
        refresh_token.is_revoked = True
        await commit_transaction(db=db)
    except HTTPException:
        raise
    except Exception:
        raise Exception("Failed to revoke token")


async def insert_refresh_token(db: AsyncSession, jti: str):
    try:
        uuid_jti = to_uuid(jti)
        await insert_instance(model=RefreshToken, db=db, **{"token_id": uuid_jti})
        return True
    except Exception:
        raise Exception("Failed to insert refresh token")


async def get_roles(db: AsyncSession):
    try:
        roles = await bulk_get_instance(model=Role, db=db)
        return [{"id": role.id, "name": role.role_name} for role in roles]
    except Exception:
        raise Exception("Failed to fetch roles")


async def get_all_patients(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    is_active: bool | None = None,
):
    result = await get_patients(
        db=db, page=page, page_size=page_size, is_active=is_active
    )
    return result


async def get_providers(
    db: AsyncSession, page: int, page_size: int, is_active: bool | None
):
    providers = await get_all_providers(db, page, page_size, is_active)
    return providers


async def get_providers_by_type_service(
    db: AsyncSession, appointment_type_id: int, is_active: bool | None = None
):
    return await get_providers_by_type_repo(
        db=db, appointment_type_id=appointment_type_id, is_active=is_active
    )


async def get_patient_by_id_service(
    db: AsyncSession, id: int, is_active: bool | None = None
):
    return await get_patient_by_id_repo(db=db, id=id, is_active=is_active)

async def get_user_by_id_service(
    db: AsyncSession, id: int, is_active: bool | None = None
):
    return await get_user_by_id_repo(db=db, id=id, is_active=is_active)



async def update_user_service(db: AsyncSession, user_id: int, user_data: UserUpdate):
    data = user_data.model_dump(exclude_unset=True)

    profile_data = None
    if user_data.patient_profile is not None:
        profile_data = user_data.patient_profile.model_dump(exclude_unset=True)
        if not profile_data:
            profile_data = None

    data.pop("patient_profile", None)

    if "password" in data:
        data["password"] = get_password_hash(data["password"])

    return await update_user_with_profile_repo(
        db=db, user_id=user_id, user_data=data, profile_data=profile_data
    )


async def get_all_providers_service(db: AsyncSession, is_active: bool | None = None):
    providers = await get_all_providers_repo(db=db, is_active=is_active)

    return providers
