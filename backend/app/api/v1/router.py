from fastapi import APIRouter
from app.api.v1 import tokens, branches, auth, users, dashboard, organizations, rpi, inventory

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(tokens.router)
api_router.include_router(branches.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(organizations.router)
api_router.include_router(rpi.router)
api_router.include_router(inventory.router)