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
    def get_branch_stats(
        branch_id: str,
        db: Session,
        metric_type: str = "sales",
        time_range: str = "7d"
    ) -> DashboardStatsResponse:
        try:
            branch_id_uuid = uuid.UUID(branch_id)
        except ValueError:
            return DashboardStatsResponse()

        branch = db.query(Branch).filter(Branch.id == branch_id_uuid).first()
        if not branch:
            return DashboardStatsResponse()

        # 1. INVENTARIO Y PRODUCTOS
        products = db.query(Product).filter(Product.branch_id == branch_id_uuid, Product.is_active == True).all()
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

        # 3. MERMAS HOY (Movimientos de salida automáticos detectados por sensor hoy)
        from app.models.inventory import InventoryMovement
        mermas_query = db.query(InventoryMovement).join(Product).filter(
            and_(
                InventoryMovement.branch_id == branch_id_uuid,
                InventoryMovement.created_at >= today_start,
                InventoryMovement.created_at <= today_end,
                InventoryMovement.movement_type == 'out',
                InventoryMovement.reason == 'auto_detected_from_sensor'
            )
        ).all()
        mermas_today = sum(abs(m.quantity) * m.product.unit_cost for m in mermas_query if m.product) or 0.0

        # 4. SALUD DEL STOCK (Stock Saludable %)
        stock_prom_pct = 100.0
        if products_count > 0:
            stock_prom_pct = ((products_count - low_stock_count) / products_count) * 100.0

        margins = {
            "current_margin": round(mermas_today, 2),
            "margin_percentage": round(stock_prom_pct, 1)
        }

        # 5. ALERTAS DINÁMICAS
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

            # Mapear urgencia
            is_critical = a.alert_type in ['theft', 'anomaly']
            
            formatted_alerts.append({
                "type": "critica" if is_critical else "advertencia",
                "title": f"{'Robo hormiga' if is_critical else 'Falla/Offline'} — {shelf_name}",
                "description": "Atención requerida" if is_critical else "Revisar conexión",
                "time": time_str
            })

        # 6. GRÁFICOS DINÁMICOS CON AGRUPAMIENTO POR INTERVALO
        daily_sales_data = []
        is_demo = False

        # Determinar intervalos y etiquetas según time_range
        time_range = time_range.lower() if time_range else "7d"
        metric_type = metric_type.lower() if metric_type else "sales"

        intervals = []
        weekday_names = ["lun", "mart", "mie", "jue", "vie", "sab", "dom"]

        if time_range == "24h":
            # 8 intervalos de 3 horas
            for i in range(7, -1, -1):
                start_time = datetime.now() - timedelta(hours=(i+1)*3)
                end_time = datetime.now() - timedelta(hours=i*3)
                label = start_time.strftime("%H:%M")
                intervals.append((start_time, end_time, label))
        elif time_range == "30d":
            # 10 intervalos de 3 días
            for i in range(9, -1, -1):
                start_time = datetime.combine(datetime.now().date() - timedelta(days=(i+1)*3), datetime.min.time())
                end_time = datetime.combine(datetime.now().date() - timedelta(days=i*3), datetime.max.time())
                label = start_time.strftime("%d/%m")
                intervals.append((start_time, end_time, label))
        elif time_range == "3m":
            # 12 intervalos de 7 días (semanas)
            for i in range(11, -1, -1):
                start_time = datetime.combine(datetime.now().date() - timedelta(days=(i+1)*7), datetime.min.time())
                end_time = datetime.combine(datetime.now().date() - timedelta(days=i*7), datetime.max.time())
                label = f"Sem {12-i}"
                intervals.append((start_time, end_time, label))
        else:  # "7d" por defecto
            # 7 días individuales
            for i in range(6, -1, -1):
                day_date = datetime.now().date() - timedelta(days=i)
                start_time = datetime.combine(day_date, datetime.min.time())
                end_time = datetime.combine(day_date, datetime.max.time())
                label = "hoy" if i == 0 else weekday_names[day_date.weekday()]
                intervals.append((start_time, end_time, label))

        # Realizar consultas para cada intervalo
        for start, end, label in intervals:
            val = 0.0
            if metric_type == "sales":
                sales_query = db.query(Sale).filter(
                    and_(
                        Sale.branch_id == branch_id_uuid,
                        Sale.created_at >= start,
                        Sale.created_at <= end
                    )
                ).all()
                val = float(sum(s.total for s in sales_query) or 0.0)
            elif metric_type == "mermas":
                # Calcular mermas en el intervalo (retiros de sensor)
                from app.models.inventory import InventoryMovement
                mermas_interval_query = db.query(InventoryMovement).join(Product).filter(
                    and_(
                        InventoryMovement.branch_id == branch_id_uuid,
                        InventoryMovement.created_at >= start,
                        InventoryMovement.created_at <= end,
                        InventoryMovement.movement_type == 'out',
                        InventoryMovement.reason == 'auto_detected_from_sensor'
                    )
                ).all()
                val = float(sum(abs(m.quantity) * m.product.unit_cost for m in mermas_interval_query if m.product) or 0.0)
            else:  # activity
                # Contar movimientos de sensores (IN y OUT)
                activity_query = db.query(func.count(InventoryMovement.id)).filter(
                    and_(
                        InventoryMovement.branch_id == branch_id_uuid,
                        InventoryMovement.created_at >= start,
                        InventoryMovement.created_at <= end,
                        InventoryMovement.reason == 'auto_detected_from_sensor'
                    )
                ).scalar() or 0
                val = float(activity_query)

            daily_sales_data.append({"day": label, "value": val})



        return DashboardStatsResponse(
            inventory_value=round(inventory_value, 2),
            sales_today=round(sales_today, 2),
            sales_count_today=sales_count_today,
            products_count=products_count,
            low_stock_count=low_stock_count,
            daily_sales_data=daily_sales_data,
            sales_last_7_days=[],
            margins=margins,
            alerts=formatted_alerts,
            is_demo=is_demo
        )
