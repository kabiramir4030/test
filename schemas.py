from pydantic import BaseModel

class PersonCreate(BaseModel):
    firstname: str
    lastname: str
    national_code: str
    address: str
    phone: str

class PersonResponse(BaseModel):
    firstname: str
    lastname: str
    national_code: str
    address: str
    phone: str

    class Config:
        from_attributes = True

# this is a test comment for git
# برای کاربران
class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"



from typing import Optional
from pydantic import BaseModel

class PersonUpdate(BaseModel):
    firstname: Optional[str] = None 
    lastname: Optional[str] = None  
    address: Optional[str] = None   
    phone: Optional[str] = None 