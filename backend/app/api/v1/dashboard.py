from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.branch import Branch
from app.schemas.branch import BranchResponse
from app.schemas.sales import DashboardStatsResponse
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/{branch_id}/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(branch_id: str, db: Session = Depends(get_db)):
    """
    Obtiene las estadísticas del dashboard para una sucursal.
    Si no hay datos, retorna valores por defecto ($0, 0, etc.)
    """
    stats = DashboardService.get_branch_stats(branch_id, db)
    return stats
