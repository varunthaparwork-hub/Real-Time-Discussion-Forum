"""
JWT authentication for the forum service.
This doesn't call auth-service — it verifies the JWT token locally
using the same secret key. If the token is valid, it extracts the
user_id and role from it.
"""
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials   

load_dotenv()

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

SECRET_KEY = os.getenv("JWT_SECRET_KEY" , "my_very_long_super_secure_secret_key_2026_abc123")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


@dataclass
class AuthUser:
    id: int
    role: str = "member"


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: user_id missing",
            )
        return int(user_id)
    
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or Expired token",
        )


def get_current_auth_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> AuthUser:
    """Returns AuthUser with id and role extracted from JWT."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: user_id missing",
            )
        # SimpleJWT stores role if it was added to the token — fall back to fetching from auth service
        role = payload.get("role", "member")
        return AuthUser(id=int(user_id), role=role)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or Expired token",
        )