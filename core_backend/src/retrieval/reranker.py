from ..config import CROSS_ENCODER_MODEL
import os

# We will export, quantize and load via ONNX Runtime
from transformers import AutoTokenizer
try:
    from optimum.onnxruntime import ORTModelForSequenceClassification, ORTQuantizer
    from optimum.onnxruntime.configuration import AutoQuantizationConfig
    _ONNX_AVAILABLE = True
except ImportError:
    _ONNX_AVAILABLE = False
    print("WARNING: optimum[onnxruntime] not installed, falling back to standard CrossEncoder")
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_INSTANCE = CrossEncoder(CROSS_ENCODER_MODEL, max_length=256)

if _ONNX_AVAILABLE:
    model_id = CROSS_ENCODER_MODEL
    safe_name = model_id.replace('/', '_')
    onnx_dir = f"models/onnx/{safe_name}"
    quant_dir = f"{onnx_dir}_quantized"

    if not os.path.exists(quant_dir):
        print(f"[ONNX] Exporting {model_id} to ONNX format and quantizing to INT8...")
        os.makedirs(onnx_dir, exist_ok=True)
        # 1. Export
        model_fp32 = ORTModelForSequenceClassification.from_pretrained(model_id, export=True)
        model_fp32.save_pretrained(onnx_dir)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        tokenizer.save_pretrained(onnx_dir)
        
        # 2. Quantize
        quantizer = ORTQuantizer.from_pretrained(model_fp32)
        qconfig = AutoQuantizationConfig.avx2(is_static=False)
        quantizer.quantize(save_dir=quant_dir, quantization_config=qconfig)
        tokenizer.save_pretrained(quant_dir)
        print("[ONNX] Export and Quantization complete.")

    # Load the quantized model
    tokenizer = AutoTokenizer.from_pretrained(quant_dir)
    ort_model = ORTModelForSequenceClassification.from_pretrained(quant_dir)


def rerank_hits(question: str, hits: list[dict], top_k: int) -> list[dict]:
    if not hits:
        return []
    print(f"\n[RERANKING] Scoring {len(hits)} hits...")
    cross_input = [[question, hit["content"]] for hit in hits]
    
    if _ONNX_AVAILABLE:
        inputs = tokenizer(cross_input, padding=True, truncation=True, max_length=256, return_tensors="pt")
        outputs = ort_model(**inputs)
        scores = outputs.logits.squeeze(-1).tolist()
        if isinstance(scores, float):
            scores = [scores]
    else:
        scores = CROSS_ENCODER_INSTANCE.predict(cross_input)
    
    for idx, hit in enumerate(hits):
        hit["cross_score"] = float(scores[idx])
        
    hits.sort(key=lambda x: x["cross_score"], reverse=True)
    return hits[:top_k]
