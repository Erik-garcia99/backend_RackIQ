from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta, timezone
from app.models.product import Product
from app.models.sale import Sale
from app.models.branch import Branch
from app.models.rpi_models import Alert, Shelf
from app.schemas.sales import DashboardStatsResponse
import uuid

class DashboardService:
    @staticmethod
    def get_branch_stats(branch_id: str, db: Session) -> DashboardStatsResponse:
        try:
            branch_id_uuid = uuid.UUID(branch_id)
        except ValueError:
            return DashboardStatsResponse()

        branch = db.query(Branch).filter(Branch.id == branch_id_uuid).first()
        if not branch:
            return DashboardStatsResponse()

        # 1. INVENTARIO Y PRODUCTOS
        products = db.query(Product).filter(Product.branch_id == branch_id_uuid).all()
        inventory_value = sum(p.quantity_on_hand * p.unit_cost for p in products if p.quantity_on_hand > 0) or 0.0
        products_count = len(products)
        low_stock_count = sum(1 for p in products if p.quantity_on_hand <= p.reorder_level)

        # 2. VENTAS HOY
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        sales_today_query = db.query(Sale).filter(
            and_(Sale.branch_id == branch_id_uuid, Sale.created_at >= today_start, Sale.created_at <= today_end)
        ).all()
        sales_today = sum(s.total for s in sales_today_query) or 0.0
        sales_count_today = len(sales_today_query)

        # 3. MÁRGENES Y GRÁFICOS (Reducido por brevedad, usa tu misma lógica aquí...)
        margins = {"current_margin": 180.0, "margin_percentage": 74.0} # Mantén tu lógica original
        daily_sales_data = [{"day": "hoy", "value": sales_today}] # Mantén tu lógica original

        # 4. ALERTAS DINÁMICAS (NUEVO)
        open_alerts = db.query(Alert).filter(
            Alert.branch_id == branch_id_uuid, 
            Alert.status == 'open'
        ).order_by(Alert.triggered_at.desc()).all()

        formatted_alerts = []
        now_utc = datetime.now(timezone.utc)
        
        for a in open_alerts:
            # Calcular tiempo transcurrido
            time_diff = now_utc - a.triggered_at
            minutes_ago = int(time_diff.total_seconds() / 60)
            time_str = f"hace {minutes_ago} min" if minutes_ago < 60 else f"hace {minutes_ago // 60} hrs"

            # Buscar nombre del estante afectado
            shelf_name = "General"
            if a.shelf_id:
                shelf = db.query(Shelf).filter(Shelf.id == a.shelf_id).first()
                if shelf: shelf_name = shelf.name

            # Mapear urgencia según tu base de datos
            is_critical = a.alert_type in ['theft', 'anomaly']
            
            formatted_alerts.append({
                "type": "critica" if is_critical else "advertencia",
                "title": f"{'Robo hormiga' if is_critical else 'Falla/Offline'} — {shelf_name}",
                "description": "Atención requerida" if is_critical else "Revisar conexión",
                "time": time_str
            })

        return DashboardStatsResponse(
            inventory_value=round(inventory_value, 2),
            sales_today=round(sales_today, 2),
            sales_count_today=sales_count_today,
            products_count=products_count,
            low_stock_count=low_stock_count,
            daily_sales_data=daily_sales_data,
            sales_last_7_days=[],
            margins=margins,
            alerts=formatted_alerts # Se envían las alertas al frontend
        )
