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
        orm_mode = True

# this is a test comment for git
# برای کاربران
class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"