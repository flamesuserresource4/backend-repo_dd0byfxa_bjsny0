import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Patient, Appointment, Note, SymptomCheckRequest

try:
    from bson import ObjectId
except Exception:  # fallback if bson isn't available for some reason
    ObjectId = str  # type: ignore

app = FastAPI(title="AI Healthcare Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utilities

def oid(oid_str: str):
    try:
        return ObjectId(oid_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def serialize(doc: Dict[str, Any]):
    if not doc:
        return doc
    doc["_id"] = str(doc.get("_id"))
    # Convert datetimes to isoformat
    for k, v in list(doc.items()):
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc


@app.get("/")
def read_root():
    return {"message": "AI Healthcare API is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, "name") else "❌ Unknown"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["connection_status"] = "Connected"
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# Expose schemas for viewer
class SchemaOut(BaseModel):
    name: str
    schema: dict


@app.get("/schema", response_model=List[SchemaOut])
def get_schema():
    models = [
        ("Patient", Patient),
        ("Appointment", Appointment),
        ("Note", Note),
    ]
    return [
        {"name": name, "schema": model.model_json_schema()} for name, model in models
    ]


# Patients Endpoints
@app.post("/api/patients")
def create_patient(payload: Patient):
    _id = create_document("patient", payload)
    doc = db["patient"].find_one({"_id": ObjectId(_id)}) if hasattr(ObjectId, "__call__") else db["patient"].find_one({"_id": _id})
    return serialize(doc)


@app.get("/api/patients")
def list_patients(q: Optional[str] = Query(None, description="Simple name/email search")):
    filt = {}
    if q:
        filt = {"$or": [{"name": {"$regex": q, "$options": "i"}}, {"email": {"$regex": q, "$options": "i"}}]}
    docs = get_documents("patient", filt, limit=100)
    return [serialize(d) for d in docs]


@app.get("/api/patients/{patient_id}")
def get_patient(patient_id: str):
    doc = db["patient"].find_one({"_id": oid(patient_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Patient not found")
    return serialize(doc)


# Appointments Endpoints
@app.post("/api/appointments")
def create_appointment(payload: Appointment):
    # Validate patient exists
    p = db["patient"].find_one({"_id": oid(payload.patient_id)})
    if not p:
        raise HTTPException(status_code=400, detail="Invalid patient_id")
    data = payload.model_dump()
    data["patient_id"] = payload.patient_id  # store as string for simplicity
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    result = db["appointment"].insert_one(data)
    doc = db["appointment"].find_one({"_id": result.inserted_id})
    return serialize(doc)


@app.get("/api/appointments")
def list_appointments(patient_id: Optional[str] = None, status: Optional[str] = None):
    filt: Dict[str, Any] = {}
    if patient_id:
        filt["patient_id"] = patient_id
    if status:
        filt["status"] = status
    docs = list(db["appointment"].find(filt).sort("scheduled_at", 1))
    return [serialize(d) for d in docs]


# Notes Endpoints
@app.post("/api/notes")
def create_note(payload: Note):
    # Validate patient exists
    p = db["patient"].find_one({"_id": oid(payload.patient_id)})
    if not p:
        raise HTTPException(status_code=400, detail="Invalid patient_id")
    data = payload.model_dump()
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    result = db["note"].insert_one(data)
    doc = db["note"].find_one({"_id": result.inserted_id})
    return serialize(doc)


@app.get("/api/notes")
def list_notes(patient_id: str = Query(...)):
    docs = list(db["note"].find({"patient_id": patient_id}).sort("created_at", -1))
    return [serialize(d) for d in docs]


# Symptom Checker (rule-based heuristic for MVP)
@app.post("/api/symptom-check")
def symptom_check(req: SymptomCheckRequest):
    symptoms = [s.strip().lower() for s in req.symptoms]

    rules = [
        {
            "condition": "Common Cold",
            "match_any": ["runny nose", "sneezing", "sore throat", "cough"],
            "advice": "Rest, fluids, OTC cold meds. See a clinician if symptoms persist >10 days or high fever.",
        },
        {
            "condition": "Influenza (Flu)",
            "match_any": ["fever", "body aches", "chills", "fatigue", "dry cough"],
            "advice": "Consider antiviral within 48h, rest and hydrate. Seek care if breathing difficulty.",
        },
        {
            "condition": "COVID-19",
            "match_any": ["fever", "loss of taste", "loss of smell", "dry cough", "shortness of breath"],
            "advice": "Consider rapid test, isolate if positive. Seek urgent care if severe breathlessness or chest pain.",
        },
        {
            "condition": "Migraine",
            "match_all": ["headache", "nausea"],
            "advice": "Rest in dark room, consider NSAIDs or triptans if previously prescribed.",
        },
        {
            "condition": "Gastroenteritis",
            "match_any": ["vomiting", "diarrhea", "stomach pain", "nausea"],
            "advice": "Oral rehydration, light diet. Seek care if bloody stool or dehydration.",
        },
        {
            "condition": "Allergic Rhinitis",
            "match_any": ["sneezing", "itchy eyes", "runny nose"],
            "advice": "Try antihistamines, nasal saline. Avoid triggers where possible.",
        },
        {
            "condition": "Strep Throat",
            "match_all": ["sore throat", "fever"],
            "advice": "Consider clinical testing. Avoid antibiotics without confirmation.",
        },
        {
            "condition": "Anxiety/Panic",
            "match_all": ["chest tightness", "shortness of breath"],
            "advice": "Practice slow breathing, seek professional evaluation if recurrent.",
        },
    ]

    matches = []
    for rule in rules:
        score = 0
        if "match_any" in rule:
            overlap = len([s for s in symptoms if s in rule["match_any"]])
            score += min(2, overlap)  # cap any-match contribution
        if "match_all" in rule:
            has_all = all(s in symptoms for s in rule["match_all"])
            score += 2 if has_all else 0
        if score > 0:
            matches.append({"condition": rule["condition"], "score": score, "advice": rule["advice"]})

    matches.sort(key=lambda x: x["score"], reverse=True)

    # Simple triage: risk score based on red-flag symptoms
    risk = "low"
    if any(s in symptoms for s in ["chest pain", "severe shortness of breath"]):
        risk = "high"
    elif any(s in symptoms for s in ["shortness of breath", "high fever", "bloody stool"]):
        risk = "moderate"

    guidance = "For emergencies (e.g., severe chest pain, severe breathing difficulty), call local emergency services immediately."

    return {
        "input": req.model_dump(),
        "risk": risk,
        "likely_conditions": matches[:5],
        "guidance": guidance,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
