from datetime import datetime,timezone,timedelta
from jose import jwt # type: ignore
from passlib.context import CryptContext # type: ignore
from core.config import settings

pwd_context=CryptContext(schemes=['bcrypt'],deprecated="auto")

def hash_password(password:str)->str:
    return pwd_context.hash(password)

def verify_password(password:str,hashed:str)->bool:
    return pwd_context.verify(password,hashed)

def create_access_token(data:dict):
    to_encode=data.copy()
    expire=datetime.now(timezone.utc)+timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp":expire})
    return jwt.encode(to_encode,settings.SECRET_KEY,algorithm=settings.ALGORITHM)
