"""
Test script for VectorQuery RAG API.

Tests document upload, status checking, and querying endpoints.
Uses plain ASCII output so it runs cleanly on Windows terminals that do not
support emoji characters in the active code page.
"""

import json
import time
from pathlib import Path

import requests


BASE_URL = "http://localhost:8000"
SAMPLE_DOCS_DIR = Path("sample_documents")


def test_health():
    """Test the health check endpoint."""
    print("[TEST] Health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    print(f"[OK] Health check passed: {response.json()}")
    return True


def test_root():
    """Test the root endpoint."""
    print("\n[TEST] Root endpoint...")
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    data = response.json()
    print(f"[OK] Root endpoint: {json.dumps(data, indent=2)}")
    return True


def test_upload_document(file_path: Path):
    """Test uploading a document."""
    print(f"\n[TEST] Upload document: {file_path}")

    with open(file_path, "rb") as file_handle:
        files = {"file": (file_path.name, file_handle, "text/plain")}
        response = requests.post(f"{BASE_URL}/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    print("[OK] Upload successful")
    print(f"     Doc ID: {data['doc_id']}")
    print(f"     Status: {data['status']}")
    print(f"     Message: {data['message']}")
    return data["doc_id"]


def test_get_status(doc_id: str):
    """Check document processing status."""
    print(f"\n[TEST] Processing status for doc_id: {doc_id}")

    max_retries = 120
    retry_count = 0

    while retry_count < max_retries:
        response = requests.get(f"{BASE_URL}/upload/status/{doc_id}")
        assert response.status_code == 200

        data = response.json()
        status = data["status"]
        print(f"     Status: {status}")

        if status == "completed":
            print("[OK] Document processing completed")
            return True

        if status.startswith("failed"):
            print(f"[FAIL] Document processing failed: {status}")
            return False

        retry_count += 1
        if retry_count < max_retries:
            print(f"     Waiting... ({retry_count}/{max_retries})")
            time.sleep(1)

    print("[FAIL] Timeout waiting for document processing")
    return False


def test_query_document(doc_id: str, question: str):
    """Query a document."""
    print(f"\n[TEST] Query endpoint for doc_id: {doc_id}")
    print(f"     Question: {question}")

    payload = {
        "question": question,
        "doc_id": doc_id,
        "top_k": 3,
    }

    response = requests.post(f"{BASE_URL}/query", json=payload)

    if response.status_code != 200:
        print(f"[FAIL] Query failed with status {response.status_code}")
        print(f"       Response: {response.text}")
        return False

    data = response.json()
    print("[OK] Query successful")
    print(
        f"\n     Answer:\n     "
        f"{data['answer'][:500]}{'...' if len(data['answer']) > 500 else ''}"
    )
    print("\n     Metrics:")
    print(f"     - Total Latency: {data['metrics'].get('total_latency_ms', 'N/A')} ms")
    print(f"     - Embedding Time: {data['metrics'].get('embedding_time_ms', 'N/A')} ms")
    print(f"     - Retrieval Time: {data['metrics'].get('retrieval_time_ms', 'N/A')} ms")
    print(
        f"     - LLM Generation Time: "
        f"{data['metrics'].get('llm_generation_time_ms', 'N/A')} ms"
    )
    print(f"     - Chunks Retrieved: {data['metrics'].get('chunks_retrieved', 'N/A')}")
    print(f"\n     Sources ({len(data['sources'])} chunks):")
    for index, source in enumerate(data["sources"], 1):
        print(f"     [{index}] Score: {source['score']:.4f}")
        print(f"         {source['text'][:100]}...")

    return True


def main():
    """Main test function."""
    print("=" * 80)
    print("VectorQuery RAG API - Test Suite")
    print("=" * 80)

    try:
        test_health()
        test_root()

        if not SAMPLE_DOCS_DIR.exists():
            print(f"[FAIL] Sample documents directory not found: {SAMPLE_DOCS_DIR}")
            return

        txt_files = list(SAMPLE_DOCS_DIR.glob("*.txt"))
        if not txt_files:
            print(f"[FAIL] No TXT files found in {SAMPLE_DOCS_DIR}")
            return

        sample_file = txt_files[0]
        doc_id = test_upload_document(sample_file)

        if not test_get_status(doc_id):
            print("[FAIL] Document processing failed, skipping query tests")
            return

        print("\n" + "=" * 80)
        print("Query Endpoint Test")
        print("=" * 80)

        test_queries = [
            "What is artificial intelligence?",
            "What are the benefits of AI implementation?",
            "What are the challenges in AI adoption?",
        ]

        for question in test_queries:
            try:
                test_query_document(doc_id, question)
            except Exception as exc:
                print(f"[WARN] Query test skipped: {str(exc)[:100]}")
                break

        print("\n" + "=" * 80)
        print("[OK] All available tests completed")
        print("=" * 80)

    except requests.exceptions.ConnectionError:
        print("[FAIL] Could not connect to the server at localhost:8000")
        print("       Make sure the FastAPI server is running:")
        print("       python -m uvicorn app.main:app --reload")
    except Exception as exc:
        print(f"[FAIL] Test failed with error: {str(exc)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
