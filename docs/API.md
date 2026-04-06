# Auth Service API Reference

## Base URL
Starting URL for all endpoints is typically `/api/v1`.

## Authentication Method
All protected endpoints require a JWT bearer token passed in the `Authorization` header.
Format: `Authorization: Bearer <your_access_token>`

---

## Authentication Endpoints

### POST `/auth/register`
**Description**: Registers a new user in the system. Rate limited.

**Request**:
```json
{
  "email": "user@example.com",
  "password": "strongPassword123!",
  "name": "Jane Doe",
  "phone": "+1234567890",
  "role_id": 1
}
```

**Response** (200 OK):
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Jane Doe",
  "message": "User registered successfully"
}
```

**Errors**:
- `400 Bad Request`: If email already exists or validation fails.
- `429 Too Many Requests`: Rate limit exceeded.

---

### POST `/auth/login`
**Description**: Authenticates a user and returns short-lived access and long-lived refresh tokens. Rate limited.

**Request**:
```json
{
  "email": "user@example.com",
  "password": "strongPassword123!"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhb...",
  "refresh_token": "def502...",
  "token_type": "bearer"
}
```

**Errors**:
- `401 Unauthorized`: Invalid credentials.

---

### POST `/auth/refresh`
**Description**: Exchanges a valid refresh token for a new access token.

**Request**:
```json
{
  "refresh_token": "def502..."
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbnew...",
  "token_type": "bearer"
}
```

---

### POST `/auth/logout`
**Description**: Revokes the current refresh token to securely sign out the user.

**Request**: Requires valid Bearer Token.

**Response** (200 OK):
```json
{
  "message": "Logged out securely"
}
```
