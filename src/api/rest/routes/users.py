import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.schemas.roles import RoleResponse
from src.api.rest.dependencies import get_db
from src.core.services.user import (
    create_provider_service,
    create_user,
    get_all_patients,
    get_all_providers_service,
    get_patient_by_id_service,
    get_providers,
    get_providers_by_type_service,
    get_roles,
    get_user_by_id_service,
    update_user_service,
)
from src.schemas.user import (
    PatientFullResponse,
    ProviderCreate,
    ProviderFullResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])



@router.get(
    "/get_roles",
    response_model=list[RoleResponse],
    summary="Get User Roles",
    description="Retrieves a list of all available user roles.",
)
async def get_all_roles(db: AsyncSession = Depends(get_db)):
    """
    Retrieve all available user roles.

    Fetches the complete list of roles defined in the system. Typically used
    to populate role selection menus in admin or registration interfaces.

    Args:
        db: Async database session injected by ``get_db``.

    Returns:
        list[RoleResponse]: All role records available in the system.

    Raises:
        HTTPException 500: When an unexpected error occurs during retrieval.
    """
    logger.info("Fetch all roles requested")
    try:
        result = await get_roles(db=db)
        logger.info("Roles fetched successfully", extra={"count": len(result)})
        return result
    except Exception as e:
        logger.error("Failed to fetch roles", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch roles",
        )
    

