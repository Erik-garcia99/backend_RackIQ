from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.models.branch import Branch
from app.schemas.sales import DashboardStatsResponse
import uuid

class DashboardService:
    @staticmethod
    def get_branch_stats(branch_id: str, db: Session) -> DashboardStatsResponse:
        """
        Obtiene estadísticas del dashboard para una sucursal.
        Si no hay datos, retorna valores por defecto (0).
        """
        try:
            branch_id_uuid = uuid.UUID(branch_id)
        except ValueError:
            return DashboardStatsResponse()

        # Verificar que la sucursal existe
        branch = db.query(Branch).filter(Branch.id == branch_id_uuid).first()
        if not branch:
            return DashboardStatsResponse()

        # ──── INVENTARIO ────
        products = db.query(Product).filter(Product.branch_id == branch_id_uuid).all()
        inventory_value = sum(
            p.quantity_on_hand * p.unit_cost for p in products if p.quantity_on_hand > 0
        ) or 0.0
        products_count = len(products)
        low_stock_count = sum(1 for p in products if p.quantity_on_hand <= p.reorder_level)

        # ──── VENTAS HOY ────
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        sales_today_query = db.query(Sale).filter(
            and_(
                Sale.branch_id == branch_id_uuid,
                Sale.created_at >= today_start,
                Sale.created_at <= today_end,
            )
        ).all()

        sales_today = sum(s.total for s in sales_today_query) or 0.0
        sales_count_today = len(sales_today_query)

        # ──── ÚLTIMOS 7 DÍAS ────
        seven_days_ago = today - timedelta(days=6)
        sales_last_7_days = db.query(
            func.date(Sale.created_at).label("date"),
            func.sum(Sale.total).label("total")
        ).filter(
            and_(
                Sale.branch_id == branch_id_uuid,
                Sale.created_at >= seven_days_ago,
            )
        ).group_by(func.date(Sale.created_at)).all()

        # Formato para gráfico (últimos 7 días)
        daily_sales_data = []
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            day_name = date.strftime("%a").lower()[:3]
            value = next((float(s.total) for s in sales_last_7_days if s.date == date), 0.0)
            daily_sales_data.append({
                "day": day_name,
                "value": value
            })

        # ──── MÁRGENES ────
        total_cost = sum(
            si.quantity * si.unit_price for sale in sales_today_query 
            for si in sale.items
        ) or 0.0
        margins = {
            "current_margin": (sales_today - total_cost) if sales_today > 0 else 0.0,
            "margin_percentage": ((sales_today - total_cost) / sales_today * 100) if sales_today > 0 else 0.0,
        }

        return DashboardStatsResponse(
            inventory_value=round(inventory_value, 2),
            sales_today=round(sales_today, 2),
            sales_count_today=sales_count_today,
            products_count=products_count,
            low_stock_count=low_stock_count,
            daily_sales_data=daily_sales_data,
            sales_last_7_days=[
                {"date": str(s.date), "total": float(s.total)} 
                for s in sales_last_7_days
            ],
            margins=margins
        )
