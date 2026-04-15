# VectorQuery - Quick Start Guide

## ⚡ 60-Second Setup

```bash
# 1. Install dependencies (3 minutes)
pip install -r requirements.txt

# 2. Set up OpenAI API key
echo OPENAI_API_KEY=sk_your_key_here > .env

# 3. Start the server (1 terminal)
python -m uvicorn app.main:app --reload

# 4. Test the system (another terminal)
python test_api.py

# 5. Access the API documentation
# Open browser: http://localhost:8000/docs
```

---

## 📤 Upload a Document

### Using cURL:
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@sample_documents/AI_Business_Guide.txt"

# Output:
# {
#   "message": "Document processing started",
#   "doc_id": "550e8400-e29b-41d4-a716-446655440000",
#   "status": "processing"
# }

DOC_ID="550e8400-e29b-41d4-a716-446655440000"  # Save this for next steps
```

### Using Python:
```python
import requests

response = requests.post(
    "http://localhost:8000/upload",
    files={"file": open("document.txt", "rb")}
)
doc_id = response.json()["doc_id"]
print(f"Document ID: {doc_id}")
```

---

## 🔄 Check Processing Status

```bash
curl "http://localhost:8000/upload/status/$DOC_ID"

# Output: {"doc_id": "...", "status": "completed"}

# Wait until "status" is "completed"
# This typically takes 5-10 seconds
```

---

## ❓ Ask Questions

### Using cURL:
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is artificial intelligence?",
    "doc_id": "550e8400-e29b-41d4-a716-446655440000",
    "top_k": 3
  }'
```

### Using Python:
```python
import requests

response = requests.post(
    "http://localhost:8000/query",
    json={
        "question": "What is artificial intelligence?",
        "doc_id": doc_id,
        "top_k": 3
    }
)

data = response.json()
print("Answer:", data["answer"])
print("Latency:", data["metrics"]["total_latency_ms"], "ms")
print("Sources:", len(data["sources"]), "chunks")
```

---

## 📊 Example Response

```json
{
  "answer": "According to the document, artificial intelligence has become one of the most transformative technologies of the 21st century...",
  "sources": [
    {
      "chunk_id": 0,
      "text": "Artificial Intelligence (AI) has become...",
      "score": 0.8234,
      "doc_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  ],
  "metrics": {
    "total_latency_ms": 2345.67,
    "embedding_time_ms": 12.45,
    "retrieval_time_ms": 5.23,
    "llm_generation_time_ms": 2327.99,
    "chunks_retrieved": 3
  }
}
```

---

## 🧪 Complete Workflow (Bash Script)

```bash
#!/bin/bash

# Upload document
echo "📤 Uploading document..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/upload" \
  -F "file=@sample_documents/AI_Business_Guide.txt")
DOC_ID=$(echo $RESPONSE | jq -r '.doc_id')
echo "Document ID: $DOC_ID"

# Wait for processing
echo "⏳ Waiting for processing..."
while true; do
  STATUS=$(curl -s "http://localhost:8000/upload/status/$DOC_ID" | jq -r '.status')
  if [ "$STATUS" = "completed" ]; then
    echo "✅ Processing complete!"
    break
  fi
  echo "Status: $STATUS... waiting..."
  sleep 2
done

# Ask questions
echo "❓ Asking questions..."
QUESTIONS=(
  "What is artificial intelligence?"
  "What are the benefits of AI?"
  "What are the challenges?"
)

for QUESTION in "${QUESTIONS[@]}"; do
  echo ""
  echo "Q: $QUESTION"
  curl -s -X POST "http://localhost:8000/query" \
    -H "Content-Type: application/json" \
    -d "{
      \"question\": \"$QUESTION\",
      \"doc_id\": \"$DOC_ID\",
      \"top_k\": 3
    }" | jq '.answer'
done
```

---

## 🐍 Python Complete Workflow

