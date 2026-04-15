import asyncio
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict

from app.models.schemas import UploadResponse
from app.utils.parser import DocumentParser
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStore


router = APIRouter(prefix="/upload", tags=["upload"])

# Global instances (in production, use dependency injection)
vector_store = VectorStore()
embedding_service = EmbeddingService()
chunking_service = ChunkingService()

# Track processing status
processing_status: Dict[str, str] = {}


@router.post("", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...)
):
    """
    Upload a document for processing.
    
    Supported formats: PDF, TXT
    Max file size: 100MB
    
    The document is processed in the background:
    1. Parse the document
    2. Chunk the text
    3. Generate embeddings
    4. Store in vector database
    """
    # Validate filename
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="File must have a name"
        )
    
    # Validate file extension
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ['.pdf', '.txt']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{file_extension}'. Only PDF (.pdf) and TXT (.txt) are supported."
        )
    
    # Generate unique document ID
    doc_id = str(uuid.uuid4())
    
    # Save uploaded file
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    file_path = uploads_dir / f"{doc_id}{file_extension}"
    
    try:
        content = await file.read()
        
        # Validate file size (max 100MB)
        max_size = 100 * 1024 * 1024
        if len(content) == 0:
            raise HTTPException(
                status_code=400,
                detail="File is empty. Please provide a non-empty document."
            )
        
        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is 100MB. Your file is {len(content) / (1024*1024):.2f}MB."
            )
        
        with open(file_path, "wb") as buffer:
            buffer.write(content)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        )
    
    # Set status to processing
    processing_status[doc_id] = "processing"
    
    # Run processing in a worker thread so status checks stay responsive.
    asyncio.create_task(
        asyncio.to_thread(
            process_document,
            doc_id=doc_id,
            file_path=str(file_path)
        )
    )
    
    return UploadResponse(
        message="Document processing started",
        doc_id=doc_id,
        status="processing"
    )



def process_document(doc_id: str, file_path: str):
    """
    Background task to process a document.
    
    Args:
        doc_id: Document identifier
        file_path: Path to the uploaded file
    """
    try:
        # Step 1: Parse document
        text = DocumentParser.parse_document(file_path)
        
        if not text or len(text.strip()) < 10:
            processing_status[doc_id] = "failed"
            return
        
        # Step 2: Chunk text
        chunks = chunking_service.chunk_text(text)
        
        if not chunks:
            processing_status[doc_id] = "failed"
            return
        
        # Step 3: Generate embeddings
        embeddings = embedding_service.get_embeddings(chunks)
        
        # Step 4: Get embedding dimension
        embedding_dim = embedding_service.get_embedding_dimension()
        
        # Step 5: Create vector index
        vector_store.create_index(doc_id, embedding_dim)
        
        # Step 6: Add embeddings to vector store
        vector_store.add_embeddings(doc_id, embeddings, chunks)
        
        # Step 7: Save index to disk
        vector_store.save_index(doc_id)
        
        # Update status to completed
        processing_status[doc_id] = "completed"
        
    except Exception as e:
        processing_status[doc_id] = f"failed: {str(e)}"


@router.get("/status/{doc_id}")
async def get_processing_status(doc_id: str):
    """
    Get the processing status of a document.
    
    Args:
        doc_id: Document identifier
        
    Returns:
        Processing status
    """
    if doc_id not in processing_status:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"doc_id": doc_id, "status": processing_status[doc_id]}
