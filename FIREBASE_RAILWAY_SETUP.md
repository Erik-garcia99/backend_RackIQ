# 🔐 Setup de Firebase en Railway

Tu código ya está configurado. Solo necesitas 3 pasos:

## Paso 1: Obtener JSON de Firebase

1. Ve a [Firebase Console](https://console.firebase.google.com/) → Proyecto RackIQ
2. **Configuración del proyecto** (⚙️) → **Cuentas de servicio**
3. Click en **"Generar nueva clave privada"** → Se descargará un JSON

## Paso 2: Colocar en Railway

1. Abre [Railway.app](https://railway.app/) → Tu proyecto
2. Selecciona el servicio "Backend" (o el que uses)
3. Ve a la pestaña **Variables**
4. Click en **+ New Variable**
5. Rellena así:
   - **Name:** `FIREBASE_CREDENTIALS_JSON`
   - **Value:** Copia TODO el contenido del JSON descargado (como una línea única, sin saltos)

Ejemplo:
```
FIREBASE_CREDENTIALS_JSON = {"type":"service_account","project_id":"rackiq-xxxxx","private_key_id":"abc123",...}
```

## Paso 3: Listo ✅

El código backend ya está configurado para leer esta variable.
Tu Firebase funcionará en Railway automáticamente.

---

## Para Desarrollo Local (Opcional)

Si quieres usar Firebase en tu máquina:

1. Descarga el JSON desde Firebase Console
2. Cópialo a `backend_RackIQ/backend/` con el nombre `firebase-credentials.json`
3. Crea un `.env` en `backend_RackIQ/` con:
   ```
   FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
   ```

El código detectará automáticamente el archivo local.

---

## 🔒 Seguridad

- ✅ El archivo `.gitignore` previene que el JSON se suba a GitHub
- ✅ Las credenciales en Railway están inyectadas en tiempo de ejecución
- ✅ Nunca compartas la variable de entorno FIREBASE_CREDENTIALS_JSON públicamente

## ❓ Problemas Comunes

### Error: "Firebase credentials not found"
- Revisa que la variable `FIREBASE_CREDENTIALS_JSON` esté en Railway
- Confirma que el JSON es válido (sin saltos de línea)

### Error: "Invalid JSON"
- Asegúrate de que el JSON está en UNA SOLA LÍNEA
- No incluyas saltos de línea dentro de la variable

### Funciona local pero no en Railway
- Revisa los logs de Railway para ver el error exacto
- Confirma que la variable está agregada en el Dashboard
