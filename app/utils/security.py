
from datetime import datetime, timedelta, timezone
from app.core.configs import config
import jwt
from pwdlib import PasswordHash

setting= config.get_settings()

password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password,
    )

def create_access_token(
    subject: str,
) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=setting.access_token_expire_minutes
    )

    payload = {
        "sub": subject,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        setting.jwt_secret_key.get_secret_value(),
        algorithm=setting.jwt_algorithm,
    )

def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        setting.jwt_secret_key.get_secret_value(),
        algorithms=[setting.jwt_algorithm],
    )
