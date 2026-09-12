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
    cumulative_char_pos = 0  # absolute char offset across the full document
    
    for page_num, page in enumerate(doc):
        # 1. Extract tables first
        tables = page.find_tables()
        table_bboxes = []
        if tables:
            for table in tables.tables:
                df = table.to_pandas()
                markdown_table = df.to_markdown(index=False) if not df.empty else ""
                if markdown_table:
                    _table_text = f"Table Data:\n{markdown_table}"
                    _t_start = cumulative_char_pos
                    _t_end = _t_start + len(_table_text)
                    blocks.append({
                        "text": _table_text,
                        "type": "table",
                        "page_from": page_num + 1,
                        "section_path": current_section,
                        "char_start": _t_start,
                        "char_end": _t_end,
                    })
                    cumulative_char_pos = _t_end + 1
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
                    current_section = text

                _b_start = cumulative_char_pos
                _b_end = _b_start + len(text)
                cumulative_char_pos = _b_end + 2

                blocks.append({
                    "text": text,
                    "type": "heading" if is_heading else "text",
                    "page_from": page_num + 1,
                    "section_path": current_section,
                    "char_start": _b_start,
                    "char_end": _b_end,
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
    current_parent_char_start = 0
    current_parent_char_end = 0
    
    def flush_parent():
        nonlocal current_parent_text, current_parent_page, current_parent_section
        nonlocal current_parent_char_start, current_parent_char_end
        if not current_parent_text.strip():
            return
            
        # Split parent into overlapping children based on token approximation
        words = current_parent_text.split()
        child_texts = []
        
        # Word heuristic: 1 word ~ 1.3 tokens
        window_size = int(child_budget / 1.3)
        overlap = int(overlap_budget / 1.3)
        
        parent_text_stripped = current_parent_text.strip()
        if len(words) <= window_size:
            child_texts.append(parent_text_stripped)
        else:
            for i in range(0, len(words), window_size - overlap):
                child_texts.append(" ".join(words[i:i + window_size]))

        child_spans = []
        search_pos = 0
        for ct in child_texts:
            idx = parent_text_stripped.find(ct, search_pos)
            if idx == -1:
                idx = search_pos
            child_spans.append({"char_start": current_parent_char_start + idx, "char_end": current_parent_char_start + idx + len(ct)})
            search_pos = idx + max(1, len(ct) - 20)

        chunks.append({
            "is_parent": True,
            "text": parent_text_stripped,
            "page_from": current_parent_page,
            "section_path": current_parent_section,
            "char_start": current_parent_char_start,
            "char_end": current_parent_char_end,
            "children": child_texts,
            "child_spans": child_spans,
        })

        current_parent_text = ""
        current_parent_page = None
        current_parent_section = ""
        current_parent_char_start = 0
        current_parent_char_end = 0

    for block in blocks:
        b_char_start = block.get("char_start", 0)
        b_char_end = block.get("char_end", 0)

        # Isolate tables
        if block["type"] == "table":
            flush_parent()
            _t = block["text"]
            chunks.append({
                "is_parent": True,
                "text": _t,
                "page_from": block["page_from"],
                "section_path": block["section_path"],
                "char_start": b_char_start,
                "char_end": b_char_end,
                "children": [_t],
                "child_spans": [{"char_start": b_char_start, "char_end": b_char_end}],
            })
            continue

        block_tokens = _count_tokens(block["text"])

        if _count_tokens(current_parent_text) + block_tokens > parent_budget:
            flush_parent()

        if not current_parent_text:
            current_parent_page = block["page_from"]
            current_parent_section = block["section_path"]
            current_parent_char_start = b_char_start

        current_parent_text += block["text"] + "\n\n"
        current_parent_char_end = b_char_end
        
    flush_parent()
    return chunks
