from fastapi import APIRouter
from sqlalchemy import func, select

from backend.api.dependencies import DatabaseSession
from backend.db.models import Location
from backend.api.routes.common import Limit, Offset
from backend.api.schemas import LocationResponse, Page

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=Page[LocationResponse])
def list_locations(session: DatabaseSession, limit: Limit = 50, offset: Offset = 0):
    total = session.scalar(select(func.count()).select_from(Location))
    rows = session.execute(
        select(Location.__table__).order_by(Location.name, Location.id).limit(limit).offset(offset)
    ).mappings().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}
