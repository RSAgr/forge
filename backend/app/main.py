import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import create_token, hash_password, require_admin, verify_password
from app.config import settings
from app.database import SessionLocal, get_db, initialize_database
from app.models import Department, Grievance, GrievanceHistory, User
from app.schemas import DepartmentCreate, DepartmentOut, GrievanceOut, StatusUpdate
from app.services.analytics_service import dashboard_metrics
from app.services.geospatial_service import nearby_features, reverse_geocode
from app.services.grievance_service import analyze_report, create_report, update_status
from app.services.storage_service import store_image, validate_image
from app.services.weather_service import current_weather

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
STATUSES = {"Submitted", "AI Analysed", "Verified", "Assigned", "In Progress", "Resolved", "Rejected"}
CATEGORIES = {
    "Potholes and road damage", "Garbage accumulation", "Water leakage and flooding",
    "Broken streetlights", "Damaged public infrastructure", "Drainage and sewage problems",
    "Other civic issues",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    if settings.admin_email and settings.admin_password:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == settings.admin_email.lower()))
            if user is None:
                db.add(User(name="CivicLens Administrator", email=settings.admin_email.lower(),
                    password_hash=hash_password(settings.admin_password), role="admin"))
                db.commit()
    yield


app = FastAPI(title="CivicLens API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list({
    settings.app_base_url, "http://localhost:5173", "http://127.0.0.1:5173",
}), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=settings.storage_dir, check_dir=False), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/register")
def register(name: str = Form(min_length=2, max_length=120), email: str = Form(),
             password: str = Form(min_length=10), db: Session = Depends(get_db)):
    email = email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(name=name.strip(), email=email, password_hash=hash_password(password), role="citizen")
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_token(user), "token_type": "bearer", "role": user.role, "name": user.name}


@app.post("/api/auth/login")
def login(email: str = Form(), password: str = Form(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_token(user), "token_type": "bearer", "role": user.role, "name": user.name}


@app.post("/api/grievances", response_model=GrievanceOut)
async def submit_grievance(
    background_tasks: BackgroundTasks,
    category: str = Form(),
    description: str = Form(min_length=10, max_length=5000),
    latitude: float = Form(ge=-90, le=90),
    longitude: float = Form(ge=-180, le=180),
    address: str = Form(default="", max_length=500),
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    if category not in CATEGORIES:
        raise HTTPException(422, "Unsupported issue category")
    image_bytes, image_url, mime_type = None, None, None
    if image is not None:
        mime_type = image.content_type or ""
        image_bytes = await image.read(settings.max_upload_bytes + 1)
        if len(image_bytes) > settings.max_upload_bytes:
            raise HTTPException(413, "Image exceeds the upload limit")
        try:
            validate_image(image_bytes, mime_type)
            image_url = store_image(image_bytes, image.filename or "report.jpg", mime_type)
        except ValueError as exc:
            raise HTTPException(415, str(exc)) from exc
        except Exception as exc:
            logger.exception("Image storage failed")
            raise HTTPException(503, "Image storage is unavailable") from exc
    resolved_address = address.strip()
    if not resolved_address:
        try:
            resolved_address = await reverse_geocode(latitude, longitude)
        except Exception:
            logger.exception("Reverse geocoding failed")
    grievance = create_report(db, category, description.strip(), latitude, longitude, resolved_address, image_url)
    if grievance.status == "Submitted" and grievance.duplicate_of is None:
        background_tasks.add_task(analyze_report, grievance.id, image_bytes, mime_type)
    return grievance


@app.get("/api/grievances", response_model=list[GrievanceOut])
def list_grievances(category: str | None = None, severity: str | None = None, status: str | None = None,
                    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db)):
    query = select(Grievance).where(Grievance.duplicate_of.is_(None)).order_by(Grievance.created_at.desc())
    if category:
        query = query.where(Grievance.category == category)
    if severity:
        query = query.where(Grievance.severity == severity)
    if status:
        query = query.where(Grievance.status == status)
    return db.scalars(query.offset(offset).limit(limit)).all()


@app.get("/api/grievances/{grievance_number}", response_model=GrievanceOut)
def track_grievance(grievance_number: str, db: Session = Depends(get_db)):
    result = db.execute(select(Grievance).options(joinedload(Grievance.history), joinedload(Grievance.department))
        .where(Grievance.grievance_number == grievance_number.upper())).unique()
    grievance = result.scalar_one_or_none()
    if grievance is None:
        raise HTTPException(404, "Grievance not found")
    return grievance


@app.get("/api/grievances/{grievance_number}/history")
def grievance_history(grievance_number: str, db: Session = Depends(get_db)):
    grievance = db.scalar(select(Grievance).where(Grievance.grievance_number == grievance_number.upper()))
    if grievance is None:
        raise HTTPException(404, "Grievance not found")
    return db.scalars(select(GrievanceHistory).where(GrievanceHistory.grievance_id == grievance.id)
        .order_by(GrievanceHistory.created_at)).all()


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return dashboard_metrics(db)


@app.get("/api/map")
def map_reports(db: Session = Depends(get_db)):
    items = db.scalars(select(Grievance).where(Grievance.duplicate_of.is_(None))
        .order_by(Grievance.created_at.desc()).limit(1000)).all()
    return [{"id": item.id, "grievance_number": item.grievance_number,
        "latitude": item.latitude, "longitude": item.longitude, "category": item.category,
        "severity": item.severity, "status": item.status} for item in items]


@app.get("/api/geospatial/reverse")
async def reverse(latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180)):
    try:
        return {"display_name": await reverse_geocode(latitude, longitude)}
    except Exception as exc:
        logger.exception("Nominatim request failed")
        raise HTTPException(502, "Address lookup is unavailable") from exc


@app.get("/api/geospatial/nearby")
async def nearby(latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180)):
    try:
        return await nearby_features(latitude, longitude)
    except Exception as exc:
        logger.exception("Overpass request failed")
        raise HTTPException(502, "Nearby infrastructure service is unavailable") from exc


@app.get("/api/weather")
async def weather(latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180)):
    try:
        return await current_weather(latitude, longitude)
    except Exception as exc:
        logger.exception("Open-Meteo request failed")
        raise HTTPException(502, "Weather service is unavailable") from exc


@app.get("/api/departments", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db)):
    return db.scalars(select(Department).order_by(Department.name)).all()


@app.post("/api/admin/departments", response_model=DepartmentOut)
def add_department(data: DepartmentCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if db.scalar(select(Department).where(Department.name == data.name)):
        raise HTTPException(409, "Department already exists")
    item = Department(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/api/admin/departments/{department_id}", response_model=DepartmentOut)
def edit_department(department_id: int, data: DepartmentCreate, db: Session = Depends(get_db),
                    _=Depends(require_admin)):
    item = db.get(Department, department_id)
    if item is None:
        raise HTTPException(404, "Department not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/api/admin/grievances/{grievance_number}/status", response_model=GrievanceOut)
def change_status(grievance_number: str, data: StatusUpdate, db: Session = Depends(get_db),
                  admin: User = Depends(require_admin)):
    if data.status not in STATUSES:
        raise HTTPException(422, "Unsupported grievance status")
    item = db.scalar(select(Grievance).where(Grievance.grievance_number == grievance_number.upper()))
    if item is None:
        raise HTTPException(404, "Grievance not found")
    return update_status(db, item, data.status, data.remarks, admin.id)
