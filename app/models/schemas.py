from pydantic import BaseModel, Field
from typing import List, Optional


class UploadResponse(BaseModel):
    """Response model for document upload."""
    message: str
    doc_id: str
    status: str = Field(default="processing")


class QueryRequest(BaseModel):
    """Request model for querying a document."""
    question: str = Field(..., description="The question to ask about the document")
    doc_id: str = Field(..., description="The document ID to query")
    top_k: Optional[int] = Field(default=5, ge=1, le=10, description="Number of top chunks to retrieve")


class Source(BaseModel):
    """Source information for retrieved chunks."""
    chunk_id: int
    text: str
    score: float
    doc_id: str


class QueryResponse(BaseModel):
    """Response model for query results."""
    answer: str
    sources: List[Source]
    metrics: dict


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
