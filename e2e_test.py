import requests
import json
import jwt
import asyncio
import websockets
import time
import psycopg2
from minio import Minio

# 1. Generate a valid JWT mocking our auth structure
JWT_SECRET = "super-secret-katrag-key-change-in-prod"
def generate_jwt(user_id="admin-123"):
    payload = {
        "sub": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def check_postgres(doc_id):
    print(f"[*] Checking PostgreSQL for document ID: {doc_id}...")
    conn = psycopg2.connect("postgres://task0_user:task0_password@localhost:5432/JPL_task0_RapidFoundation?sslmode=disable")
    cur = conn.cursor()
    cur.execute("SELECT status FROM documents WHERE id = %s", (doc_id,))
    row = cur.fetchone()
    if row:
        print(f"[SUCCESS] Postgres Record Found. Status: {row[0]}")
    else:
        print(f"[FAILED] Document {doc_id} not found in PostgreSQL.")
    cur.close()
    conn.close()

def check_minio(doc_id):
    print(f"[*] Checking MinIO for document ID: {doc_id}.pdf...")
    client = Minio("localhost:9002", access_key="minioadmin", secret_key="minioadmin", secure=False)
    try:
        stat = client.stat_object("katrag-docs", f"{doc_id}.pdf")
        print(f"[SUCCESS] MinIO Object Found! Size: {stat.size} bytes")
    except Exception as e:
        print(f"[FAILED] MinIO object missing: {e}")

async def test_e2e_flow():
    token = generate_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    
    group_id = 1
    upload_url = f"http://localhost:8080/groups/{group_id}/documents"
    ws_url = f"ws://localhost:8080/groups/{group_id}/ws"
    
    print(f"[*] Generated JWT Token for admin-123")
    print(f"[*] Connecting to WebSocket: {ws_url}")
    
    try:
        async with websockets.connect(ws_url, extra_headers=headers) as websocket:
            print(f"[+] WebSocket connected!")
            
            # Create a dummy PDF and upload it
            pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 21 >>\nstream\nBT /F1 24 Tf 100 700 Td (Hello World) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000214 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n284\n%%EOF\n"
            files = {'file': ('test.pdf', pdf_content, 'application/pdf')}
            
            print(f"[*] Sending POST request to {upload_url}...")
            response = await asyncio.to_thread(requests.post, upload_url, headers=headers, files=files)
            
            print(f"[*] Upload Response Status: {response.status_code}")
            
            assert response.status_code == 202, f"Expected 202, got {response.status_code}. Body: {response.text}"
            doc_id = response.json().get("document_id")
            
            # Verify Intermediate State (Postgres + MinIO)
            check_postgres(doc_id)
            check_minio(doc_id)
            
            # 4. Wait for WebSocket event
            print(f"[*] Listening for Kafka broadcast over WebSocket...")
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    print(f"[+] RECEIVED WS MESSAGE: {message}")
                    data = json.loads(message)
                    
                    # We are listening for messages matching our document_id
                    if data.get("document_id") == doc_id:
                        if data.get("status") == "indexed":
                            print("[SUCCESS] Event-driven ingestion completed successfully!")
                            break
                        elif data.get("status") == "failed":
                            print("[FAILED] Document processing failed.")
                            break
                except asyncio.TimeoutError:
                    print("[-] Timeout waiting for WebSocket message.")
                    break
    except Exception as e:
        print(f"[-] E2E flow encountered an error: {e}")

if __name__ == "__main__":
    asyncio.run(test_e2e_flow())
