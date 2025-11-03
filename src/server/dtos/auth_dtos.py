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


class UpdateProfileRequest(BaseModel):
    """
    Partial update DTO for user profiles.
    - All fields are optional to support PATCH-like updates.
    - Extra fields are allowed to keep the model forward-compatible with profile schema.
    """
    model_config = ConfigDict(extra="allow")

    # Basic
    display_name: Optional[str] = None
    name: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[datetime] = None

    # Education / metrics
    gpa_range_4: Optional[float] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    language_certificates: Optional[str] = None
    academic_certificates: Optional[str] = None
    academic_awards: Optional[str] = None
    publications: Optional[str] = None

    # Work experience
    years_of_experience: Optional[float] = None
    total_working_hours: Optional[float] = None

    # Scholarship preferences
    desired_scholarship_type: Optional[List[str]] = None
    desired_countries: Optional[List[str]] = None
    desired_funding_level: Optional[List[str]] = None
    desired_application_mode: Optional[List[str]] = None
    desired_application_month: Optional[int] = None
    desired_field_of_study: Optional[List[str]] = None

    # Misc
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    special_things: Optional[str] = None
