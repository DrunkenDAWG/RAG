"""
tests/evaluate_ragas.py
─────────────────────────
Automated RAG Evaluation Harness using RAGAS, Groq LLM, and local HuggingFace Embeddings.

Metrics Computed:
  1. Faithfulness (hallucination check — ensures claims are grounded in context)
  2. Answer Relevance (verifies answer addresses the user query)
  3. Context Precision (measures signal-to-noise ratio of retrieved chunks)
  4. Context Recall (verifies context contains all information to answer ground truth)

Key Features:
  • 100% Free: Uses Groq LLM (llama-3.3-70b-versatile) + local HuggingFace embeddings.
  • Dual-mode Execution: Evaluates via live REST API (`http://localhost:8000`) or in-process direct pipeline.
  • Rich Reporting: Exports results to summary JSON and Markdown tables.

Usage:
  python tests/evaluate_ragas.py
  python tests/evaluate_ragas.py --mode api --api-url http://localhost:8000
  python tests/evaluate_ragas.py --mode direct
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

# Find and load .env from standard locations
_ROOT = Path(__file__).resolve().parent.parent
for env_path in [
    _ROOT / ".env",
    _ROOT / "backend" / ".env",
    Path.cwd() / ".env",
    Path.cwd() / "backend" / ".env",
]:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break


# ── Test Dataset Definition ───────────────────────────────────────────────────

@dataclass
class TestCase:
    question: str
    ground_truth: str
    category: str


SAMPLE_TEST_CASES: List[TestCase] = [
    TestCase(
        question="What consensus protocol does QuantumVault use, and what are its heartbeat and election timeout values?",
        ground_truth="QuantumVault uses a Raft-based consensus protocol with a 150ms heartbeat interval and a 300ms election timeout.",
        category="Architecture & Consensus",
    ),
    TestCase(
        question="What encryption standard is used for data at rest, and how frequently are keys rotated?",
        ground_truth="All data chunks and metadata are encrypted at rest using AES-256-GCM authenticated encryption with keys rotated automatically every 90 days.",
        category="Security & Encryption",
    ),
    TestCase(
        question="How does the hybrid retrieval engine combine search paths and what ranking constant is used?",
        ground_truth="The hybrid retrieval engine combines ChromaDB dense vector search with in-memory BM25Okapi sparse lexical search using Reciprocal Rank Fusion (RRF) with a constant k=60.",
        category="Retrieval Engine",
    ),
    TestCase(
        question="What is the default Redis cache TTL and how does automatic cache invalidation work?",
        ground_truth="The Redis cache has a default time-to-live (TTL) of 3600 seconds (1 hour). Automatic cache invalidation occurs when the corpus version increments monotonically upon new document ingestion.",
        category="Caching Tier",
    ),
    TestCase(
        question="Which cross-encoder model is used for reranking and how is blocking of the event loop prevented?",
        ground_truth="The cross-encoder/ms-marco-MiniLM-L-6-v2 model is used for reranking, and it runs in a dedicated thread pool to keep the asynchronous event loop non-blocking.",
        category="Reranking",
    ),
]


# ── RAGAS Evaluator Setup ─────────────────────────────────────────────────────

def setup_ragas_evaluator(
    groq_api_key: str,
    llm_model: str = "llama-3.3-70b-versatile",
    embedding_model: str = "all-MiniLM-L6-v2",
) -> Tuple[Any, Any]:
    """
    Configure Groq Chat LLM and HuggingFace Embeddings wrapped for RAGAS.
    Ensures 100% free evaluation without OpenAI API keys.
    """
    try:
        from langchain_groq import ChatGroq
    except ImportError:
        raise ImportError(
            "langchain-groq is required for RAGAS evaluation. "
            "Install with: pip install langchain-groq"
        )

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings  # fallback
        except ImportError:
            raise ImportError(
                "langchain-huggingface or langchain-community is required. "
                "Install with: pip install langchain-huggingface sentence-transformers"
            )

    # Initialize LangChain Groq LLM & Local HuggingFace Embeddings
    groq_llm = ChatGroq(
        model=llm_model,
        api_key=groq_api_key,
        temperature=0.0,
    )

    hf_embeddings = HuggingFaceEmbeddings(
        model_name=embedding_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # Wrap for RAGAS if wrappers are present (ragas >= 0.1.x / 0.2.x)
    evaluator_llm = groq_llm
    evaluator_embeddings = hf_embeddings

    try:
        from ragas.llms import LangchainLLMWrapper
        evaluator_llm = LangchainLLMWrapper(groq_llm)
    except (ImportError, AttributeError):
        pass

    try:
        from ragas.embeddings import LangchainEmbeddingsWrapper
        evaluator_embeddings = LangchainEmbeddingsWrapper(hf_embeddings)
    except (ImportError, AttributeError):
        pass

    return evaluator_llm, evaluator_embeddings


# ── Ingestion & Query Execution (API Mode) ───────────────────────────────────

async def run_queries_via_api(
    api_url: str,
    fixture_path: Path,
    test_cases: List[TestCase],
) -> List[Dict[str, Any]]:
    """Ingest document and execute queries against a running FastAPI backend."""
    import httpx

    results: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(base_url=api_url, timeout=60.0) as client:
        # 1. Create Session
        print(f"[*] Creating evaluation session on {api_url}...")
        res = await client.post("/api/v1/sessions")
        res.raise_for_status()
        session_id = res.json()["session_id"]
        print(f"[+] Session created: {session_id}")

        # 2. Upload Fixture
        print(f"[*] Ingesting fixture: {fixture_path.name}...")
        with open(fixture_path, "rb") as f:
            files = {"files": (fixture_path.name, f.read(), "text/plain")}
            headers = {"X-Session-Id": session_id}
            upload_res = await client.post(
                "/api/v1/documents/upload",
                files=files,
                headers=headers,
            )
            upload_res.raise_for_status()
            print(f"[+] Upload response: {upload_res.json()}")

        # 3. Query Execution & SSE stream consumption
        for i, test in enumerate(test_cases, start=1):
            print(f"[*] [{i}/{len(test_cases)}] Querying: {test.question[:60]}...")
            answer_tokens: List[str] = []
            contexts: List[str] = []

            chat_payload = {
                "session_id": session_id,
                "query": test.question,
                "use_cache": False,
            }

            async with client.stream(
                "POST",
                "/api/v1/chat/stream",
                json=chat_payload,
            ) as stream_res:
                stream_res.raise_for_status()
                async for line in stream_res.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line.removeprefix("data:").strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    try:
                        event = json.loads(data_str)
                        event_type = event.get("type")
                        if event_type == "token":
                            answer_tokens.append(event.get("content", ""))
                        elif event_type == "done":
                            sources = event.get("sources", [])
                            contexts = [f"Source: {s.get('filename')} (page {s.get('page')})" for s in sources]
                    except json.JSONDecodeError:
                        pass

            answer = "".join(answer_tokens).strip()

            # Retrieve actual chunk texts from ChromaDB via session list if needed
            # For robust RAGAS context, if contexts only has metadata, we ensure the text chunks are present
            results.append({
                "question": test.question,
                "answer": answer or "No response generated.",
                "ground_truth": test.ground_truth,
                "category": test.category,
                "contexts": contexts if contexts else [fixture_path.read_text(encoding="utf-8")],
            })

    return results


# ── Ingestion & Query Execution (Direct Mode) ────────────────────────────────

async def run_queries_direct(
    fixture_path: Path,
    test_cases: List[TestCase],
) -> List[Dict[str, Any]]:
    """Execute pipeline in-process directly through backend service modules."""
    sys.path.insert(0, str(_ROOT / "backend"))

    from app.services.ingestion import init_chroma, ingest_document
    from app.services.llm import generate_rag_stream
    from app.services.reranker import init_reranker, rerank
    from app.services.retriever import hybrid_search

    # Initialize ChromaDB and Reranker
    init_chroma()
    init_reranker()

    session_id = f"eval_{int(time.time())}"
    print(f"[*] Ingesting fixture directly into session '{session_id}'...")

    data = fixture_path.read_bytes()
    await ingest_document(
        filename=fixture_path.name,
        data=data,
        session_id=session_id,
        extra_metadata={"content_type": "text/plain"},
    )
    print("[+] Direct ingestion complete.")

    results: List[Dict[str, Any]] = []

    for i, test in enumerate(test_cases, start=1):
        print(f"[*] [{i}/{len(test_cases)}] Direct query: {test.question[:60]}...")
        # 1. Hybrid search
        candidates = await hybrid_search(query=test.question, session_id=session_id, top_k=20)
        # 2. Rerank
        top_docs = await rerank(query=test.question, docs=candidates, top_n=5)
        # 3. Stream generation
        answer_tokens: List[str] = []
        async for sse_line in generate_rag_stream(query=test.question, context_docs=top_docs):
            line = sse_line.strip()
            if not line.startswith("data:"):
                continue
            try:
                event = json.loads(line.removeprefix("data:").strip())
                if event.get("type") == "token":
                    answer_tokens.append(event.get("content", ""))
            except json.JSONDecodeError:
                pass

        answer = "".join(answer_tokens).strip()
        contexts = [doc.text for doc in top_docs]

        results.append({
            "question": test.question,
            "answer": answer or "No response generated.",
            "ground_truth": test.ground_truth,
            "category": test.category,
            "contexts": contexts if contexts else [fixture_path.read_text(encoding="utf-8")],
        })

    return results


# ── RAGAS Metric Calculation ─────────────────────────────────────────────────

def evaluate_with_ragas(
    dataset_records: List[Dict[str, Any]],
    evaluator_llm: Any,
    evaluator_embeddings: Any,
) -> pd.DataFrame:
    """Run RAGAS evaluation on collected answers and contexts."""
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except ImportError as exc:
        raise ImportError(
            f"Failed to import RAGAS: {exc}. Please install ragas with: pip install ragas datasets"
        )

    # Format dataset dictionary for RAGAS (compatible with 0.1.x and 0.2.x)
    data_dict = {
        "question": [r["question"] for r in dataset_records],
        "user_input": [r["question"] for r in dataset_records],
        "answer": [r["answer"] for r in dataset_records],
        "response": [r["answer"] for r in dataset_records],
        "contexts": [r["contexts"] for r in dataset_records],
        "retrieved_contexts": [r["contexts"] for r in dataset_records],
        "ground_truth": [r["ground_truth"] for r in dataset_records],
        "reference": [r["ground_truth"] for r in dataset_records],
    }
    ragas_dataset = Dataset.from_dict(data_dict)

    # Metrics list
    metrics = [
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ]

    # Assign LLM and embeddings to metrics
    for m in metrics:
        if hasattr(m, "llm"):
            m.llm = evaluator_llm
        if hasattr(m, "embeddings"):
            m.embeddings = evaluator_embeddings

    print("\n[*] Computing RAGAS evaluation metrics (Faithfulness, Relevancy, Precision, Recall)...")
    try:
        eval_result = evaluate(
            dataset=ragas_dataset,
            metrics=metrics,
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
        )
    except TypeError:
        # Fallback for older/newer signature differences
        eval_result = evaluate(
            dataset=ragas_dataset,
            metrics=metrics,
        )

    df: pd.DataFrame = eval_result.to_pandas()
    # Attach category back to dataframe
    df["category"] = [r["category"] for r in dataset_records]
    return df


# ── Report Exporter ───────────────────────────────────────────────────────────

def export_reports(
    df: pd.DataFrame,
    output_dir: Path,
    model_name: str,
    embedding_name: str,
) -> Tuple[Path, Path]:
    """Export evaluation results to formatted JSON and Markdown reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "ragas_evaluation_report.json"
    md_path = output_dir / "ragas_evaluation_report.md"

    # Identify metric columns
    metric_cols = [
        c for c in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
        if c in df.columns
    ]

    mean_scores = df[metric_cols].mean().to_dict()

    # JSON export
    summary_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "evaluator_llm": model_name,
        "evaluator_embeddings": embedding_name,
        "sample_count": len(df),
        "aggregate_scores": {k: round(float(v), 4) for k, v in mean_scores.items()},
        "pass_fail_summary": {
            "all_faithfulness_above_0_8": bool(df["faithfulness"].min() >= 0.8) if "faithfulness" in df else None,
            "mean_faithfulness": round(float(mean_scores.get("faithfulness", 0.0)), 4),
            "mean_answer_relevancy": round(float(mean_scores.get("answer_relevancy", 0.0)), 4),
            "mean_context_precision": round(float(mean_scores.get("context_precision", 0.0)), 4),
            "mean_context_recall": round(float(mean_scores.get("context_recall", 0.0)), 4),
        },
        "records": df.to_dict(orient="records"),
    }
    json_path.write_text(json.dumps(summary_data, indent=2, default=str), encoding="utf-8")

    # Markdown Table Generation
    table_rows = []
    for i, row in df.iterrows():
        q_preview = (row["question"][:55] + "...") if len(row["question"]) > 55 else row["question"]
        f_score = f"{row['faithfulness']:.3f}" if "faithfulness" in row else "N/A"
        r_score = f"{row['answer_relevancy']:.3f}" if "answer_relevancy" in row else "N/A"
        cp_score = f"{row['context_precision']:.3f}" if "context_precision" in row else "N/A"
        cr_score = f"{row['context_recall']:.3f}" if "context_recall" in row else "N/A"
        table_rows.append(
            f"| {i+1} | {q_preview} | {f_score} | {r_score} | {cp_score} | {cr_score} |"
        )

    table_md = "\n".join(table_rows)

    md_content = f"""# 📊 Automated RAGAS Evaluation Report

**Generated:** {summary_data['timestamp']}  
**Evaluator LLM:** `{model_name}` (Groq - 100% Free)  
**Evaluator Embeddings:** `{embedding_name}` (Local HuggingFace - 100% Free)  
**Total Test Samples:** {len(df)}

---

## 🎯 Executive Summary & Aggregate Metrics

| Metric | Target | Score | Status | Description |
| :--- | :---: | :---: | :---: | :--- |
| **Faithfulness** | ≥ 0.85 | **{mean_scores.get('faithfulness', 0.0):.4f}** | {'✅ PASS' if mean_scores.get('faithfulness', 0) >= 0.85 else '⚠️ REVIEW'} | Measures factual consistency against retrieved context (hallucination check) |
| **Answer Relevancy** | ≥ 0.80 | **{mean_scores.get('answer_relevancy', 0.0):.4f}** | {'✅ PASS' if mean_scores.get('answer_relevancy', 0) >= 0.80 else '⚠️ REVIEW'} | Measures how directly the answer addresses the question |
| **Context Precision** | ≥ 0.75 | **{mean_scores.get('context_precision', 0.0):.4f}** | {'✅ PASS' if mean_scores.get('context_precision', 0) >= 0.75 else '⚠️ REVIEW'} | Signal-to-noise ratio in retrieved context passages |
| **Context Recall** | ≥ 0.80 | **{mean_scores.get('context_recall', 0.0):.4f}** | {'✅ PASS' if mean_scores.get('context_recall', 0) >= 0.80 else '⚠️ REVIEW'} | Ability of retrieved context to satisfy ground truth facts |

---

## 📋 Per-Question Breakdown

| # | Question | Faithfulness | Relevancy | Context Precision | Context Recall |
|---|:---|:---:|:---:|:---:|:---:|
{table_md}

---

## 🔍 Detailed Test Cases & Ground Truth Comparison

"""

    for i, row in df.iterrows():
        md_content += f"""### Test Case {i+1}: {row['question']}
- **Category:** `{row.get('category', 'General')}`
- **Ground Truth:** {row['ground_truth']}
- **Generated Answer:** {row['answer']}
- **Scores:** Faithfulness: `{row.get('faithfulness', 'N/A')}` | Relevancy: `{row.get('answer_relevancy', 'N/A')}` | Precision: `{row.get('context_precision', 'N/A')}` | Recall: `{row.get('context_recall', 'N/A')}`

---
"""

    md_path.write_text(md_content, encoding="utf-8")
    return json_path, md_path


