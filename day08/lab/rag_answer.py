"""
rag_answer.py - Retrieval and grounded answering for Day 08 lab.
"""

import argparse
import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()


COLLECTION_NAME = "rag_lab"
TOP_K_SEARCH = 10
TOP_K_SELECT = 3
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
ABSTAIN_MESSAGE = "Khong du du lieu."

DENSE_ABSTAIN_THRESHOLD = 0.20
RERANK_ABSTAIN_THRESHOLD = 0.00
RERANK_MODEL_NAME = os.getenv(
    "RERANK_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
)

_rerank_model = None


def retrieve_dense(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """Query ChromaDB using the same embedding model used for indexing."""
    import chromadb

    from index import CHROMA_DB_DIR, get_embedding

    if not query or not query.strip():
        return []

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


def retrieve_sparse(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """Sparse retrieval is not used in this lab variant."""
    _ = query, top_k
    print("[retrieve_sparse] Not implemented. Returning empty result.")
    return []


def retrieve_hybrid(
    query: str,
    top_k: int = TOP_K_SEARCH,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
) -> List[Dict[str, Any]]:
    """Fallback to dense retrieval because this team variant uses rerank."""
    _ = dense_weight, sparse_weight
    print("[retrieve_hybrid] Using dense retrieval fallback.")
    return retrieve_dense(query, top_k=top_k)


def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = TOP_K_SELECT,
) -> List[Dict[str, Any]]:
    """Rerank candidate chunks with a cross-encoder."""
    global _rerank_model

    if not candidates or top_k <= 0:
        return []

    if _rerank_model is None:
        from sentence_transformers import CrossEncoder

        print(f"[Rerank] Loading cross-encoder model: {RERANK_MODEL_NAME}")
        _rerank_model = CrossEncoder(RERANK_MODEL_NAME)

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


def build_context_block(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a context block for prompting."""
    context_parts = []
    for index, chunk in enumerate(chunks, start=1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", "unknown")
        section = meta.get("section", "")
        score = chunk.get("score", 0.0)
        text = chunk.get("text", "")

        header = f"[{index}] {source}"
        if section:
            header += f" | {section}"
        header += f" | score={score:.2f}"

        context_parts.append(f"{header}\n{text}")

    return "\n\n".join(context_parts)


def build_grounded_prompt(query: str, context_block: str) -> str:
    """Build a concise grounded-answer prompt."""
    return f"""You are a careful RAG assistant.
Answer only from the retrieved context below.
If the context is insufficient, reply exactly: "{ABSTAIN_MESSAGE}"
Use citation markers like [1], [2] based on the snippets.
Keep the answer short, factual, and in the same language as the question.

Question: {query}

Context:
{context_block}

Answer:"""


def call_llm(prompt: str) -> str:
    """Call the configured LLM provider."""
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-...":
            raise ValueError("Thieu OPENAI_API_KEY hop le trong .env.")

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
            raise ValueError("Thieu GOOGLE_API_KEY hop le trong .env.")

        import google.generativeai as genai

        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return (response.text or "").strip()

    raise ValueError(f"LLM_PROVIDER khong hop le: {provider}")


def should_abstain(chunks: List[Dict[str, Any]], use_rerank: bool) -> bool:
    """Check whether retrieved evidence is too weak to answer."""
    if not chunks:
        return True

    best_score = float(chunks[0].get("score", 0.0))
    threshold = RERANK_ABSTAIN_THRESHOLD if use_rerank else DENSE_ABSTAIN_THRESHOLD
    return best_score < threshold


def rag_answer(
    query: str,
    retrieval_mode: str = "dense",
    top_k_search: int = TOP_K_SEARCH,
    top_k_select: int = TOP_K_SELECT,
    use_rerank: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Run retrieval, optional rerank, grounded generation, and return a result dict."""
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
        raise ValueError(f"retrieval_mode khong hop le: {retrieval_mode}")

    if verbose:
        print(f"\n[RAG] Query: {query}")
        print(f"[RAG] Retrieved {len(candidates)} candidates (mode={retrieval_mode})")
        for index, chunk in enumerate(candidates[:3], start=1):
            source = chunk.get("metadata", {}).get("source", "?")
            score = float(chunk.get("score", 0.0))
            print(f"  [{index}] score={score:.3f} | {source}")

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
    sources = sorted(
        {
            chunk.get("metadata", {}).get("source", "unknown")
            for chunk in selected_chunks
        }
    )

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "chunks_used": selected_chunks,
        "config": config,
    }


def compare_retrieval_strategies(query: str) -> None:
    """Compare dense baseline and dense + rerank on one query."""
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


def main() -> None:
    """CLI entry point for manual testing."""
    parser = argparse.ArgumentParser(description="Run the RAG pipeline for one query.")
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
