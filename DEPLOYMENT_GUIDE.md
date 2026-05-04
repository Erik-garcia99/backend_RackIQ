# Guía de Deployment en Railway + Supabase

## 🏗️ Arquitectura General

```
┌─────────────────────────────────────────────┐
│    TU MÁQUINA LOCAL (DESARROLLO)            │
│  docker-compose.yml                         │
│  ├─ PostgreSQL local (para desarrollo)      │
│  └─ Backend local (FastAPI)                 │
│  Usa: .env con DATABASE_URL local           │
└─────────────────────────────────────────────┘
                  ↓ (git push)
┌─────────────────────────────────────────────┐
│    GITHUB (Tu repositorio)                  │
│  ✓ Código del backend                       │
│  ✓ docker-compose.yml (para documentación)  │
│  ✗ .env (protegido por .gitignore)          │
│  ✗ firebase-credentials.json (protegido)    │
└─────────────────────────────────────────────┘
                  ↓ (GitHub → Railway)
┌─────────────────────────────────────────────┐
│    RAILWAY (Hosting del Backend)            │
│  Ejecuta: Dockerfile (NO docker-compose)    │
│  Conecta a: Supabase (BASE DE DATOS)        │
│  Variables: DATABASE_URL de Supabase        │
└─────────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│    SUPABASE (Base de datos PostgreSQL)      │
│  PostgreSQL alojada en la nube              │
│  Accesible desde: Railway backend           │
└─────────────────────────────────────────────┘
```

**RESUMEN CLAVE:**
- `docker-compose.yml` = SOLO para desarrollo local (no se usa en Railway)
- Railway = Ejecuta `Dockerfile` directamente
- Supabase = Tu base de datos en producción
- El código ya soporta esto con variables de entorno ✓

### 1.1 Credenciales NUNCA deben ir en Git

Las siguientes carpetas y archivos están en `.gitignore`:
- `.env` - Variables de entorno locales
- `firebase-credentials.json` - Credenciales de Firebase
- `service-account-key.json` - Claves de servicio

### 1.2 Flujo de Credenciales Correcto

```
┌─────────────────────────────────────────────────────┐
│         TU MÁQUINA LOCAL (DESARROLLO)               │
│  .env (LOCAL) → variables de entorno locales        │
│  firebase-credentials.json (LOCAL) → desarrollo     │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│              REPOSITORIO GIT (GITHUB)               │
│  .gitignore previene que sientas credenciales      │
│  .env.backend.example muestra la estructura (SIN valores)  │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│           RAILWAY (PRODUCCIÓN)                      │
│  Variables de entorno configuradas en el dashboard  │
│  Credenciales inyectadas en tiempo de ejecución    │
└─────────────────────────────────────────────────────┘
```

## 2. PASO 1: PREPARAR TU REPOSITORIO EN GIT

### 2.1 Crear el repositorio (si no existe)

```bash
# En tu carpeta del proyecto
git init
git add .
git commit -m "Initial commit: RackIQ Backend"
git branch -M main
git remote add origin https://github.com/tu-usuario/tu-repo.git
git push -u origin main
```

### 2.2 Verificar que `.gitignore` está en su lugar

```bash
# Confirmar que Git ignora los archivos sensibles
git status

# No deberías ver:
# - .env
# - firebase-credentials.json
# - database/
```

## 3. PASO 2: CONFIGURAR CREDENCIALES LOCALMENTE

### 3.1 Crear `.env` local (NO lo subas a Git)

```bash
# Copia .env.backend.example
cp .env.backend.example .env

# Edita con tus valores reales
nano .env
```

Contenido de `.env` con valores reales:

```env
# Base de datos PostgreSQL - Puede ser:
# A) Supabase (si quieres probar en local contra Supabase)
# DATABASE_URL=postgresql://postgres:PASSWORD@db.SUPABASE_ID.supabase.co:5432/postgres
#
# B) PostgreSQL Local (desde docker-compose up)
# DATABASE_URL=postgresql://postgres:best4ever@localhost:5432/rackiq_db

DATABASE_URL=postgresql://postgres:best4ever@localhost:5432/rackiq_db

# Firebase (descarga el JSON de Firebase Console)
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json

# JWT
SECRET_KEY=tu-clave-secreta-muy-larga-y-aleatoria

# API
API_PREFIX=/api/v1
PROJECT_NAME=RackIQ API

# Entorno
ENVIRONMENT=development
DEBUG=True
```

### 3.2 Descargar credenciales de Firebase

