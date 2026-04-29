from fastapi import Depends,HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from sqlalchemy.orm import Session
from typing import Optional
from core.config import settings
from db.postgres import get_db
from db.models import User
import uuid

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)

def get_current_user(
        
        token_oauth: Optional[str] = Depends(oauth2_scheme),
        token_http: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
        db: Session = Depends(get_db)
):
    token: Optional[str] = None
    if token_http:
        token = token_http.credentials

    elif token_oauth:
        token = token_oauth

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload=jwt.decode(token,settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
        user_id=payload.get("sub")

        if not user_id:
            raise HTTPException(status_code=401,detail="Invalid token")
        
        user=db.query(User).filter(User.id==uuid.UUID(user_id)).first()
    except Exception:
        raise HTTPException(status_code=401,detail="Invalid token")
    
    if not user:
        raise HTTPException(status_code=401,detail="User not found")
     
    return user


