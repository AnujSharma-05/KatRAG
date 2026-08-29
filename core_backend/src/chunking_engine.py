import fitz
import pandas as pd
from transformers import AutoTokenizer

# Using the tokenizer to accurately count tokens for the embedding model
try:
    TOKENIZER = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
except:
    TOKENIZER = None
#this function counts tokens in a text for chunking and the measure is done by the tokenizer of the embedding model
#it is not accurate but it is a good approximation of the number of tokens

def _count_tokens(text: str) -> int:
    if TOKENIZER:
        return len(TOKENIZER.encode(text, add_special_tokens=False))
    # Fallback heuristic: 1 token ~= 4 characters
    return len(text) // 4

def extract_blocks_from_pdf(file_path: str) -> list[dict]:
    """
    Extracts structural blocks (text, tables, headings) from a PDF.
    Tracks the section hierarchy (section_path) dynamically.
    """
    doc = fitz.open(file_path)
    blocks = []
    current_section = "Document Start"
    
    for page_num, page in enumerate(doc):
        # 1. Extract tables first
        tables = page.find_tables()
        table_bboxes = []
        if tables:
            for table in tables.tables:
                df = table.to_pandas()
                markdown_table = df.to_markdown(index=False) if not df.empty else ""
                if markdown_table:
                    blocks.append({
                        "text": f"Table Data:\n{markdown_table}",
                        "type": "table",
                        "page_from": page_num + 1,
                        "section_path": current_section
                    })
                table_bboxes.append(table.bbox)
                
        # 2. Extract text blocks
        text_blocks = page.get_text("dict")["blocks"]
        for block in text_blocks:
            if block.get("type") == 0:  # text block type
                bbox = block["bbox"]
                
                # Skip text that is part of an already extracted table
                is_in_table = any(fitz.Rect(bbox).intersects(fitz.Rect(tb)) for tb in table_bboxes)
                if is_in_table:
                    continue
                    
                text = ""
                is_heading = False
                
                for line in block["lines"]:
                    for span in line["spans"]:
                        text += span["text"]
                        # Heading heuristic: large font or bold
                        if span["size"] > 12 or "bold" in span["font"].lower():
                            is_heading = True

                text = text.strip()
                if not text:
                    continue
                
                # Update current section path if a heading is found
                if is_heading and len(text) < 100:
                    # Very simple tracking: just use the heading as the section
                    current_section = text
                
                blocks.append({
                    "text": text,
                    "type": "heading" if is_heading else "text",
                    "page_from": page_num + 1,
                    "section_path": current_section
                })
                
    return blocks

def chunk_structural_blocks(blocks: list[dict], bypass_llm: bool = True) -> list[dict]:
    """
    Implements Parent-Child chunking.
    Groups blocks into 1024-token Parents, and splits them into 256-token Children.
    Tables are isolated.
    """
    """
    ┌────────────────────────────────────────────────────────────────┐
│                    PARENT CHUNK (~1024 tokens)                 │
│  Accumulated text blocks until the token budget is reached.     │
│                                                                │
│  ┌─────────────────┐   ┌─────────────────┐   ┌──────────────┐  │
│  │ CHILD 1 (256t)  │───│ CHILD 2 (256t)  │───│ CHILD 3...   │  │
│  └─────────────────┘   └─────────────────┘   └──────────────┘  │
│             ◄── Overlap (50t) ──►                              │
└────────────────────────────────────────────────────────────────┘
    """
    chunks = []
    parent_budget = 1024
    child_budget = 256
    overlap_budget = 50
    
    current_parent_text = ""
    current_parent_page = None
    current_parent_section = ""
    
    def flush_parent():
        nonlocal current_parent_text, current_parent_page, current_parent_section
        if not current_parent_text.strip():
            return
            
        # Split parent into overlapping children based on token approximation
        words = current_parent_text.split()
        child_texts = []
        
        # Word heuristic: 1 word ~ 1.3 tokens
        window_size = int(child_budget / 1.3)
        overlap = int(overlap_budget / 1.3)
        
        if len(words) <= window_size:
            child_texts.append(current_parent_text)
        else:
            for i in range(0, len(words), window_size - overlap):
                child_texts.append(" ".join(words[i:i + window_size]))
                
        chunks.append({
            "is_parent": True,
            "text": current_parent_text.strip(),
            "page_from": current_parent_page,
            "section_path": current_parent_section,
            "children": child_texts
        })
        
        current_parent_text = ""
        current_parent_page = None
        current_parent_section = ""

    for block in blocks:
        # Isolate tables
        if block["type"] == "table":
            flush_parent()
            
            # If bypass_llm is False in the future, we would call the LLM here to summarize the table
            # For now, the table is its own parent and child
            chunks.append({
                "is_parent": True,
                "text": block["text"],
                "page_from": block["page_from"],
                "section_path": block["section_path"],
                "children": [block["text"]]
            })
            continue
            
        block_tokens = _count_tokens(block["text"])
        
        if _count_tokens(current_parent_text) + block_tokens > parent_budget:
            flush_parent()
            
        if not current_parent_text:
            current_parent_page = block["page_from"]
            current_parent_section = block["section_path"]
            
        current_parent_text += block["text"] + "\n\n"
        
    flush_parent()
    return chunks
