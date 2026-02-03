from fastapi import FastAPI

from app.db.base import Base
from app.db.session import engine
from app.routers.documents import router as documents_router
from app.routers.auth import router as auth_router

app = FastAPI(title="SED API")

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

app.include_router(auth_router)
app.include_router(documents_router)

@app.get("/")
def root():
    return {"status": "ok", "message": "SED API is running"}
