from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import documents, auth, dashboard

app = FastAPI(
    title="MDAV API",
    description="Multimodal Government Document Verification and Automated Authentication",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])


@app.get("/")
async def root():
    return {"message": "MDAV API is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
