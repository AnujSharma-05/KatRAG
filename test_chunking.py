import sys
import json
import logging
from core_backend.src.chunking_engine import extract_blocks_from_pdf, chunk_structural_blocks

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

pdf_path = "E:\\Codes\\JPL\\KatRAG\\uploads\\1 Harry Potter and the Sorcerer's Stone (1).pdf"

logging.info(f"Extracting blocks from {pdf_path}...")
blocks = extract_blocks_from_pdf(pdf_path)
logging.info(f"Extracted {len(blocks)} structural blocks.")

logging.info("Applying parent-child chunking...")
structured_chunks = chunk_structural_blocks(blocks, bypass_llm=True)
logging.info(f"Generated {len(structured_chunks)} parent chunks.")

for i, chunk in enumerate(structured_chunks[:2]):
    print(f"\n--- PARENT CHUNK {i+1} ---")
    print(f"Content Preview: {chunk.get('text')[:100]}...")
    print(f"Child Chunks: {len(chunk.get('children', []))}")
