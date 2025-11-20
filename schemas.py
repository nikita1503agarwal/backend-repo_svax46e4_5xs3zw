"""
Database Schemas for Swachh Scan

Each Pydantic model corresponds to a MongoDB collection.
Collection name is the lowercase of class name.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime


class Facility(BaseModel):
    """Public facility that will have a QR code"""
    code: str = Field(..., description="Unique QR code or short identifier")
    name: str = Field(..., description="Facility name, e.g., Toilet Block A")
    address: Optional[str] = Field(None, description="Address or description of location")
    lat: Optional[float] = Field(None, description="Latitude")
    lng: Optional[float] = Field(None, description="Longitude")
    ward: Optional[str] = Field(None, description="Administrative ward/zone")
    is_active: bool = Field(True, description="Whether facility is active")


class Staff(BaseModel):
    """Cleaning staff profile"""
    name: str
    phone: Optional[str] = None
    employee_id: Optional[str] = None
    ward: Optional[str] = None
    is_active: bool = True


class Feedback(BaseModel):
    """Citizen feedback / complaint that becomes a cleaning task"""
    facility_code: str = Field(..., description="Facility QR code or unique code")
    rating: int = Field(..., ge=1, le=5, description="Hygiene rating 1-5")
    comment: Optional[str] = Field(None, description="Text feedback/suggestions")
    photo_url: Optional[HttpUrl] = Field(None, description="Optional photo URL from user")
    status: str = Field("open", description="open | in_progress | resolved")
    assigned_to: Optional[str] = Field(None, description="Staff ID (stringified ObjectId)")
    before_photo_url: Optional[HttpUrl] = None
    after_photo_url: Optional[HttpUrl] = None
    user_lat: Optional[float] = None
    user_lng: Optional[float] = None
    staff_start_lat: Optional[float] = None
    staff_start_lng: Optional[float] = None
    staff_complete_lat: Optional[float] = None
    staff_complete_lng: Optional[float] = None
    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