1. Ir a [Firebase Console](https://console.firebase.google.com/)
2. Proyecto → Configuración del Proyecto
3. Pestaña "Cuentas de Servicio"
4. Click en "Generar nueva clave privada"
5. Guardar el JSON como `firebase-credentials.json` en la raíz de `backend/`
6. **⚠️ NUNCA lo subas a Git**

### 3.3 Generar SECRET_KEY para JWT

```python
# En Python
import secrets
print(secrets.token_urlsafe(32))
```

O en terminal:

```bash
# Linux/Mac
openssl rand -hex 32

# Windows PowerShell
[System.Convert]::ToBase64String((1..32 | ForEach-Object {Get-Random -Maximum 256}))
```

## 4. PASO 3: CONFIGURAR RAILWAY + SUPABASE

### 4.1 Crear cuenta en Railway

1. Ir a [Railway.app](https://railway.app/)
2. Sign up con GitHub
3. Crear un nuevo proyecto

### 4.2 Conectar GitHub a Railway

1. En Railway: New Project → GitHub Repo
2. Autorizar Railway en GitHub
3. Seleccionar tu repositorio `backend_RackIQ`
4. Railway detectará automáticamente el Dockerfile

### 4.3 IMPORTANTE: NO Agregar PostgreSQL a Railway

⚠️ **ESTO ES CLAVE:**
- **NO hagas:** Add Service → PostgreSQL en Railway
- **RAZÓN:** Usarás Supabase como tu base de datos (más barato, mejor para prod)
- **en su lugar:** La base de datos estará en Supabase (sección 4.4 abajo)

### 4.4 Obtener DATABASE_URL de Supabase

1. Crear cuenta en [Supabase.com](https://supabase.com) (gratuito)
2. New Project → Selecciona región (ej: us-east-1)
3. Espera a que se cree (2-3 minutos)
4. Dashboard → Settings → Database
5. Connection strings → PostgreSQL
6. Copia la URL completa (debería verse así):
   ```
   postgresql://postgres:[PASSWORD]@db.[ID].supabase.co:5432/postgres
   ```
7. Guarda esta URL en lugar seguro (la necesitarás en Railway)

**IMPORTANTE:**
- La contraseña está en esa URL
- **NO la subas a Git**
- **SÍ la copias en Railway**
- Si necesitas resetear contraseña: Settings → Database → Reset password

### 4.5 Configurar Variables de Entorno en Railway

En el Dashboard de Railway, ir al Backend Service y agregar estas variables:

**Backend Service - Variables de Entorno:**
```
DATABASE_URL = postgresql://postgres:[PASSWORD]@db.[SUPABASE_ID].supabase.co:5432/postgres
FIREBASE_CREDENTIALS_JSON = {"type":"service_account","project_id":"..."}
SECRET_KEY = (tu clave generada)
ALGORITHM = HS256
ENVIRONMENT = production
DEBUG = False
ALLOWED_ORIGINS = https://backendrackiq-production.up.railway.app
```

⚠️ **Para FIREBASE_CREDENTIALS_JSON:**
- Copia TODO el JSON desde Firebase Console (sin saltos de línea)
- Pégalo como una sola línea en Railway

⚠️ **IMPORTANTE**: 
- El `DATABASE_URL` viene de Supabase, NO de Railway
- No copies/pegues en el navegador si puedes
- Copia desde Supabase Settings → Database → Connection strings
- **ALLOWED_ORIGINS** debe incluir tu dominio de Railway para que el frontend pueda hacer peticiones

## 5. PASO 4: CONFIGURAR FIREBASE EN RAILWAY

Firebase soporta 2 formas de cargar credenciales:

### Opción A: Credenciales como Variable de Entorno JSON (Recomendado para Railway)

**En Firebase Console:**
1. Ve a **Configuración del proyecto** (⚙️) → **Cuentas de servicio**
2. Click en **"Generar nueva clave privada"**
3. Descarga el archivo JSON

**En Railway:**
1. Abre tu Backend Service en el Dashboard
2. Ve a **Variables**
3. Agrega una nueva variable:
   - **Nombre:** `FIREBASE_CREDENTIALS_JSON`
   - **Valor:** Copia TODO el contenido del JSON descargado (sin saltos de línea)

**En el código FastAPI:**
El código ya está configurado para leer esta variable automáticamente. No necesitas cambios.

### Opción B: Credenciales desde Archivo Local (Para Desarrollo)

Si ejecutas localmente:
1. Descarga `firebase-credentials.json` desde Firebase Console
2. Cópialo a la carpeta `backend_RackIQ/backend/`
3. Tu archivo `.env` local puede usar:
   ```
   FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
   ```
4. O dejar vacía y que use el default

## 6. PASO 5: VERIFICAR CONEXIÓN A SUPABASE

Tu base de datos ya está en Supabase. No necesitas nada adicional.

### Verificar que funciona en Railway:

1. Ve a Railway Dashboard → tu proyecto
2. Abre los logs del Backend
3. Busca un mensaje de conexión exitosa a la base de datos
4. Prueba el endpoint `/health` desde Railway:
   ```bash
   curl https://tu-app.railway.app/health
   ```
5. Debería retornar:
   ```json
   {
     "status": "ok",
     "service": "RackIQ API",
     "environment": "production"
   }
   ```

### Si falla la conexión a Supabase:

1. Verifica que `DATABASE_URL` está correcto en Railway
2. Verifica que la contraseña de Supabase es correcta
3. Verifica que Supabase permite conexiones externas (Settings → Database → Firewall)
4. Revisa los logs en Railway para ver el error exacto

## 7. PASO 6: DEPLOY INICIAL

### Flujo de Deploy

1. **Supabase:** Ya está creada y con DATABASE_URL listo
2. **GitHub:** Hiciste push del código (sin .env ni firebase-credentials.json)
3. **Railway:** 
   - Detecta nuevo push en GitHub
   - Descarga el Dockerfile
   - Construye la imagen Docker
   - Inyecta variables de entorno (incluyendo DATABASE_URL de Supabase)
   - Ejecuta el container

### Primera vez:

1. En Railway: New Project → selecciona tu GitHub repo
2. Railway automáticamente detecta que hay Dockerfile
3. Agrega las variables de entorno (DATABASE_URL de Supabase, SECRET_KEY, etc.)
4. Haz clic en Deploy (o se dispara automáticamente con git push)

### Monitorear el Deploy:

1. Railway dashboard → Deployments tab
2. Ver log en tiempo real
3. Esperar a que muestre "Success"

### Si falla el Deploy:

**Error común 1: "Cannot connect to database"**
- Revisa que `DATABASE_URL` es correcto (de Supabase)
- Revisa que la contraseña es válida
- Supabase puede requerir agregar Railway IP a firewall

**Error común 2: "Module not found"**
- Verifica que `requirements.txt` está en `backend/`
- Verifica que Dockerfile copia correctamente

**Error común 3: "Port already in use"**
- Railway automáticamente asigna PORT
- No hardcodees puerto en el código (ya está en Dockerfile)

## 8. MEJORES PRÁCTICAS

### ✅ HAZLO

- ✅ Usa `.env.backend.example` como plantilla (sin valores reales)
- ✅ Agrega todos los archivos sensibles a `.gitignore`
- ✅ Genera claves secretas aleatorias por entorno
- ✅ Usa variables de entorno para TODO (DATABASE_URL, KEYS, etc.)
- ✅ Configura CORS solo con dominios permitidos en producción
- ✅ Usa HTTPS en producción (Railway proporciona gratis)
- ✅ Rota credenciales regularmente
- ✅ Monitorea los logs de Railway
- ✅ Para producción, usa Supabase (PostgreSQL en la nube) - NO guardes BD en Railway
- ✅ `docker-compose.yml` está en Git (para desarrollo local), pero NO en Railway

### ❌ NO LO HAGAS

- ❌ Hardcodea credenciales en `config.py` o `main.py`
- ❌ Subas `.env` a Git
- ❌ Subas `firebase-credentials.json` a Git
- ❌ Confíes en `.gitignore` solo - revisa `git status`
- ❌ Reutilices mismas contraseñas en dev/test/prod
- ❌ Uses `CORS allow_origins=["*"]` en producción
- ❌ Comitas claves privadas
- ❌ Uses PostgreSQL de Railway en producción (caro y efímero)
- ❌ Intentes ejecutar `docker-compose` en Railway

## 9. RENOVACIÓN DE CREDENCIALES

### Cuando cambies contraseña de Firebase:

1. Actualiza en Firebase Console
2. Descarga nuevo JSON
3. Actualiza `.env` local
4. Actualiza variables en Railway
5. NO subas a Git

### Cuando cambies contraseña de Supabase (PostgreSQL):

1. Actualiza en Supabase Console → Settings → Database → Reset password
2. Supabase genera nuevo `DATABASE_URL`
3. Actualiza `.env` local con nuevo DATABASE_URL
4. Actualiza en Railway: Backend Service → variables → DATABASE_URL
5. Railway automáticamente redeploya con nueva conexión
6. NO subas la contraseña a Git

## 10. VERIFICACIÓN FINAL (Antes de Producción)

```bash
# 1. Verificar que credenciales NO están en Git
git ls-files | grep -E "\.env|firebase-credentials|service-account"
# Resultado: (vacío - es correcto)

# 2. Verificar que .env existe localmente
ls -la .env
# Resultado: .env (sin versión en Git)

# 3. Verificar que config.py usa variables de entorno
grep "os.getenv" backend/app/core/config.py
# Resultado: múltiples líneas con getenv

# 4. Verificar DATABASE_URL de Supabase
echo $DATABASE_URL  # En Windows: echo %DATABASE_URL%
# Resultado: postgresql://postgres:...@db.*.supabase.co:...

# 5. Ejecutar localmente con docker-compose + .env
docker-compose up
# Debe conectarse sin errores de credenciales

# 6. En Railway: verificar deployment exitoso
# Railway Dashboard → Deployments → Status: "Success"
# Railway Dashboard → Logs → Ver que conecta a Supabase

# 7. Probar endpoint en Railway
curl https://tu-app.railway.app/health
# Resultado: {"status": "ok", ...}
```

---

**¿Preguntas?** Revisa la sección específica arriba o contacta a tu equipo DevOps.
