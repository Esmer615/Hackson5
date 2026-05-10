from ninja import NinjaAPI

from apps.core.api import router as core_router
from apps.textbooks.api import router as textbooks_router

api = NinjaAPI(title="Hackson5 API", version="1.0.0")

api.add_router("", core_router)
api.add_router("", textbooks_router)
