from pydantic import BaseModel, EmailStr
from typing import Optional

class userSignup(BaseModel):
    username : str
    password : str
    email :  EmailStr

class userSignin(BaseModel):
    username : str
    password : str

class userResponse(BaseModel):
    id : int
    username : str
    email : EmailStr
    status : str
    phone_number : str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenData(BaseModel):
    username: Optional[str] = None

class SessionInfo(BaseModel):
    id: int
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: str
    expires_at: str