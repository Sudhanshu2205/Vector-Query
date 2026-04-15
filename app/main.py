import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware


def _get_dotenv_encodings(env_path: Path) -> list[str]:
    """Detect likely encodings for dotenv files created on different platforms."""
    file_prefix = env_path.read_bytes()[:4]

    if file_prefix.startswith((b"\xff\xfe", b"\xfe\xff")):
        return ["utf-16", "utf-8-sig", "utf-8"]
    if file_prefix.startswith(b"\xef\xbb\xbf"):
        return ["utf-8-sig", "utf-8", "utf-16"]
    return ["utf-8", "utf-8-sig", "utf-16"]


def _load_environment(env_path: Path) -> None:
    """Load environment variables while tolerating common Windows encodings."""
    last_error = None

    for encoding in _get_dotenv_encodings(env_path):
        try:
            load_dotenv(env_path, encoding=encoding)
            return
        except UnicodeDecodeError as exc:
            last_error = exc

    raise RuntimeError(
        f"Failed to read environment file at {env_path}. "
        "Save the file as UTF-8 or UTF-16 text."
    ) from last_error


# Load environment variables from .env file
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    _load_environment(env_path)


from app.routes.upload import router as upload_router
from app.routes.query import router as query_router


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title="VectorQuery: Production-Ready RAG Pipeline API",
    description="""
    A production-ready Retrieval-Augmented Generation (RAG) API for intelligent document Q&A.
    
    ## Features
    - Document ingestion (PDF/TXT)
    - Intelligent chunking with overlap
    - Semantic similarity search using FAISS
    - LLM-powered answer generation
    - Comprehensive metrics tracking
    - Rate limiting
    """,
    version="1.0.0"
)

ui_dir = Path(__file__).resolve().parent / "ui"
app.mount("/ui", StaticFiles(directory=ui_dir, html=True), name="ui")

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload_router)
app.include_router(query_router)


@app.get("/")
@limiter.limit("100/minute")
async def root(request: Request):
    """Root endpoint with API information."""
    return {
        "message": "VectorQuery: Production-Ready RAG Pipeline API",
        "version": "1.0.0",
        "endpoints": {
            "upload": "/upload",
            "query": "/query",
            "status": "/upload/status/{doc_id}",
            "docs": "/docs",
            "ui": "/ui"
        }
    }


@app.get("/health")
@limiter.limit("100/minute")
async def health_check(request: Request):
    """Health check endpoint."""
    return {"status": "healthy"}
