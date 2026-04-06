from pydantic import BaseModel


class LoginResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    access_max_age: int
    refresh_max_age: int

class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_max_age: int

class UserPayload(BaseModel):
    id: int
    email: str
    name: str
    role_id: int
    phone_number: str


class VerifyTokenResponse(BaseModel):
    valid: bool
    access_token: str
    user: UserPayload
    access_max_age: int | None = None  