import random
import string
import time

OTP_LENGTH      = 6
OTP_TTL_SECONDS = 300   
MAX_ATTEMPTS    = 5     

_store: dict[str, dict] = {}


def _generate_code() -> str:
    return ''.join(random.choices(string.digits, k=OTP_LENGTH))


def create_otp(email: str) -> str:
    
    code = _generate_code()
    _store[email] = {
        "code":       code,
        "expires_at": time.monotonic() + OTP_TTL_SECONDS,
        "attempts":   0,
    }
    return code


def verify_otp(email: str, code: str) -> tuple[bool, str]:
    
    record = _store.get(email)

    if record is None:
        return False, "No OTP found for this email. Please request a new one."

    if time.monotonic() > record["expires_at"]:
        del _store[email]
        return False, "OTP has expired. Please request a new one."

    if record["attempts"] >= MAX_ATTEMPTS:
        del _store[email]
        return False, "Too many incorrect attempts. Please request a new OTP."

    if record["code"] != code.strip():
        record["attempts"] += 1
        remaining = MAX_ATTEMPTS - record["attempts"]
        return False, f"Incorrect OTP. {remaining} attempt(s) remaining."

    del _store[email]
    return True, "OTP verified successfully."