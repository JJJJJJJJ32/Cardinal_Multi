from aiogram import Router

from .start import router as start_router
from .orders import router as orders_router
from .messages import router as messages_router
from .lots import router as lots_router
from .lolzteam_settings import router as lolzteam_router
from .ai_consultant import router as ai_router
from .stats import router as stats_router
from .balance import router as balance_router
from .logs import router as logs_router
from .settings import router as settings_router
from .diagnostics import router as diagnostics_router
from .backups import router as backups_router
from .notifications import router as notifications_router


def get_account_bot_router() -> Router:
    router = Router(name="account_bot")
    router.include_router(start_router)
    router.include_router(orders_router)
    router.include_router(messages_router)
    router.include_router(lots_router)
    router.include_router(lolzteam_router)
    router.include_router(ai_router)
    router.include_router(stats_router)
    router.include_router(balance_router)
    router.include_router(logs_router)
    router.include_router(settings_router)
    router.include_router(diagnostics_router)
    router.include_router(backups_router)
    router.include_router(notifications_router)
    return router