from __future__ import annotations

from dataclasses import dataclass

from passlib.context import CryptContext

from app.config import Settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass(frozen=True)
class UserRecord:
    username: str
    password_hash: str
    roles: list[str]
    email: str
    name: str


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def parse_users(settings: Settings) -> dict[str, UserRecord]:
    """
    Parse AUTH_USERS.
    Formats per user (comma-separated):
      username:password:role
      username:password:role1|role2
    Passwords are hashed at load time (demo). For production inject pre-hashed values
    with prefix `{bcrypt}` — if password starts with `$2`, treat as already hashed.
    """
    users: dict[str, UserRecord] = {}
    raw = settings.auth_users.strip()
    if not raw:
        return users
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split(":")
        if len(bits) < 3:
            continue
        username, password, roles_raw = bits[0], bits[1], bits[2]
        roles = [r.strip() for r in roles_raw.replace("|", ",").split(",") if r.strip()]
        if password.startswith("$2"):
            hashed = password
        else:
            hashed = _hash_password(password)
        users[username] = UserRecord(
            username=username,
            password_hash=hashed,
            roles=roles,
            email=f"{username}@local.sre",
            name=username.title(),
        )
    return users
