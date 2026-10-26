from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from .errors import BusinessError

password_hasher = PasswordHash.recommended()


def hash_password(password: str):
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str):
    try:
        return password_hasher.verify(password, hashed)
    except Exception:
        return False


def issue_token(settings, user, login_session):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user.id, "jti": login_session.id, "ver": user.token_version,
                       "iat": now, "exp": now + timedelta(seconds=settings.jwt_ttl_seconds),
                       "iss": "knowledge-base", "aud": "knowledge-base-web"},
                      settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_token(settings, token):
    try:
        return jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=["HS256"],
                          audience="knowledge-base-web", issuer="knowledge-base",
                          options={"require": ["sub", "jti", "ver", "iat", "exp"]})
    except jwt.PyJWTError as exc:
        raise BusinessError(401, "登录已失效，请重新登录") from exc
