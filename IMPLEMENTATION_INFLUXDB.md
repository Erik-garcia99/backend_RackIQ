# Implementación - InfluxDB + Detección de Movimientos

## ✅ Cambios realizados:

### 1. **Configuración Backend**
- ✅ Agregadas variables de InfluxDB a `app/core/config.py`
- ✅ Agregadas variables de Celery a `app/core/config.py`

### 2. **Modelo de Datos**
- ✅ Agregado campo `last_recorded_units` a modelo `Shelf` para tracking de unidades

### 3. **Servicio InfluxDB**
- ✅ Creado `app/services/influx_detector.py`
  - `get_current_weight()`: Obtiene peso actual de InfluxDB
  - `detect_movement()`: Detecta cambios en un estante
  - `detect_all_movements()`: Detecta en todos los estantes
  - `change_product()`: Cambia producto sin generar evento falso

### 4. **Endpoints API**
- ✅ Creado `app/api/v1/inventory.py` con:
  - `GET /api/v1/inventory/shelf/{shelf_id}/status` - Estado online/offline
  - `GET /api/v1/inventory/branch/{branch_id}/shelves` - Estado de todos los estantes
  - `GET /api/v1/inventory/branch/{branch_id}/movements` - Historial de movimientos
  - `POST /api/v1/inventory/shelf/{shelf_id}/change-product` - Cambiar producto
  - `POST /api/v1/inventory/detect-all-movements` - Test endpoint

### 5. **Schemas**
- ✅ Creado `app/schemas/inventory.py` con modelos Pydantic

### 6. **Tareas Asincrónicas (Celery)**
- ✅ Creado `app/workers/celery_app.py` - Configuración de Celery
- ✅ Creado `app/workers/inventory_tasks.py` - Tarea de detección periódica
- ✅ Tarea se ejecuta cada 30 segundos automáticamente

### 7. **Router**
- ✅ Actualizado `app/api/v1/router.py` para incluir endpoints de inventory

---

## 📦 Dependencias necesarias:

```bash
# En requirements.txt agregar:
influxdb-client==1.36.0
celery==5.3.4
redis==5.0.1
```

O instalar directamente:
```bash
pip install influxdb-client celery redis
```

---

## 🚀 Cómo ejecutar:

### **Opción 1: Sin Celery (Simple - Testing)**
```bash
# Backend solamente
cd backend_RackIQ/backend
python -m uvicorn app.main:app --reload
```

Prueba manualmente:
```bash
curl http://localhost:8000/api/v1/inventory/detect-all-movements
```

### **Opción 2: Con Celery (Producción)**

**Requiere Redis:**
```bash
# En Windows
redis-server

# O en WSL
wsl redis-server
```

**Terminal 1 - Backend:**
```bash
cd backend_RackIQ/backend
python -m uvicorn app.main:app --reload
```

**Terminal 2 - Celery Worker:**
```bash
cd backend_RackIQ/backend
celery -A app.workers.celery_app worker --loglevel=info
```

**Terminal 3 - Celery Beat (Scheduler):**
```bash
cd backend_RackIQ/backend
celery -A app.workers.celery_app beat --loglevel=info
```

---

## 📊 Arquitectura del flujo:

```
RPi (Edge Computing)
    ↓ [Envía peso cada 60s]
InfluxDB
    ↓ [Backend chequea cada 30s]
Celery Task (cada 30s)
    ↓ [Consulta InfluxDB + Supabase]
Backend detecta movimientos
    ↓ [Si cambio >= 1 unidad]
Supabase InventoryMovement
    ↓ [Frontend consulta]
Frontend (tiempo quasi-real)
```

---

## 🔍 Variables de Entorno (.env)

```bash
# InfluxDB
INFLUX_URL=https://us-east-1-1.aws.cloud2.influxdata.com
INFLUX_TOKEN=tu_token_aqui
INFLUX_ORG=rackiq
INFLUX_BUCKET=inventario_estantes

# Celery (si usas Redis)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## ✅ Lo que hace cada componente:

| Componente | Qué hace | Dónde |
|-----------|----------|-------|
| **InfluxDetector** | Consulta InfluxDB, calcula unidades, detecta cambios | `services/influx_detector.py` |
| **Endpoints** | Expone datos de status y movimientos al frontend | `api/v1/inventory.py` |
| **Celery Task** | Ejecuta detección cada 30 segundos automáticamente | `workers/inventory_tasks.py` |
| **Modelo Shelf** | Guarda `last_recorded_units` para comparación | `models/rpi_models.py` |
| **Supabase** | Almacena movimientos detectados | Base de datos |

---

## 🧪 Testing rápido:

```bash
# Ver estado actual de un estante
curl http://localhost:8000/api/v1/inventory/shelf/SHELF_ID/status

# Ver todos los estantes de una sucursal
curl http://localhost:8000/api/v1/inventory/branch/BRANCH_ID/shelves

# Ver historial de movimientos
curl http://localhost:8000/api/v1/inventory/branch/BRANCH_ID/movements?days=7

# Cambiar producto de un estante
curl -X POST http://localhost:8000/api/v1/inventory/shelf/SHELF_ID/change-product \
  -H "Content-Type: application/json" \
  -d '{"new_product_id": "NEW_PRODUCT_UUID"}'
```

---

## ⚠️ Importante:

1. **InfluxDB debe estar corriendo** y con datos siendo escritos por la RPi
2. **Redis es opcional** - sin él, las tareas se ejecutan en modo síncrono
3. **Todos los pesos vienen de InfluxDB** - no hay valores hardcodeados
4. **Todos los productos vienen de Supabase** - puedes cambiarlos sin código
5. **Los movimientos se registran SOLO si hay cambio >= 1 unidad**

---

¿Listo para probar?
