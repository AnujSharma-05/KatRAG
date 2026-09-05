import sys
import os
import asyncio
from datetime import datetime

# Ensure src is importable
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database import sessionLocal, Base, engine
from src.models import Document, DocumentVersion
from src.milvus_store import milvus_store
from src.services import answer_question

def setup_test_data():
    db = sessionLocal()
    
    # Clear existing for clean test
    db.query(DocumentVersion).delete()
    db.query(Document).delete()
    db.commit()
    milvus_store.delete_all_chunks()
    
    org_id = "test_org"
    group_id = 999
    
    doc = Document(filename="policy.pdf", status="ready", organization_id=org_id, group_id=group_id)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # v1 (Historical)
    v1 = DocumentVersion(
        id="ver_historical",
        document_id=doc.id,
        version_num=1,
        is_current=False,
        valid_from=datetime(2024, 1, 1),
        valid_to=datetime(2024, 6, 1),
        status="indexed"
    )
    
    # v2 (Current)
    v2 = DocumentVersion(
        id="ver_current",
        document_id=doc.id,
        version_num=2,
        is_current=True,
        valid_from=datetime(2024, 6, 1),
        valid_to=None,
        status="indexed"
    )
    
    db.add(v1)
    db.add(v2)
    db.commit()
    
    # Encode and insert vectors
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    
    v1_text = "Health coverage is $5,000"
    v2_text = "Health coverage is $10,000"
    
    v1_emb = model.encode([v1_text])[0].tolist()
    v2_emb = model.encode([v2_text])[0].tolist()
    
    # Simulate the worker pipeline sequence
    milvus_store.upsert_chunks(doc.id, [v1_text], [v1_emb], org_id)
    milvus_store.deprecate_document_vectors(doc.id, org_id)
    milvus_store.upsert_chunks(doc.id, [v2_text], [v2_emb], org_id)
    
    db.close()
    return doc.id, org_id, group_id

async def run_tests():
    print("Setting up temporal test data...")
    doc_id, org_id, group_id = setup_test_data()
    
    print("\n--- Test 1: Current Query (as_of = None) ---")
    res1 = await answer_question(
        question="What is the health coverage limit?",
        document_id=doc_id,
        group_id=group_id,
        organization_id=org_id,
        bypass_llm=True
    )
    citations1 = res1.get("citations", [])
    if citations1 and "$10,000" in citations1[0]["content_preview"]:
        print("=> PASS: Retrieved current v2 ($10,000)")
    else:
        print(f"=> FAIL: {citations1}")
        assert False, "Failed Test 1"
        
    print("\n--- Test 2: Historical Query (as_of = 2024-03-15) ---")
    res2 = await answer_question(
        question="What is the health coverage limit?",
        document_id=doc_id,
        group_id=group_id,
        organization_id=org_id,
        as_of="2024-03-15T00:00:00",
        bypass_llm=True
    )
    citations2 = res2.get("citations", [])
    if citations2 and "$5,000" in citations2[0]["content_preview"]:
        print("=> PASS: Retrieved historical v1 ($5,000)")
    else:
        print(f"=> FAIL: {citations2}")
        assert False, "Failed Test 2"
        
    print("\n--- Test 3: Out of Bounds Query (as_of = 2023-01-01) ---")
    res3 = await answer_question(
        question="What is the health coverage limit?",
        document_id=doc_id,
        group_id=group_id,
        organization_id=org_id,
        as_of="2023-01-01T00:00:00",
        bypass_llm=True
    )
    citations3 = res3.get("citations", [])
    if not citations3:
        print("=> PASS: No documents retrieved before inception")
    else:
        print(f"=> FAIL: {citations3}")
        assert False, "Failed Test 3"

if __name__ == "__main__":
    asyncio.run(run_tests())
