from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Department

ROUTES = {
    "Potholes and road damage": "Public Works Department",
    "Garbage accumulation": "Municipal Sanitation Department",
    "Water leakage and flooding": "Water Supply Department",
    "Broken streetlights": "Electrical Department",
    "Damaged public infrastructure": "Public Works Department",
    "Drainage and sewage problems": "Drainage and Sewerage Department",
    "Other civic issues": "Municipal Services Department",
}


def assign_department(db: Session, category: str) -> Department:
    name = ROUTES.get(category, ROUTES["Other civic issues"])
    department = db.scalar(select(Department).where(Department.name == name))
    if department is None:
        department = Department(name=name, verification_status="unverified")
        db.add(department)
        db.flush()
    return department
