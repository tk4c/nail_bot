# ============================================================
# handlers/__init__.py — Регистрация всех роутеров
# ============================================================

from handlers.user import router as user_router
from handlers.admin import router as admin_router
from handlers.subscription import router as subscription_router

__all__ = ["user_router", "admin_router", "subscription_router"]
