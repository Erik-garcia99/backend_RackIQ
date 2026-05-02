import firebase_admin
from firebase_admin import credentials, messaging
import os
import json
from typing import Optional

# Ruta al archivo de credenciales de Firebase
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")

# Inicializar Firebase (solo si no está inicializado)
try:
    firebase_admin.get_app()
except ValueError:
    # La app no está inicializada
    try:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully")
    except FileNotFoundError:
        print(f"⚠️  Firebase credentials not found at {FIREBASE_CREDENTIALS_PATH}")
    except Exception as e:
        print(f"⚠️  Error initializing Firebase: {e}")


def send_push_notification(
    push_token: str,
    title: str,
    body: str,
    data: dict = None
) -> bool:
    """
    Envía una notificación push a un dispositivo específico.
    
    Args:
        push_token: Token FCM del dispositivo
        title: Título de la notificación
        body: Cuerpo/mensaje de la notificación
        data: Datos adicionales (optional)
    
    Returns:
        bool: True si se envió exitosamente, False si hubo error
    """
    if not push_token:
        print(f"⚠️  No push token provided for notification")
        return False
    
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=push_token,
        )
        response = messaging.send(message)
        print(f"✅ Notification sent successfully. Message ID: {response}")
        return True
    except messaging.UnregisteredError:
        print(f"⚠️  Token {push_token} is no longer registered")
        return False
    except messaging.InvalidArgumentError as e:
        print(f"⚠️  Invalid token or data: {e}")
        return False
    except Exception as e:
        print(f"❌ Error sending notification: {e}")
        return False


def send_multicast_notification(
    push_tokens: list,
    title: str,
    body: str,
    data: dict = None
) -> dict:
    """
    Envía una notificación a múltiples dispositivos.
    
    Args:
        push_tokens: Lista de tokens FCM
        title: Título
        body: Mensaje
        data: Datos adicionales
    
    Returns:
        dict: {success: int, failed: int}
    """
    if not push_tokens:
        return {"success": 0, "failed": 0}
    
    try:
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            tokens=push_tokens,
        )
        response = messaging.send_multicast(message)
        
        print(f"✅ Multicast sent: {response.success_count} successful, {response.failure_count} failed")
        return {"success": response.success_count, "failed": response.failure_count}
    except Exception as e:
        print(f"❌ Error sending multicast: {e}")
        return {"success": 0, "failed": len(push_tokens)}
