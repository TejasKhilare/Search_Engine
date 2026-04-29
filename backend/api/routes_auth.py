from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from db.postgres import get_db
from db.models import User
from core.security import hash_password,verify_password,create_access_token

router=APIRouter(prefix="/api",tags=["auth"])

class RegisterRequest(BaseModel):
    username:str
    email:str
    password:str

class LoginRequest(BaseModel):
    email:str
    password:str

@router.post("/register")
def register(req:RegisterRequest,db:Session=Depends(get_db)):
    if(db.query(User).filter(User.email==req.email).first()):
        raise HTTPException(status_code=400,detail="Email already exist")
    if(db.query(User).filter(User.username==req.username).first()):
        raise HTTPException(status_code=400,detail="Username already exist")

    user=User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password)
    )
    db.add(user)
    db.commit()

    return {"message":"User created successfully.."}

@router.post("/login")
def login(req:LoginRequest,db:Session=Depends(get_db)):
    user=db.query(User).filter(User.email==req.email).first()
    if not user or not verify_password(req.password,user.password_hash): # type: ignore
        raise HTTPException(status_code=401,detail="Invalid credentials")
    token=create_access_token({"sub":str(user.id)})
    return {
        "access_token":token,
        "token_type":"bearer"
    }