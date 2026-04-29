"""
JWT auth for the notification service.
Same approach as forum-service — verifies the token locally
using the shared secret key to extract user_id.
Used for REST API endpoints (GET notifications, mark as read, etc.)
"""
import os
from dotenv import load_dotenv

from fastapi import Depends , HTTPException , status
from fastapi.security import HTTPAuthorizationCredentials , HTTPBearer
from jose import JWTError , jwt

load_dotenv()

security = HTTPBearer()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM" , "HS256")

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security),) -> int:
    token = credentials.credentials

    try:
        payload = jwt.decode(token , SECRET_KEY , algorithms = [ALGORITHM])
        user_id = payload.get("user_id")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail = "Invalid Token: user_id is missing"
            )
        return int(user_id)
    
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Token"
        )