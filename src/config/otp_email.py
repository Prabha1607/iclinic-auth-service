from fastapi_mail import FastMail, MessageSchema

from src.config.email_config import email_conf


def _build_otp_body(otp_code: str) -> str:
    lines = [
        "Hello,",
        "",
        "Your email verification code for iClinic is:",
        "",
        f"        {otp_code}",
        "",
        "This code is valid for 5 minutes.",
        "Do not share it with anyone.",
        "",
        "If you did not request this, you can safely ignore this email.",
        "",
        "Best regards,",
        "The iClinic Team",
    ]
    return "\n".join(lines)


async def send_otp_email(to_email: str, otp_code: str) -> None:
    message = MessageSchema(
        subject="Your iClinic verification code",
        recipients=[to_email],
        body=_build_otp_body(otp_code),
        subtype="plain",
    )
    fm = FastMail(email_conf)
    await fm.send_message(message)