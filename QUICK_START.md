# GUÍA RÁPIDA: PRIMEROS PASOS PARA RAILWAY + SUPABASE

## 🏗️ Arquitectura

```
Desarrollo Local              Producción
─────────────────             ──────────
PostgreSQL local ─────────┐   
Backend local   ──────────┼──→ Railway Backend
docker-compose  ────────┐ │    │
                        │ └────→ Supabase PostgreSQL
```

**Importante:**
- `docker-compose.yml` = Solo para desarrollo local
- Railway = NO ejecuta docker-compose
- Railway = Conecta a Supabase (base de datos externa)

---

## 📋 Checklist (En orden)

### PASO 0: Crear Supabase Database (ANTES de Railway)
- [ ] Crear cuenta en [Supabase.com](https://supabase.com)
- [ ] New Project → Copiar `DATABASE_URL` (PostgreSQL connection string)
- [ ] Guardar la URL en lugar seguro (necesitarás en Railway)
- [ ] Crear las tablas/migraciones en Supabase (si las tienes, ejecutar SQL)

### PASO 1: Limpieza Local (5 minutos)
- [ ] Crear `.env` local con tus valores reales (copia de `.env.example`)
- [ ] Poner `DATABASE_URL` de Supabase en `.env` (para testing)
- [ ] Descargar `firebase-credentials.json` desde Firebase Console
- [ ] Verificar que `.gitignore` existe y contiene los archivos sensibles
- [ ] Ejecutar `git status` y confirmar que NO ve `.env` ni `firebase-credentials.json`

### PASO 2: Setup GitHub (5 minutos)
- [ ] Si no tienes repo: `git init && git remote add origin https://github.com/...`
- [ ] `git add .` (con `.gitignore` activo)
- [ ] `git commit -m "Initial commit: Backend con Supabase"`
- [ ] `git push -u origin main`
- [ ] Verificar en GitHub que NO ves archivos `.env`

### PASO 3: Setup Railway (10 minutos)
- [ ] Crear cuenta en [Railway.app](https://railway.app/)
- [ ] New Project → GitHub Repo → conectar tu repo
- [ ] **NO agregar PostgreSQL en Railway** (usarás Supabase)
- [ ] Add Environment Variables en el backend (ver sección 4.4)
- [ ] Deploy (automático)

### PASO 4: Verificación
- [ ] Railway muestra "Deployment Success"
- [ ] Backend conecta a Supabase correctamente
- [ ] Probar endpoint `/health` con curl

---

## 🔑 Variables de Entorno (Copia-Pega)

### En tu `.env` local:
```env
DATABASE_URL=postgresql://postgres:SUPABASE_PASSWORD@db.SUPABASE_ID.supabase.co:5432/postgres
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
SECRET_KEY=tu-clave-aleatoria-aqui
ENVIRONMENT=development
DEBUG=True
```

**OBTENER `DATABASE_URL` de Supabase:**
1. Ir a [Supabase Dashboard](https://app.supabase.com)
2. Tu proyecto → Settings → Database
3. Connection string → PostgreSQL
4. Copiar la URL completa

### En Railway Dashboard (Backend Service):
```
DATABASE_URL = postgresql://postgres:PASSWORD@db.SUPABASE_ID.supabase.co:5432/postgres
FIREBASE_CREDENTIALS_PATH = ./firebase-credentials.json
SECRET_KEY = (copia del .env local)
ENVIRONMENT = production
DEBUG = False
ALLOWED_ORIGINS = https://tu-frontend.com,https://tu-app.railway.app
```

---

## ⚠️ Lo MÁS Importante

1. **`.env` NUNCA en Git** - está en `.gitignore`
2. **`firebase-credentials.json` NUNCA en Git** - está en `.gitignore`
3. **`docker-compose.yml` SÍ va en Git** - es para desarrollo local
4. **Verifica:** `git ls-files | grep firebase` = vacío ✅
5. **Verifica:** `git ls-files | grep ".env"` = vacío (menos .env.example) ✅

---

## 🚀 Comando para Verificar Todo

```bash
# Verifica que archivos sensibles NO están en Git
git ls-files | grep -E "\.(env|json)" | grep -E "(firebase|credentials|\.env$)"

# Si la salida está VACÍA = correcto ✅
# Si aparecen archivos = problema ⚠️
```

---

## 📚 Documentación Completa

Ver [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) para detalles completos sobre Supabase, Firebase, Railway.
