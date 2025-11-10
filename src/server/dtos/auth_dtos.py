from pydantic import BaseModel, EmailStr
from pydantic import ConfigDict
from typing import Optional, List
from datetime import datetime

class RegisterRequest(BaseModel):
    # --- Thông tin bắt buộc để đăng nhập ---
    email: EmailStr
    password: str
    display_name: Optional[str] = None

class VerifyRequest(BaseModel):
    id_token: str

