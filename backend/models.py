from pydantic import BaseModel, EmailStr

# =========================
# USER SCHEMAS
# =========================

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


from pydantic import BaseModel

class ForgotPasswordRequest(BaseModel):
    email: str
    new_password: str

