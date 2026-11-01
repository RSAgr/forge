import asyncio
import logging
import secrets
from datetime import datetime, timezone

from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models import Grievance, GrievanceHistory, GrievanceReport
from app.services.ai_service import analyze_issue
from app.services.duplicate_service import find_duplicate
from app.services.routing_service import assign_department
from app.services.severity_service import calculate_severity
from app.services.weather_service import current_weather

logger = logging.getLogger(__name__)


def create_report(db: Session, category: str, description: str, latitude: float, longitude: float,
                  address: str, image_url: str | None) -> Grievance:
    duplicate = find_duplicate(db, category, description, latitude, longitude)
    if duplicate:
        parent = duplicate.duplicate_parent or duplicate
        parent.report_count += 1
        db.add(GrievanceReport(grievance_id=parent.id, image_url=image_url, description=description))
        db.commit()
        db.refresh(parent)
        return parent
    department = assign_department(db, category)
    grievance = Grievance(
        grievance_number=f"CL-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(3).upper()}",
        category=category, description=description, image_url=image_url, latitude=latitude, longitude=longitude,
        location=WKTElement(f"POINT({longitude} {latitude})", srid=4326), address=address,
        assigned_department_id=department.id, status="Submitted", report_count=1,
    )
    db.add(grievance)
    db.flush()
    db.add(GrievanceHistory(grievance_id=grievance.id, new_status="Submitted", remarks="Report received"))
    db.add(GrievanceReport(grievance_id=grievance.id, image_url=image_url, description=description))
    db.commit()
    db.refresh(grievance)
    return grievance


async def analyze_report(grievance_id: int, image_bytes: bytes | None, mime_type: str | None) -> None:
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        grievance = db.get(Grievance, grievance_id)
        if grievance is None or grievance.duplicate_of is not None:
            return
        weather_context = {}
        try:
            current = (await current_weather(grievance.latitude, grievance.longitude)).get("current", {})
            weather_context = {"temperature_c": current.get("temperature_2m"),
                "rainfall_mm": current.get("rain", current.get("precipitation", 0)),
                "weather_code": current.get("weather_code")}
        except Exception:
            logger.exception("Weather context unavailable for %s", grievance_id)
        analysis = await asyncio.to_thread(analyze_issue, grievance.description, image_bytes, mime_type, weather_context)
        analysis["weather_context"] = weather_context
        old_status = grievance.status
        grievance.category = analysis["category"]
        grievance.severity_score, grievance.severity, grievance.severity_factors = calculate_severity(analysis)
        grievance.ai_analysis = analysis
        grievance.assigned_department_id = assign_department(db, grievance.category).id
        grievance.status = "AI Analysed"
        db.add(GrievanceHistory(grievance_id=grievance.id, previous_status=old_status,
            new_status=grievance.status, remarks="AI analysis completed"))
        db.commit()
    except Exception as exc:
        logger.exception("AI analysis failed for %s", grievance_id)
        db.rollback()
        grievance = db.get(Grievance, grievance_id)
        if grievance:
            grievance.processing_error = str(exc)
            db.commit()
    finally:
        db.close()


def update_status(db: Session, grievance: Grievance, status: str, remarks: str, updated_by: int) -> Grievance:
    previous = grievance.status
    grievance.status = status
    grievance.updated_at = datetime.now(timezone.utc)
    db.add(GrievanceHistory(grievance_id=grievance.id, previous_status=previous,
        new_status=status, updated_by=updated_by, remarks=remarks))
    db.commit()
    db.refresh(grievance)
    return grievance
