"""
rag_answer.py - Sprint 2 + Sprint 3: Retrieval and grounded answering.

Sprint 2:
- Dense retrieval from ChromaDB
- Grounded answer generation with citations
- Single-query CLI for manual testing

Sprint 3:
- Optional rerank with cross-encoder
- Strategy comparison helper
"""

import argparse
import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# CONFIG
# =============================================================================

COLLECTION_NAME = "rag_lab"
TOP_K_SEARCH = 10
TOP_K_SELECT = 3
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
ABSTAIN_MESSAGE = "Không đủ dữ liệu."

# Heuristics for abstention.
DENSE_ABSTAIN_THRESHOLD = 0.20
RERANK_ABSTAIN_THRESHOLD = 0.00

_rerank_model = None


# =============================================================================
# RETRIEVAL - DENSE
# =============================================================================

def retrieve_dense(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Query ChromaDB with the same embedding model used during indexing.
    """
    import chromadb

    from index import CHROMA_DB_DIR, get_embedding

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection(COLLECTION_NAME)

    query_embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    chunks: List[Dict[str, Any]] = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        chunks.append(
            {
                "text": document,
                "metadata": metadata or {},
                "score": 1 - float(distance),
            }
        )

    return chunks


# =============================================================================
# RETRIEVAL - OPTIONAL SPRINT 3 STUBS
# =============================================================================

def retrieve_sparse(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Placeholder for BM25 retrieval if the team later chooses hybrid retrieval.
    """
    print("[retrieve_sparse] Not implemented. Falling back to empty result.")
    return []


def retrieve_hybrid(
    query: str,
    top_k: int = TOP_K_SEARCH,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    Placeholder hybrid retrieval. Current team choice is rerank, so dense is used.
    """
    _ = dense_weight, sparse_weight
    print("[retrieve_hybrid] Team selected rerank, fallback to dense retrieval.")
    return retrieve_dense(query, top_k)


# =============================================================================
# RERANK - SPRINT 3 VARIANT
# =============================================================================

def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = TOP_K_SELECT,
) -> List[Dict[str, Any]]:
    """
    Rerank candidate chunks with a cross-encoder.
    """
    global _rerank_model

    if not candidates or top_k <= 0:
        return []

    if _rerank_model is None:
        from sentence_transformers import CrossEncoder

        print("[Rerank] Loading cross-encoder model...")
        _rerank_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    pairs = [[query, chunk.get("text", "")] for chunk in candidates]
    scores = _rerank_model.predict(pairs)
    ranked = sorted(
        zip(candidates, scores),
        key=lambda item: float(item[1]),
        reverse=True,
    )

    selected_chunks: List[Dict[str, Any]] = []
    for chunk, score in ranked[:top_k]:
        updated_chunk = dict(chunk)
        updated_chunk["score"] = float(score)
        selected_chunks.append(updated_chunk)

    return selected_chunks


# =============================================================================
# PROMPTING
# =============================================================================

def build_context_block(chunks: List[Dict[str, Any]]) -> str:
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", "unknown")
        section = meta.get("section", "")
        score = chunk.get("score", 0.0)
        text = chunk.get("text", "")

        header = f"[{i}] {source}"
        if section:
            header += f" | {section}"
        header += f" | score={score:.2f}"

        context_parts.append(f"{header}\n{text}")

    return "\n\n".join(context_parts)


def build_grounded_prompt(query: str, context_block: str) -> str:
    return f"""You are a careful RAG assistant.
Answer only from the retrieved context below.
If the context is insufficient, reply exactly: \"{ABSTAIN_MESSAGE}\"
Use citation markers like [1], [2] based on the snippets.
Keep the answer short, factual, and in the same language as the question.

Question: {query}

Context:
{context_block}

Answer:"""


# =============================================================================
# LLM CALL
# =============================================================================

def call_llm(prompt: str) -> str:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-...":
            raise ValueError("Thiếu OPENAI_API_KEY hợp lệ trong .env.")

        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=256,
        )
        return (response.choices[0].message.content or "").strip()

    if provider == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "...":
            raise ValueError("Thiếu GOOGLE_API_KEY hợp lệ trong .env.")

        import google.generativeai as genai

        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return (response.text or "").strip()

    raise ValueError(f"LLM_PROVIDER không hợp lệ: {provider}")


# =============================================================================
# ABSTAIN CHECK
# =============================================================================

def should_abstain(chunks: List[Dict[str, Any]], use_rerank: bool) -> bool:
    if not chunks:
        return True

    best_score = chunks[0].get("score", 0.0)
    threshold = RERANK_ABSTAIN_THRESHOLD if use_rerank else DENSE_ABSTAIN_THRESHOLD
    return float(best_score) < threshold


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def rag_answer(
    query: str,
    retrieval_mode: str = "dense",
    top_k_search: int = TOP_K_SEARCH,
    top_k_select: int = TOP_K_SELECT,
    use_rerank: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    config = {
        "retrieval_mode": retrieval_mode,
        "top_k_search": top_k_search,
        "top_k_select": top_k_select,
        "use_rerank": use_rerank,
    }

    if retrieval_mode == "dense":
        candidates = retrieve_dense(query, top_k=top_k_search)
    elif retrieval_mode == "sparse":
        candidates = retrieve_sparse(query, top_k=top_k_search)
    elif retrieval_mode == "hybrid":
        candidates = retrieve_hybrid(query, top_k=top_k_search)
    else:
        raise ValueError(f"retrieval_mode không hợp lệ: {retrieval_mode}")

    if verbose:
        print(f"\n[RAG] Query: {query}")
        print(f"[RAG] Retrieved {len(candidates)} candidates (mode={retrieval_mode})")
        for i, chunk in enumerate(candidates[:3], 1):
            source = chunk.get("metadata", {}).get("source", "?")
            print(f"  [{i}] score={chunk.get('score', 0):.3f} | {source}")

    if use_rerank:
        selected_chunks = rerank(query, candidates, top_k=top_k_select)
    else:
        selected_chunks = candidates[:top_k_select]

    if verbose:
        print(f"[RAG] After select: {len(selected_chunks)} chunks")

    if should_abstain(selected_chunks, use_rerank=use_rerank):
        return {
            "query": query,
            "answer": ABSTAIN_MESSAGE,
            "sources": [],
            "chunks_used": selected_chunks,
            "config": config,
        }

    context_block = build_context_block(selected_chunks)
    prompt = build_grounded_prompt(query, context_block)

    if verbose:
        print(f"\n[RAG] Prompt preview:\n{prompt[:500]}...\n")

    answer = call_llm(prompt)
    sources = list({c.get("metadata", {}).get("source", "unknown") for c in selected_chunks})

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "chunks_used": selected_chunks,
        "config": config,
    }


# =============================================================================
# SPRINT 3 COMPARISON
# =============================================================================

def compare_retrieval_strategies(query: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"Query: {query}")
    print("=" * 60)

    experiments = [
        {"label": "baseline_dense", "retrieval_mode": "dense", "use_rerank": False},
        {"label": "dense_rerank", "retrieval_mode": "dense", "use_rerank": True},
    ]

    for experiment in experiments:
        print(f"\n--- {experiment['label']} ---")
        result = rag_answer(
            query=query,
            retrieval_mode=experiment["retrieval_mode"],
            use_rerank=experiment["use_rerank"],
            verbose=False,
        )
        print(f"Answer: {result['answer']}")
        print(f"Sources: {result['sources']}")


# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the RAG pipeline for one query."
    )
    parser.add_argument("query", help="Question to answer")
    parser.add_argument(
        "--retrieval-mode",
        choices=["dense", "sparse", "hybrid"],
        default="dense",
        help="Retrieval mode before select/rerank",
    )
    parser.add_argument(
        "--top-k-search",
        type=int,
        default=TOP_K_SEARCH,
        help="Number of chunks retrieved before rerank",
    )
    parser.add_argument(
        "--top-k-select",
        type=int,
        default=TOP_K_SELECT,
        help="Number of chunks kept after select/rerank",
    )
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Disable cross-encoder rerank",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print debug logs",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare dense baseline vs dense+rerank for the query",
    )
    args = parser.parse_args()

    if args.compare:
        compare_retrieval_strategies(args.query)
        return

    result = rag_answer(
        query=args.query,
        retrieval_mode=args.retrieval_mode,
        top_k_search=args.top_k_search,
        top_k_select=args.top_k_select,
        use_rerank=not args.no_rerank,
        verbose=args.verbose,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
