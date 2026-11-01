from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Department, Grievance, GrievanceHistory


def dashboard_metrics(db: Session) -> dict:
    total = db.scalar(select(func.count(Grievance.id))) or 0
    resolved = db.scalar(select(func.count(Grievance.id)).where(Grievance.status == "Resolved")) or 0
    open_count = db.scalar(select(func.count(Grievance.id)).where(Grievance.status.notin_(["Resolved", "Rejected"]))) or 0
    priority = db.scalar(select(func.count(Grievance.id)).where(Grievance.severity.in_(["Critical", "High"]))) or 0
    durations = db.execute(select(Grievance.created_at, GrievanceHistory.created_at)
        .join(GrievanceHistory, GrievanceHistory.grievance_id == Grievance.id)
        .where(GrievanceHistory.new_status == "Resolved")).all()
    elapsed = [(end - start).total_seconds() / 3600 for start, end in durations if end >= start]
    group = lambda col: db.execute(select(col, func.count(Grievance.id)).group_by(col)).all()
    return {
        "total": total, "open": open_count, "resolved": resolved, "priority": priority,
        "average_resolution_hours": round(sum(elapsed)/len(elapsed), 1) if elapsed else None,
        "categories": group(Grievance.category), "severities": group(Grievance.severity),
        "statuses": group(Grievance.status),
        "departments": db.execute(select(Department.name, func.count(Grievance.id))
            .join(Grievance, Grievance.assigned_department_id == Department.id)
            .group_by(Department.name).order_by(func.count(Grievance.id).desc())).all(),
        "trend": db.execute(select(func.date(Grievance.created_at), func.count(Grievance.id))
            .group_by(func.date(Grievance.created_at)).order_by(func.date(Grievance.created_at))).all(),
    }
