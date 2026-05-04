from passlib.context import CryptContext
from database import users_collection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')
    truncated_bytes = password_bytes[:72]
    return pwd_context.hash(truncated_bytes)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # truncate plain_password like when hashing
    plain_bytes = plain_password.encode('utf-8')[:72]
    return pwd_context.verify(plain_bytes, hashed_password)

def create_user(user: dict):
    user["password"] = hash_password(user["password"])
    users_collection.insert_one(user)

def authenticate_user(email: str, password: str) -> dict | None:
    user = users_collection.find_one({"email": email})
    if not user:
        return None
    if not verify_password(password, user["password"]):
        return None
    return user