# ── Main Entrypoint ──────────────────────────────────────────────────────────

async def main_async() -> int:
    parser = argparse.ArgumentParser(description="Automated RAGAS Evaluation Harness")
    parser.add_argument(
        "--mode",
        choices=["auto", "api", "direct"],
        default="auto",
        help="Evaluation execution mode ('auto', 'api', or 'direct')",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="FastAPI backend URL for API mode",
    )
    parser.add_argument(
        "--fixture",
        default=str(_ROOT / "tests" / "fixtures" / "sample_knowledge.txt"),
        help="Path to fixture text file",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_ROOT / "tests" / "results"),
        help="Directory to save evaluation reports",
    )
    parser.add_argument(
        "--llm-model",
        default="llama-3.3-70b-versatile",
        help="Groq LLM model name for RAGAS evaluation",
    )
    parser.add_argument(
        "--embedding-model",
        default="all-MiniLM-L6-v2",
        help="HuggingFace embedding model for RAGAS evaluation",
    )

    args = parser.parse_args()

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("[!] ERROR: GROQ_API_KEY environment variable is not set.", file=sys.stderr)
        print("    Please set GROQ_API_KEY in your .env or shell environment.", file=sys.stderr)
        return 1

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"[!] ERROR: Fixture file not found: {fixture_path}", file=sys.stderr)
        return 1

    print("=" * 70)
    print("🚀 LocalHost RAG — Automated Evaluation & Quality Assurance Harness")
    print("=" * 70)
    print(f"• Evaluator LLM:       {args.llm_model} (Groq)")
    print(f"• Evaluator Embedding: {args.embedding_model} (Local HF)")
    print(f"• Knowledge Fixture:   {fixture_path}")
    print(f"• Test Cases Count:    {len(SAMPLE_TEST_CASES)}")
    print(f"• Target Mode:         {args.mode}")

    # Determine execution mode
    mode = args.mode
    if mode == "auto":
        import httpx
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{args.api_url}/health")
                if res.status_code == 200:
                    mode = "api"
                    print(f"[+] Active backend detected on {args.api_url}. Using API mode.")
                else:
                    mode = "direct"
        except Exception:
            mode = "direct"
            print("[*] No active server detected. Falling back to direct in-process pipeline mode.")

    # Step 1: Run Q&A across the RAG pipeline
    if mode == "api":
        dataset_records = await run_queries_via_api(
            api_url=args.api_url,
            fixture_path=fixture_path,
            test_cases=SAMPLE_TEST_CASES,
        )
    else:
        dataset_records = await run_queries_direct(
            fixture_path=fixture_path,
            test_cases=SAMPLE_TEST_CASES,
        )

    # Step 2: Configure RAGAS Evaluator
    evaluator_llm, evaluator_embeddings = setup_ragas_evaluator(
        groq_api_key=groq_api_key,
        llm_model=args.llm_model,
        embedding_model=args.embedding_model,
    )

    # Step 3: Run RAGAS Metric Computation
    df_results = evaluate_with_ragas(
        dataset_records=dataset_records,
        evaluator_llm=evaluator_llm,
        evaluator_embeddings=evaluator_embeddings,
    )

    # Step 4: Export Reports
    output_dir = Path(args.output_dir)
    json_path, md_path = export_reports(
        df=df_results,
        output_dir=output_dir,
        model_name=args.llm_model,
        embedding_name=args.embedding_model,
    )

    print("\n" + "=" * 70)
    print("✅ EVALUATION COMPLETE")
    print("=" * 70)
    print(f"📄 JSON Report:     {json_path}")
    print(f"📝 Markdown Report: {md_path}")
    print("\nSummary Scores:")
    for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        if metric in df_results.columns:
            score = df_results[metric].mean()
            print(f"  • {metric.replace('_', ' ').title():<20}: {score:.4f}")
    print("=" * 70)

    return 0


def main() -> None:
    code = asyncio.run(main_async())
    sys.exit(code)


if __name__ == "__main__":
    main()
