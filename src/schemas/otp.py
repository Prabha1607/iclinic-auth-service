
from pydantic import BaseModel, EmailStr


class SendOtpRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
<<<<<<< HEAD
    otp: str
=======
    otp: str
>>>>>>> feature/coding-standard
