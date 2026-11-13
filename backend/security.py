import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

passwords = PasswordHash.recommended()
# A dummy verification makes unknown-account logins do the same costly hash work.
DUMMY_HASH = passwords.hash('unused-dummy-password')


def verify_password(password: str, encoded: str) -> bool:
    try:
        return passwords.verify(password, encoded)
    except (ValueError, UnknownHashError):
        # Invalid legacy hashes must never become server errors or authenticate.
        return False


def password_version(encoded: str) -> str:
    return hashlib.sha256(encoded.encode()).hexdigest()


def token_for(user: dict, settings) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        'sub': user['user_id'], 'ver': password_version(user['password_hash']),
        'iat': now, 'exp': now + timedelta(minutes=settings.access_token_minutes),
        'iss': 'loop-ai', 'aud': 'loop-ai-web',
    }, settings.jwt_secret, algorithm='HS256')
