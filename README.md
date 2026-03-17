# Auth Service

Handles all authentication, user management, role management, and token operations.

## Port: 8001

## Responsibilities
- Patient / Provider / Front-desk registration and login
- JWT access + refresh token issuance and revocation
- Logout / token refresh / token verify
- User CRUD (patients, providers, roles)
- Database migrations and all user-related seeds

## Routes
| Method | Path | Auth Required |
|--------|------|---------------|
| POST | /api/v1/auth/register | No |
| POST | /api/v1/auth/login | No |
| GET  | /api/v1/auth/logout | Cookie |
| POST | /api/v1/auth/refresh | Cookie |
| GET  | /api/v1/auth/verify | Cookie |
| GET  | /api/v1/users/get_roles | No |
| GET  | /api/v1/users/list | Bearer |
| GET  | /api/v1/users/providers | Bearer |
| GET  | /api/v1/users/providers/by-type | Bearer |
| POST | /api/v1/users/patients/create | No |
| PUT  | /api/v1/users/update/{user_id} | Bearer |
| GET  | /api/v1/internal/users/by-identifier | Internal (no token) |
| GET  | /api/v1/health | No |

## Setup
```bash
cp .env.example .env
# fill in your values
uvicorn src.api.rest.app:app --host 0.0.0.0 --port 8001 --reload
```

## Docker
```bash
docker-compose up --build
```