```python
import requests
import time
import json

API_URL = "http://localhost:8000"

def upload_document(file_path):
    """Upload a document and get doc_id"""
    with open(file_path, 'rb') as f:
        response = requests.post(
            f"{API_URL}/upload",
            files={"file": f}
        )
    return response.json()["doc_id"]

def wait_for_processing(doc_id, max_wait=60):
    """Wait for document processing to complete"""
    start = time.time()
    while time.time() - start < max_wait:
        response = requests.get(f"{API_URL}/upload/status/{doc_id}")
        status = response.json()["status"]
        if status == "completed":
            return True
        print(f"Status: {status}...")
        time.sleep(2)
    return False

def query_document(doc_id, question, top_k=3):
    """Ask a question about the document"""
    response = requests.post(
        f"{API_URL}/query",
        json={
            "question": question,
            "doc_id": doc_id,
            "top_k": top_k
        }
    )
    return response.json()

# Main workflow
doc_id = upload_document("sample_documents/AI_Business_Guide.txt")
print(f"Uploaded document: {doc_id}")

if wait_for_processing(doc_id):
    print("✅ Processed successfully!")
    
    # Ask questions
    questions = [
        "What is artificial intelligence?",
        "What are the benefits of AI?",
        "What challenges exist?"
    ]
    
    for question in questions:
        result = query_document(doc_id, question)
        print(f"\nQ: {question}")
        print(f"A: {result['answer'][:200]}...")
        print(f"Latency: {result['metrics']['total_latency_ms']}ms")
else:
    print("❌ Processing timeout")
```

---

## 🛠️ Common Commands

### Health Check
```bash
curl http://localhost:8000/health
# {"status": "healthy"}
```

### Get API Info
```bash
curl http://localhost:8000/
# Full endpoint information
```

### View Available Documents
```bash
# Currently stored in memory via processing_status dict
curl http://localhost:8000/upload/status/YOUR_DOC_ID
```

### Interactive API Docs
```
http://localhost:8000/docs       # Swagger UI
http://localhost:8000/redoc      # ReDoc
```

---

## 📝 Settings & Configuration

### Adjust via .env
```env
# OpenAI Configuration
OPENAI_API_KEY=sk_your_api_key_here

# Chunking Parameters
CHUNK_SIZE=400        # Smaller = more precise, more chunks
CHUNK_OVERLAP=80      # Larger = more context, slower processing

# Retrieval Parameters
TOP_K=5              # How many chunks to retrieve (1-10)

# Model Selection
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
LLM_MODEL=gpt-3.5-turbo
```

---

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| "Port 8000 already in use" | Change port: `--port 8001` |
| "ModuleNotFoundError" | Run `pip install -r requirements.txt` |
| "OpenAI API key not configured" | Set `.env` or export environment variable |
| "Embedding model download failed" | Check internet connection, try again |
| "Document processing slow" | Large files are normal, can take 1-2 min |

---

## 🚀 Tips for Success

### For Testing:
1. Start with sample_documents provided
2. Use short questions (5-15 words)
3. Check metrics to understand latency
4. Try different top_k values

### For Production:
1. Use environment variables for secrets
2. Monitor metrics in logs
3. Set up error alerting
4. Cache frequently asked questions
5. Consider rate limiting per user

### For Development:
1. Use `--reload` for auto-reload during development
2. Keep test_api.py passing
3. Monitor server logs for errors
4. Profile slow operations with metrics

---

## 📚 Next Steps

1. **Get OpenAI Key**: https://platform.openai.com/api-keys
2. **Set in .env**: `OPENAI_API_KEY=sk_...`
3. **Run Questions**: Use provided examples
4. **Check Metrics**: Understand performance
5. **Customize**: Adjust chunk size, top_k, etc.
6. **Deploy**: Follow DEPLOYMENT_GUIDE.md

---

## 📞 Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/` | GET | API info |
| `/upload` | POST | Upload document |
| `/upload/status/{doc_id}` | GET | Check processing |
| `/query` | POST | Ask question |
| `/docs` | GET | API documentation |

---

## ✅ Verify Installation

```bash
# Test each component
curl http://localhost:8000/health
# Should return: {"status": "healthy"}

# If you get connection error:
# Server not running? Start with:
# python -m uvicorn app.main:app --reload
```

---

**Ready to go!** 🚀
Start with: `python test_api.py`
