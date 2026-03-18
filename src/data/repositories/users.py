from fastapi import HTTPException, status
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.data.models.postgres.user import PatientProfile, ProviderProfile, User


async def get_patients(
    db: AsyncSession,
    page: int,
    page_size: int,
    is_active: bool | None = None,
):

    stmt = (
        select(User)
        .where(User.role_id == 1)
        .options(selectinload(User.patient_profile))
    )

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)

    return result.scalars().all()


async def get_all_providers_repo(db: AsyncSession, is_active: bool | None = None):
    stmt = (
        select(User)
        .where(User.role_id == 2)
        .options(selectinload(User.provider_profile))
    )

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    result = await db.execute(stmt)

    return result.scalars().all()


async def get_all_providers(
    db: AsyncSession, page: int, page_size: int, is_active: bool | None
):
    stmt = (
        select(User)
        .where(User.role_id == 2)
        .options(selectinload(User.provider_profile))
    )

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)

    return result.scalars().all()


async def get_providers_by_type_repo(
    db: AsyncSession, appointment_type_id: int, is_active: bool | None = None
):

    stmt = (
        select(User)
        .where(User.role_id == 2, User.appointment_type_id == appointment_type_id)
        .options(selectinload(User.provider_profile))
    )

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    result = await db.execute(stmt)

    return result.scalars().all()


async def get_patient_by_id_repo(
    db: AsyncSession, id: int, is_active: bool | None = None
):
    stmt = (
        select(User)
        .where(User.role_id == 1, User.id == id)
        .options(selectinload(User.patient_profile))
    )

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    result = await db.execute(stmt)
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    return patient

async def get_user_by_id_repo(
    db: AsyncSession, id: int, is_active: bool | None = None
):
    stmt = (
        select(User)
        .where(User.id == id)
        .options(selectinload(User.patient_profile))
    )

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    return user


async def insert_user(db: AsyncSession, user_data: dict):

    stmt = insert(User).values(**user_data).returning(User.id)

    result = await db.execute(stmt)

    return result.scalar_one()


async def insert_patient_profile(db: AsyncSession, user_id: int, profile_data: dict):

    profile_data["user_id"] = user_id

    stmt = insert(PatientProfile).values(**profile_data)

    await db.execute(stmt)


async def insert_provider_profile(db: AsyncSession, user_id: int, profile_data: dict):
    profile_data["user_id"] = user_id

    stmt = insert(ProviderProfile).values(**profile_data)

    await db.execute(stmt)


async def update_user_with_profile_repo(
    db: AsyncSession, user_id: int, user_data: dict, profile_data: dict | None = None
):
    try:
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise Exception("User not found")

        if user_data:
            stmt = update(User).where(User.id == user_id).values(**user_data)
            await db.execute(stmt)

        if profile_data:
            profile_stmt = select(PatientProfile).where(
                PatientProfile.user_id == user_id
            )
            profile_result = await db.execute(profile_stmt)
            existing_profile = profile_result.scalar_one_or_none()

            if existing_profile:
                stmt = (
                    update(PatientProfile)
                    .where(PatientProfile.user_id == user_id)
                    .values(**profile_data)
                )
                await db.execute(stmt)
            else:
                new_profile = PatientProfile(user_id=user_id, **profile_data)
                db.add(new_profile)

        await db.commit()

        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.patient_profile))
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    except Exception:
        await db.rollback()
        raise Exception("Failed to update user")
