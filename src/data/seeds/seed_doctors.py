from sqlalchemy import text

from src.data.clients.postgres_client import AsyncSessionLocal


async def seed_doctors():
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
            INSERT INTO users
                (id, role_id, appointment_type_id, first_name, last_name,
                 country_code, phone_no, email, password, is_active, created_at)
            VALUES
                (1, 2, 1, 'Arjun',  'Kumar',  '+91', '9000000001', 'arjun.kumar@clinic.com',  'hashed_pass', true, NOW()),
                (2, 2, 2, 'Meena',  'Ravi',   '+91', '9000000002', 'meena.ravi@clinic.com',   'hashed_pass', true, NOW()),
                (3, 2, 3, 'Rahul',  'Sharma', '+91', '9000000003', 'rahul.sharma@clinic.com', 'hashed_pass', true, NOW())
            ON CONFLICT (id) DO UPDATE SET
                role_id            = EXCLUDED.role_id,
                appointment_type_id = EXCLUDED.appointment_type_id,
                first_name         = EXCLUDED.first_name,
                last_name          = EXCLUDED.last_name,
                country_code       = EXCLUDED.country_code,
                phone_no           = EXCLUDED.phone_no,
                email              = EXCLUDED.email,
                is_active          = true,
                created_at         = COALESCE(users.created_at, NOW());
            """)
        )

        await session.execute(
            text("""
            INSERT INTO provider_profiles
                (id, user_id, specialization, qualification, experience, bio)
            VALUES
                (1, 1, 'General Physician',  'MBBS',                  8,  'Experienced in general health care'),
                (2, 2, 'Cardiologist',        'MBBS, MD Cardiology',  12, 'Heart specialist'),
                (3, 3, 'Pediatrician',        'MBBS, MD Pediatrics',  10, 'Child health expert')
            ON CONFLICT (id) DO UPDATE SET
                user_id        = EXCLUDED.user_id,
                specialization = EXCLUDED.specialization,
                qualification  = EXCLUDED.qualification,
                experience     = EXCLUDED.experience,
                bio            = EXCLUDED.bio;
            """)
        )

        await session.execute(
            text("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));")
        )
        await session.execute(
            text(
                "SELECT setval('provider_profiles_id_seq', (SELECT MAX(id) FROM provider_profiles));"
            )
        )

        await session.commit()
