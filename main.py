import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import db, create_document, get_documents
from bson import ObjectId

from schemas import Facility as FacilitySchema, Staff as StaffSchema, Feedback as FeedbackSchema

app = FastAPI(title="Swachh Scan API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        try:
            return ObjectId(str(v))
        except Exception:
            raise ValueError("Invalid ObjectId")


def serialize_doc(doc):
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id"))
    # Convert datetimes to isoformat
    for k, v in list(doc.items()):
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc


@app.get("/")
def read_root():
    return {"message": "Swachh Scan Backend is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# ========== Facility Endpoints ==========
class FacilityCreate(FacilitySchema):
    pass


@app.post("/api/facilities")
def create_facility(payload: FacilityCreate):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    # Ensure unique code
    existing = db["facility"].find_one({"code": payload.code})
    if existing:
        raise HTTPException(400, detail="Facility code already exists")
    inserted_id = create_document("facility", payload)
    doc = db["facility"].find_one({"_id": ObjectId(inserted_id)})
    return serialize_doc(doc)


@app.get("/api/facilities/by-code/{code}")
def get_facility_by_code(code: str):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    doc = db["facility"].find_one({"code": code})
    if not doc:
        raise HTTPException(404, detail="Facility not found")
    return serialize_doc(doc)


# ========== Staff Endpoints (basic create & list) ==========
class StaffCreate(StaffSchema):
    pass


@app.post("/api/staff")
def create_staff(payload: StaffCreate):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    inserted_id = create_document("staff", payload)
    doc = db["staff"].find_one({"_id": ObjectId(inserted_id)})
    return serialize_doc(doc)


@app.get("/api/staff")
def list_staff():
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    docs = get_documents("staff")
    return [serialize_doc(d) for d in docs]


# ========== Feedback / Task Endpoints ==========
class FeedbackCreate(BaseModel):
    facility_code: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    photo_url: Optional[str] = None
    user_lat: Optional[float] = None
    user_lng: Optional[float] = None


@app.post("/api/feedback")
def submit_feedback(payload: FeedbackCreate):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    facility = db["facility"].find_one({"code": payload.facility_code})
    if not facility:
        raise HTTPException(404, detail="Facility not found for given code")
    feedback = FeedbackSchema(
        facility_code=payload.facility_code,
        rating=payload.rating,
        comment=payload.comment,
        photo_url=payload.photo_url,
        status="open",
        user_lat=payload.user_lat,
        user_lng=payload.user_lng,
    )
    inserted_id = create_document("feedback", feedback)
    doc = db["feedback"].find_one({"_id": ObjectId(inserted_id)})
    return serialize_doc(doc)


@app.get("/api/feedback")
def list_feedback(status: Optional[str] = None, facility_code: Optional[str] = None, assigned_to: Optional[str] = None, limit: Optional[int] = 100):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    query = {}
    if status:
        query["status"] = status
    if facility_code:
        query["facility_code"] = facility_code
    if assigned_to:
        query["assigned_to"] = assigned_to
    docs = db["feedback"].find(query).sort("created_at", -1)
    if limit:
        docs = docs.limit(int(limit))
    return [serialize_doc(d) for d in docs]


# Assignment and status updates
class AssignPayload(BaseModel):
    staff_id: str


@app.patch("/api/feedback/{feedback_id}/assign")
def assign_feedback(feedback_id: str, payload: AssignPayload):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    res = db["feedback"].update_one(
        {"_id": PyObjectId.validate(feedback_id)},
        {"$set": {"assigned_to": payload.staff_id, "status": "in_progress", "updated_at": datetime.now(timezone.utc), "started_at": datetime.now(timezone.utc)}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, detail="Feedback not found")
    doc = db["feedback"].find_one({"_id": PyObjectId.validate(feedback_id)})
    return serialize_doc(doc)


class StartPayload(BaseModel):
    before_photo_url: Optional[str] = None
    staff_start_lat: Optional[float] = None
    staff_start_lng: Optional[float] = None


@app.patch("/api/feedback/{feedback_id}/start")
def start_task(feedback_id: str, payload: StartPayload):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    updates["status"] = "in_progress"
    updates["updated_at"] = datetime.now(timezone.utc)
    updates.setdefault("started_at", datetime.now(timezone.utc))
    res = db["feedback"].update_one({"_id": PyObjectId.validate(feedback_id)}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(404, detail="Feedback not found")
    doc = db["feedback"].find_one({"_id": PyObjectId.validate(feedback_id)})
    return serialize_doc(doc)


class ResolvePayload(BaseModel):
    after_photo_url: Optional[str] = None
    staff_complete_lat: Optional[float] = None
    staff_complete_lng: Optional[float] = None


@app.patch("/api/feedback/{feedback_id}/resolve")
def resolve_task(feedback_id: str, payload: ResolvePayload):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    updates["status"] = "resolved"
    updates["updated_at"] = datetime.now(timezone.utc)
    updates["resolved_at"] = datetime.now(timezone.utc)
    res = db["feedback"].update_one({"_id": PyObjectId.validate(feedback_id)}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(404, detail="Feedback not found")
    doc = db["feedback"].find_one({"_id": PyObjectId.validate(feedback_id)})
    return serialize_doc(doc)


# Stats endpoint for dashboard
@app.get("/api/stats")
def stats():
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    total = db["feedback"].count_documents({})
    open_count = db["feedback"].count_documents({"status": "open"})
    in_progress = db["feedback"].count_documents({"status": "in_progress"})
    resolved = db["feedback"].count_documents({"status": "resolved"})

    # Leaderboard: tasks resolved per staff
    pipeline = [
        {"$match": {"status": "resolved", "assigned_to": {"$ne": None}}},
        {"$group": {"_id": "$assigned_to", "resolved_count": {"$sum": 1}}},
        {"$sort": {"resolved_count": -1}},
        {"$limit": 10},
    ]
    leaderboard = list(db["feedback"].aggregate(pipeline))
    # Attach staff names if present
    for item in leaderboard:
        staff = db["staff"].find_one({"_id": ObjectId(item["_id"])}) if ObjectId.is_valid(item["_id"]) else None
        item["staff_id"] = item.pop("_id")
        item["staff_name"] = staff.get("name") if staff else None

    return {
        "counts": {
            "total": total,
            "open": open_count,
            "in_progress": in_progress,
            "resolved": resolved,
        },
        "leaderboard": leaderboard,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
