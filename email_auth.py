"""QuantX AI — email/password (JWT) auth helpers + email OTP (Resend).

Coexists with Emergent Google OAuth (session_token flow). Dev-mode: when
RESEND_API_KEY is empty, OTP is not emailed — it is returned/logged for preview.
"""
import os
import hashlib
import secrets
import asyncio
import logging
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
ACCESS_TTL_MIN = 60 * 24  # 1 day access token (simple; refresh also issued)
REFRESH_TTL_DAYS = 7
OTP_TTL_MIN = 10
OTP_RESEND_COOLDOWN_SEC = 45


def _secret():
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id, "email": email, "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TTL_MIN),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id, "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TTL_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str):
    try:
        return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


def gen_otp() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def hash_otp(code: str) -> str:
    return hashlib.sha256(f"{code}{_secret()}".encode()).hexdigest()


def resend_configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY", "").strip())


async def send_otp_email(to_email: str, name: str, code: str) -> bool:
    """Returns True if emailed via Resend, False in dev mode (not sent)."""
    if not resend_configured():
        logger.info(f"[DEV OTP] {to_email} -> {code}")
        return False
    import resend
    resend.api_key = os.environ["RESEND_API_KEY"]
    html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#020617;padding:32px;font-family:Arial,sans-serif">
      <tr><td align="center">
        <table width="480" cellpadding="0" cellspacing="0" style="background:#0B0F19;border:1px solid #1E293B;border-radius:12px;padding:32px">
          <tr><td style="color:#0EA5E9;font-size:20px;font-weight:bold">QuantX AI</td></tr>
          <tr><td style="color:#94A3B8;font-size:13px;padding-top:4px">Probability Over Prediction</td></tr>
          <tr><td style="color:#F8FAFC;font-size:15px;padding-top:24px">Hi {name or 'there'}, your verification code is:</td></tr>
          <tr><td style="color:#F8FAFC;font-size:34px;font-weight:bold;letter-spacing:8px;padding:16px 0;font-family:monospace">{code}</td></tr>
          <tr><td style="color:#64748B;font-size:12px">This code expires in {OTP_TTL_MIN} minutes. If you didn't request it, ignore this email.</td></tr>
        </table>
      </td></tr>
    </table>
    """
    params = {
        "from": os.environ.get("SENDER_EMAIL", "onboarding@resend.dev"),
        "to": [to_email],
        "subject": f"Your QuantX AI verification code: {code}",
        "html": html,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        return True
    except Exception as e:
        logger.error(f"Resend send failed: {e}")
        return False
