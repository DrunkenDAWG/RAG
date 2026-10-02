# 🧪 Test & Evaluation Suite

This directory contains automated end-to-end smoke tests and quality assurance evaluation harnesses for **LocalHost RAG**.

---

## 📁 Directory Structure

```
tests/
├── fixtures/
│   └── sample_knowledge.txt      # Factual reference document for QA & RAGAS eval
├── results/
│   ├── ragas_evaluation_report.json   # Exported quantitative metric summary
│   └── ragas_evaluation_report.md     # Formatted markdown scorecards & tables
├── evaluate_ragas.py             # 100% Free RAGAS automated evaluation harness
├── smoke_test.sh                 # End-to-end curl + SSE + cache validation bash script
└── requirements-test.txt         # Testing & evaluation dependencies
```

---

## 1. 🚀 End-to-End Smoke Test (`smoke_test.sh`)

Automated bash script that executes the complete 5-step user journey against the live backend:

1. **Session Lifecycle:** `POST /api/v1/sessions` → captures `session_id`.
2. **Scoped Ingestion:** `POST /api/v1/documents/upload` with `-H "X-Session-Id"` → verifies chunking & indexing.
3. **SSE Streaming:** `POST /api/v1/chat/stream` → validates real-time token events and citation markers.
4. **Contextual Rewriting:** Submits anaphoric follow-up question (`"How often are its keys rotated?"`) → verifies LLM query rewrite.
5. **Redis Smart Cache:** Re-submits query → asserts `"type": "cached"` event and verifies response time **< 50ms**.

### Running the Smoke Test

```bash
# Ensure backend is running (http://localhost:8000)
bash tests/smoke_test.sh

# Or with custom backend endpoint:
API_BASE_URL=http://localhost:8000 bash tests/smoke_test.sh
```

---

## 2. 📊 RAGAS Evaluation Harness (`evaluate_ragas.py`)

Automated AI evaluation measuring 4 core RAG metrics without requiring OpenAI or paid API services:

- **Faithfulness:** Verifies generated answers do not contain hallucinations and are strictly grounded in retrieved context.
- **Answer Relevancy:** Verifies generated answers directly address user intent without digression.
- **Context Precision:** Measures signal-to-noise ratio in retrieved passages.
- **Context Recall:** Verifies whether all reference ground truth facts are present in retrieved chunks.

### Free LLM & Embedding Setup

- **LLM:** Groq `llama-3.3-70b-versatile` (free tier).
- **Embeddings:** Local HuggingFace `all-MiniLM-L6-v2` (runs 100% locally on CPU).

### Installation & Execution

```bash
# 1. Install evaluation dependencies
pip install -r tests/requirements-test.txt

# 2. Ensure GROQ_API_KEY is set in your .env or environment
export GROQ_API_KEY="gsk_..."

# 3. Run evaluation (auto-detects live server or direct mode)
python tests/evaluate_ragas.py

# Optional arguments:
python tests/evaluate_ragas.py --mode direct
python tests/evaluate_ragas.py --mode api --api-url http://localhost:8000
```

### Generated Reports

Results are automatically saved to:
- `tests/results/ragas_evaluation_report.json`
- `tests/results/ragas_evaluation_report.md`
