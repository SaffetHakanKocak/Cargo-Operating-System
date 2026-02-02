from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.api.v1.auth_router import router as auth_router
from app.api.v1.logistics_router import router as logistics_router
from app.db.base import Base
from app.db.session import engine

app = FastAPI(title="Yazlab3 Logistics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

Base.metadata.create_all(bind=engine)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(logistics_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")
