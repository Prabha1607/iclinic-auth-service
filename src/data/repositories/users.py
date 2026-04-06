import logging

from fastapi import HTTPException, status
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.data.models.postgres.user import PatientProfile, ProviderProfile, User

logger = logging.getLogger(__name__)


async def get_patients(
    db: AsyncSession,
    page: int,
    page_size: int,
    is_active: bool | None = None,
) -> list[User]:
    logger.info(
        "Fetching patients",
        extra={"page": page, "page_size": page_size, "is_active": is_active},
    )
    try:
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
        patients = result.scalars().all()

        logger.info(
            "Patients fetched successfully",
            extra={"count": len(patients), "page": page},
        )
        return patients
    except Exception as e:
        logger.error(
            "Failed to fetch patients",
            extra={"page": page, "page_size": page_size, "error": str(e)},
        )
        raise


async def get_all_providers_repo(
    db: AsyncSession, is_active: bool | None = None
) -> list[User]:
    logger.info("Fetching all providers", extra={"is_active": is_active})
    try:
        stmt = (
            select(User)
            .where(User.role_id == 2)
            .options(selectinload(User.provider_profile))
        )

        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        result = await db.execute(stmt)
        providers = result.scalars().all()

        logger.info(
            "All providers fetched successfully",
            extra={"count": len(providers), "is_active": is_active},
        )
        return providers
    except Exception as e:
        logger.error(
            "Failed to fetch all providers",
            extra={"is_active": is_active, "error": str(e)},
        )
        raise


async def get_all_providers(
    db: AsyncSession,
    page: int,
    page_size: int,
    is_active: bool | None,
) -> list[User]:
    logger.info(
        "Fetching paginated providers",
        extra={"page": page, "page_size": page_size, "is_active": is_active},
    )
    try:
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
        providers = result.scalars().all()

        logger.info(
            "Paginated providers fetched successfully",
            extra={"count": len(providers), "page": page},
        )
        return providers
    except Exception as e:
        logger.error(
            "Failed to fetch paginated providers",
            extra={"page": page, "page_size": page_size, "error": str(e)},
        )
        raise


async def get_providers_by_type_repo(
    db: AsyncSession,
    appointment_type_id: int,
    is_active: bool | None = None,
) -> list[User]:
    logger.info(
        "Fetching providers by appointment type",
        extra={"appointment_type_id": appointment_type_id, "is_active": is_active},
    )
    try:
        stmt = (
            select(User)
            .where(User.role_id == 2, User.appointment_type_id == appointment_type_id)
            .options(selectinload(User.provider_profile))
        )

        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        result = await db.execute(stmt)
        providers = result.scalars().all()

        logger.info(
            "Providers by type fetched successfully",
            extra={
                "appointment_type_id": appointment_type_id,
                "count": len(providers),
            },
        )
        return providers
    except Exception as e:
        logger.error(
            "Failed to fetch providers by appointment type",
            extra={"appointment_type_id": appointment_type_id, "error": str(e)},
        )
        raise


async def get_patient_by_id_repo(
    db: AsyncSession,
    id: int,
    is_active: bool | None = None,
) -> User:
    logger.info("Fetching patient by ID", extra={"patient_id": id, "is_active": is_active})
    try:
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
            logger.warning("Patient not found", extra={"patient_id": id})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        logger.info("Patient fetched successfully", extra={"patient_id": id})
        return patient
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to fetch patient by ID",
            extra={"patient_id": id, "error": str(e)},
        )
        raise


async def get_user_by_id_repo(
    db: AsyncSession,
    id: int,
    is_active: bool | None = None,
) -> User:
    logger.info("Fetching user by ID", extra={"user_id": id, "is_active": is_active})
    try:
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
            logger.warning("User not found", extra={"user_id": id})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        logger.info("User fetched successfully", extra={"user_id": id})
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to fetch user by ID",
            extra={"user_id": id, "error": str(e)},
        )
        raise


async def insert_user(db: AsyncSession, user_data: dict) -> int:
    logger.info("Inserting user record")
    try:
        stmt = insert(User).values(**user_data).returning(User.id)
        result = await db.execute(stmt)
        user_id = result.scalar_one()
        logger.info("User record inserted successfully", extra={"user_id": user_id})
        return user_id
    except Exception as e:
        logger.error("Failed to insert user record", extra={"error": str(e)})
        raise


async def insert_patient_profile(
    db: AsyncSession, user_id: int, profile_data: dict
) -> None:
    logger.info("Inserting patient profile", extra={"user_id": user_id})
    try:
        profile_data["user_id"] = user_id
        stmt = insert(PatientProfile).values(**profile_data)
        await db.execute(stmt)
        logger.info("Patient profile inserted successfully", extra={"user_id": user_id})
    except Exception as e:
        logger.error(
            "Failed to insert patient profile",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise


async def insert_provider_profile(
    db: AsyncSession, user_id: int, profile_data: dict
) -> None:
    logger.info("Inserting provider profile", extra={"user_id": user_id})
    try:
        profile_data["user_id"] = user_id
        stmt = insert(ProviderProfile).values(**profile_data)
        await db.execute(stmt)
        logger.info("Provider profile inserted successfully", extra={"user_id": user_id})
    except Exception as e:
        logger.error(
            "Failed to insert provider profile",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise


async def update_user_with_profile_repo(
    db: AsyncSession,
    user_id: int,
    user_data: dict,
    profile_data: dict | None = None,
) -> User:
    logger.info("Updating user with profile", extra={"user_id": user_id})
    try:
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("User not found for update", extra={"user_id": user_id})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if user_data:
            stmt = update(User).where(User.id == user_id).values(**user_data)
            await db.execute(stmt)
            logger.info("User fields updated", extra={"user_id": user_id})

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
                logger.info("Patient profile updated", extra={"user_id": user_id})
            else:
                db.add(PatientProfile(user_id=user_id, **profile_data))
                logger.info("Patient profile created", extra={"user_id": user_id})

        await db.commit()

        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.patient_profile))
        )
        result = await db.execute(stmt)
<<<<<<< HEAD
        updated_user = result.scalar_one()
=======
        
        return result.scalar_one()
>>>>>>> feature/coding-standard

        logger.info("User updated and refetched successfully", extra={"user_id": user_id})
        return updated_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update user with profile",
            extra={"user_id": user_id, "error": str(e)},
        )
        await db.rollback()
        raise