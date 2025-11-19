"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import date, datetime

# Example schemas (kept for reference):

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Healthcare app schemas

class Patient(BaseModel):
    """Patients collection schema (collection: "patient")"""
    name: str = Field(..., description="Full name")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    dob: Optional[date] = Field(None, description="Date of birth")
    gender: Optional[str] = Field(None, description="Gender")
    conditions: List[str] = Field(default_factory=list, description="Known medical conditions")
    allergies: List[str] = Field(default_factory=list, description="Allergies")
    medications: List[str] = Field(default_factory=list, description="Current medications")

class Appointment(BaseModel):
    """Appointments collection schema (collection: "appointment")"""
    patient_id: str = Field(..., description="Reference to patient _id (string)")
    scheduled_at: datetime = Field(..., description="Scheduled date and time (ISO8601)")
    reason: str = Field(..., description="Reason for visit")
    status: str = Field("scheduled", description="scheduled | completed | cancelled")

class Note(BaseModel):
    """Notes collection schema (collection: "note")"""
    patient_id: str = Field(..., description="Reference to patient _id (string)")
    content: str = Field(..., description="Clinical note content")
    author: Optional[str] = Field(None, description="Author or clinician name")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")

# Request model for symptom checker (not a collection)
class SymptomCheckRequest(BaseModel):
    age: int = Field(..., ge=0, le=120)
    sex: Optional[str] = Field(None)
    symptoms: List[str] = Field(..., description="List of symptoms")
    duration_days: Optional[int] = Field(1, ge=0)