@router.get(
    "/list",
    response_model=list[PatientFullResponse],
    summary="List Patients",
    description="Retrieves a paginated list of patients.",
)
async def get_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, le=100),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a paginated list of patient users.

    Supports optional filtering by active status. Returns patients ordered
    by the service layer's default ordering.

    Args:
        page:      1-based page number (default: ``1``, minimum: ``1``).
        page_size: Maximum number of records per page (default: ``10``, maximum: ``100``).
        is_active: Optional filter to return only active or inactive patients.
                   Omit to return patients regardless of active status.
        db:        Async database session injected by ``get_db``.

    Returns:
        list[PatientFullResponse]: Paginated list of patient records.
        Returns an empty list when no patients match the applied filters.

    Raises:
        HTTPException 500: When an unexpected error occurs during retrieval.
    """
    logger.info(
        "Fetch patients requested",
        extra={"page": page, "page_size": page_size, "is_active": is_active},
    )
    try:
        users = await get_all_patients(
            db=db,
            page=page,
            page_size=page_size,
            is_active=is_active,
        )
        logger.info(
            "Patients fetched successfully",
            extra={"count": len(users), "page": page},
        )
        return users
    except Exception as e:
        logger.error("Failed to fetch patients", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch patients",
        )


@router.get("/providers/by-type", response_model=list[ProviderFullResponse])
async def get_providers_by_type(
    appointment_type_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all active providers that support a given appointment type.

    Filters the provider list to those configured to handle the specified
    appointment type. Only active providers are returned.

    Args:
        appointment_type_id: Primary key of the appointment type to filter by.
        db:                  Async database session injected by ``get_db``.

    Returns:
        list[ProviderFullResponse]: Active providers supporting the given
        appointment type. Returns an empty list when none are found.

    Raises:
        HTTPException 500: When an unexpected error occurs during retrieval.
    """
    logger.info(
        "Fetch providers by type requested",
        extra={"appointment_type_id": appointment_type_id},
    )
    try:
        providers = await get_providers_by_type_service(
            db=db, appointment_type_id=appointment_type_id, is_active=True
        )
        logger.info(
            "Providers by type fetched successfully",
            extra={"appointment_type_id": appointment_type_id, "count": len(providers)},
        )
        return providers
    except Exception as e:
        logger.error(
            "Failed to fetch providers by type",
            extra={"appointment_type_id": appointment_type_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch providers by appointment type",
        )


@router.get("/providers/full", response_model=list[ProviderFullResponse])
async def get_all_providers(db: AsyncSession = Depends(get_db)):
    """
    Retrieve the full list of all active providers without pagination.

    Returns every active provider in the system in a single response.
    Intended for internal use cases where a complete provider list is
    required, such as populating maps or admin dashboards.

    Args:
        db: Async database session injected by ``get_db``.

    Returns:
        list[ProviderFullResponse]: All active provider records.
        Returns an empty list when no active providers exist.

    Raises:
        HTTPException 500: When an unexpected error occurs during retrieval.
    """
    logger.info("Fetch all active providers requested")
    try:
        providers = await get_all_providers_service(db=db, is_active=True)
        logger.info(
            "All active providers fetched successfully",
            extra={"count": len(providers)},
        )
        return providers
    except Exception as e:
        logger.error("Failed to fetch all providers", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch providers",
        )


@router.get(
    "/providers",
    response_model=list[ProviderFullResponse],
    summary="List Providers",
    description="Retrieves a paginated list of providers.",
)
async def get_all_providers_paginated(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, le=100),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a paginated list of providers.

    Supports optional filtering by active status. Use ``/providers/full``
    when an unpaginated complete list is required.

    Args:
        page:      1-based page number (default: ``1``, minimum: ``1``).
        page_size: Maximum number of records per page (default: ``10``, maximum: ``100``).
        is_active: Optional filter by the provider's active flag.
                   Omit to return providers regardless of active status.
        db:        Async database session injected by ``get_db``.

    Returns:
        list[ProviderFullResponse]: Paginated list of provider records.
        Returns an empty list when no providers match the applied filters.

    Raises:
        HTTPException 500: When an unexpected error occurs during retrieval.
    """
    logger.info(
        "Fetch paginated providers requested",
        extra={"page": page, "page_size": page_size, "is_active": is_active},
    )
    try:
        providers = await get_providers(db, page, page_size, is_active)
        logger.info(
            "Paginated providers fetched successfully",
            extra={"count": len(providers), "page": page},
        )
        return providers
    except Exception as e:
        logger.error("Failed to fetch paginated providers", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch providers",
        )


@router.get("/patient/{id}", response_model=PatientFullResponse)
async def get_patient_by_id(id: int, db: AsyncSession = Depends(get_db)):
    """
    Retrieve a single active patient record by primary key.

    Args:
        id: Primary key of the patient to retrieve.
        db: Async database session injected by ``get_db``.

    Returns:
        PatientFullResponse: Full patient record including profile details.

    Raises:
        HTTPException 404: When no active patient with the given ID exists
                           (raised by the service layer).
        HTTPException 500: When an unexpected error occurs during retrieval.
    """
    logger.info("Fetch patient by ID requested", extra={"patient_id": id})
    try:
        patient = await get_patient_by_id_service(db=db, id=id, is_active=True)
        logger.info("Patient fetched successfully", extra={"patient_id": id})
        return patient
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to fetch patient by ID",
            extra={"patient_id": id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch patient",
        )


@router.get("/{id}", response_model=UserResponse)
async def get_user_by_id(id: int, db: AsyncSession = Depends(get_db)):
    """
    Retrieve a single active user record by primary key.

    Generic user lookup that returns the base user fields regardless of
    role. For role-specific responses use the dedicated patient or provider
    endpoints.

    Args:
        id: Primary key of the user to retrieve.
        db: Async database session injected by ``get_db``.

    Returns:
        UserResponse: Base user record fields.

    Raises:
        HTTPException 404: When no active user with the given ID exists
                           (raised by the service layer).
        HTTPException 500: When an unexpected error occurs during retrieval.
    """
    logger.info("Fetch user by ID requested", extra={"user_id": id})
    try:
        user = await get_user_by_id_service(db=db, id=id, is_active=True)
        logger.info("User fetched successfully", extra={"user_id": id})
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to fetch user by ID",
            extra={"user_id": id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user",
        )


@router.post("/patients/create", response_model=PatientFullResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(patient: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new patient user account.

    Persists a new patient record with the supplied details. The endpoint
    enforces uniqueness on email address and phone number at the database level.

    Args:
        patient: Patient creation payload containing personal and contact details.
        db:      Async database session injected by ``get_db``.

    Returns:
        PatientFullResponse: The newly created patient record including
        generated fields such as ``id`` and ``created_at``.

    Raises:
        HTTPException 400: When the email address or phone number is already
                           registered to an existing account.
        HTTPException 500: When an unexpected error occurs during creation.
    """
    logger.info("Create patient requested", extra={"email": patient.email})
    try:
        created_patient = await create_user(db=db, user_data=patient)
        logger.info(
            "Patient created successfully",
            extra={"email": patient.email, "patient_id": created_patient.id},
        )
        return created_patient
    except IntegrityError:
        logger.warning(
            "Patient creation rejected — duplicate email or phone",
            extra={"email": patient.email},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or phone already exists",
        )
    except Exception as e:
        logger.error(
            "Failed to create patient",
            extra={"email": patient.email, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create patient",
        )
    
@router.post(
    "/providers/create",
    response_model=ProviderFullResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(provider: ProviderCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new provider account.
    """
    logger.info("Create provider requested", extra={"email": provider.email})
    try:
        created_provider = await create_provider_service(db=db, provider_data=provider)
        logger.info(
            "Provider created successfully",
            extra={"email": provider.email, "provider_id": created_provider.id},
        )
        return created_provider

    except IntegrityError:
        logger.warning(
            "Provider creation rejected — duplicate email or phone",
            extra={"email": provider.email},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or phone already exists",
        )

    except Exception as e:
        logger.error(
            "Failed to create provider",
            extra={"email": provider.email, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create provider",
        )
    
@router.get("/providers/full", response_model=list[ProviderFullResponse])
async def get_all_providers(db: AsyncSession = Depends(get_db)):
    return await get_all_providers_service(db=db, is_active=True)

@router.put("/update/{user_id}", response_model=PatientFullResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    logger.info("Update user requested", extra={"user_id": user_id})
    try:
        user = await update_user_service(db=db, user_id=user_id, user_data=user_data)
        logger.info("User updated successfully", extra={"user_id": user_id})
        return user

    except IntegrityError:
        logger.warning(
            "User update rejected — duplicate email",
            extra={"user_id": user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "Failed to update user",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        )
    
    