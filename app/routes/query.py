import time
import numpy as np
from fastapi import APIRouter, HTTPException
from typing import Dict

from app.models.schemas import QueryRequest, QueryResponse, Source
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.retrieval import RetrievalService
from app.services.llm import LLMService
from app.routes.upload import processing_status, vector_store, embedding_service


router = APIRouter(prefix="/query", tags=["query"])

# Use shared instances from upload module
retrieval_service = RetrievalService()
llm_service = LLMService()


@router.post("", response_model=QueryResponse)
async def query_document(request: QueryRequest):
    """
    Query a document with a question.
    
    Process:
    1. Check if document is processed
    2. Embed the query
    3. Retrieve relevant chunks using similarity search
    4. Generate answer using LLM
    5. Return answer with sources and metrics
    """
    # Validate question length
    if not request.question or len(request.question.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Question must be at least 3 characters long"
        )
    
    # Check if document exists and is processed
    if request.doc_id not in processing_status:
        raise HTTPException(
            status_code=404,
            detail="Document not found. Please upload a document first."
        )
    
    status = processing_status[request.doc_id]
    if status != "completed":
        if status.startswith("failed"):
            raise HTTPException(
                status_code=400,
                detail=f"Document processing failed: {status[7:]}"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Document is still being processed. Status: {status}. Please try again in a few seconds."
            )
    
    # Load index if not in memory
    if request.doc_id not in vector_store.indexes:
        try:
            vector_store.load_index(request.doc_id)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load document index: {str(e)}"
            )
    
    total_start_time = time.time()
    
    try:
        # Step 1: Embed query
        embedding_start = time.time()
        query_embedding = embedding_service.get_embedding(request.question)
        embedding_time = (time.time() - embedding_start) * 1000  # Convert to ms
        
        # Step 2: Retrieve relevant chunks
        retrieved_chunks, retrieval_time = retrieval_service.retrieve(
            vector_store=vector_store,
            doc_id=request.doc_id,
            query_embedding=query_embedding,
            top_k=request.top_k
        )
        
        if not retrieved_chunks:
            raise HTTPException(
                status_code=404,
                detail="No relevant chunks found for the query. The document may not contain information related to your question."
            )
        
        # Step 3: Format context
        context = retrieval_service.format_context(retrieved_chunks)
        
        # Step 4: Generate answer
        try:
            answer, generation_time = llm_service.generate_answer(
                question=request.question,
                context=context
            )
        except ValueError as e:
            raise HTTPException(
                status_code=503,
                detail=f"LLM service unavailable: {str(e)}. Please configure OPENAI_API_KEY environment variable."
            )
        except RuntimeError as e:
            raise HTTPException(
                status_code=502,
                detail=f"LLM request failed: {str(e)[:300]}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate answer: {str(e)[:100]}"
            )
        
        total_time = (time.time() - total_start_time) * 1000  # Convert to ms
        
        # Format sources
        sources = [
            Source(
                chunk_id=chunk['chunk_id'],
                text=chunk['text'][:200] + "..." if len(chunk['text']) > 200 else chunk['text'],
                score=chunk['score'],
                doc_id=chunk['doc_id']
            )
            for chunk in retrieved_chunks
        ]
        
        # Return response with metrics
        return QueryResponse(
            answer=answer,
            sources=sources,
            metrics={
                "total_latency_ms": round(total_time, 2),
                "embedding_time_ms": round(embedding_time, 2),
                "retrieval_time_ms": round(retrieval_time, 2),
                "llm_generation_time_ms": round(generation_time, 2),
                "chunks_retrieved": len(retrieved_chunks)
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during query processing: {str(e)[:100]}"
        )
