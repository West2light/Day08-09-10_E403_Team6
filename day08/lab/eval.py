"""
eval.py â€” Sprint 4: Evaluation & Scorecard
==========================================
Má»¥c tiÃªu Sprint 4 (60 phÃºt):
  - Cháº¡y 10 test questions qua pipeline
  - Cháº¥m Ä‘iá»ƒm theo 4 metrics: Faithfulness, Relevance, Context Recall, Completeness
  - So sÃ¡nh baseline vs variant
  - Ghi káº¿t quáº£ ra scorecard

Definition of Done Sprint 4:
  âœ“ Demo cháº¡y end-to-end (index â†’ retrieve â†’ answer â†’ score)
  âœ“ Scorecard trÆ°á»›c vÃ  sau tuning
  âœ“ A/B comparison: baseline vs variant vá»›i giáº£i thÃ­ch vÃ¬ sao variant tá»‘t hÆ¡n

A/B Rule (tá»« slide):
  Chá»‰ Ä‘á»•i Má»˜T biáº¿n má»—i láº§n Ä‘á»ƒ biáº¿t Ä‘iá»u gÃ¬ thá»±c sá»± táº¡o ra cáº£i thiá»‡n.
  Äá»•i Ä‘á»“ng thá»i chunking + hybrid + rerank + prompt = khÃ´ng biáº¿t biáº¿n nÃ o cÃ³ tÃ¡c dá»¥ng.
"""

import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from rag_answer import rag_answer

# =============================================================================
# Cáº¤U HÃŒNH
# =============================================================================

TEST_QUESTIONS_PATH = Path(__file__).parent / "data" / "test_questions.json"
RESULTS_DIR = Path(__file__).parent / "results"

# Cáº¥u hÃ¬nh baseline (Sprint 2)
BASELINE_CONFIG = {
    "retrieval_mode": "dense",
    "top_k_search": 10,
    "top_k_select": 3,
    "use_rerank": False,
    "label": "baseline_dense",
}

# Cáº¥u hÃ¬nh variant (Sprint 3 â€” Ä‘iá»u chá»‰nh theo lá»±a chá»n cá»§a nhÃ³m)
# TODO Sprint 4: Cáº­p nháº­t VARIANT_CONFIG theo variant nhÃ³m Ä‘Ã£ implement
VARIANT_CONFIG = {
    "retrieval_mode": "dense",
    "top_k_search": 10,
    "top_k_select": 3,
    "use_rerank": True,
    "label": "variant_dense_rerank",
}


# =============================================================================
# SCORING FUNCTIONS
# 4 metrics tá»« slide: Faithfulness, Answer Relevance, Context Recall, Completeness
# =============================================================================

def score_faithfulness(
    answer: str,
    chunks_used: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Faithfulness: CÃ¢u tráº£ lá»i cÃ³ bÃ¡m Ä‘Ãºng chá»©ng cá»© Ä‘Ã£ retrieve khÃ´ng?
    CÃ¢u há»i: Model cÃ³ tá»± bá»‹a thÃªm thÃ´ng tin ngoÃ i retrieved context khÃ´ng?

    Thang Ä‘iá»ƒm 1-5:
      5: Má»i thÃ´ng tin trong answer Ä‘á»u cÃ³ trong retrieved chunks
      4: Gáº§n nhÆ° hoÃ n toÃ n grounded, 1 chi tiáº¿t nhá» chÆ°a cháº¯c cháº¯n
      3: Pháº§n lá»›n grounded, má»™t sá»‘ thÃ´ng tin cÃ³ thá»ƒ tá»« model knowledge
      2: Nhiá»u thÃ´ng tin khÃ´ng cÃ³ trong retrieved chunks
      1: CÃ¢u tráº£ lá»i khÃ´ng grounded, pháº§n lá»›n lÃ  model bá»‹a

    TODO Sprint 4 â€” CÃ³ 2 cÃ¡ch cháº¥m:

    CÃ¡ch 1 â€” Cháº¥m thá»§ cÃ´ng (Manual, Ä‘Æ¡n giáº£n):
        Äá»c answer vÃ  chunks_used, cháº¥m Ä‘iá»ƒm theo thang trÃªn.
        Ghi lÃ½ do ngáº¯n gá»n vÃ o "notes".

    CÃ¡ch 2 â€” LLM-as-Judge (Tá»± Ä‘á»™ng, nÃ¢ng cao):
        Gá»­i prompt cho LLM:
            "Given these retrieved chunks: {chunks}
             And this answer: {answer}
             Rate the faithfulness on a scale of 1-5.
             5 = completely grounded in the provided context.
             1 = answer contains information not in the context.
             Output JSON: {'score': <int>, 'reason': '<string>'}"

    Tráº£ vá» dict vá»›i: score (1-5) vÃ  notes (lÃ½ do)
    """
    # TODO Sprint 4: Implement scoring
    # Táº¡m thá»i tráº£ vá» None (yÃªu cáº§u cháº¥m thá»§ cÃ´ng)
    if not answer or not answer.strip():
        return {
            "score": 1,
            "notes": "Answer rá»—ng hoáº·c khÃ´ng há»£p lá»‡.",
        }

    if not chunks_used:
        return {
            "score": 1,
            "notes": "KhÃ´ng cÃ³ retrieved chunks Ä‘á»ƒ Ä‘á»‘i chiáº¿u faithfulness.",
        }

    from rag_answer import call_llm

    context_parts = []
    for i, chunk in enumerate(chunks_used, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", "unknown")
        section = meta.get("section", "")
        text = chunk.get("text", "")

        header = f"[{i}] {source}"
        if section:
            header += f" | {section}"

        context_parts.append(f"{header}\n{text}")

    context_block = "\n\n".join(context_parts)

    prompt = f"""You are evaluating faithfulness of an answer to the provided evidence.

Task:
Rate how well the answer is grounded in the retrieved chunks on a scale of 1 to 5.

Scoring rubric:
5 = Every important claim in the answer is supported by the retrieved chunks.
4 = Almost entirely grounded; only one small detail is uncertain.
3 = Mostly grounded, but some details may come from outside knowledge or are weakly supported.
2 = Several parts of the answer are not supported by the retrieved chunks.
1 = The answer is largely ungrounded or contains substantial fabricated information.

Rules:
- Judge only based on the retrieved chunks.
- Do not reward answers for being plausible.
- If the answer adds facts not present in the chunks, lower the score.
- Output ONLY valid JSON.
- Use this exact schema:
{{"score": <integer 1-5>, "notes": "<short reason>"}}

Retrieved chunks:
{context_block}

Answer:
{answer}

JSON:"""

    try:
        raw_output = call_llm(prompt)
        result = json.loads(raw_output)

        score = result.get("score")
        notes = result.get("notes", "")

        if not isinstance(score, int) or not (1 <= score <= 5):
            raise ValueError("Invalid score")

        return {
            "score": score,
            "notes": notes,
        }

    except Exception:
        return {
            "score": None,
            "notes": "LLM-as-judge failed. Cáº§n cháº¥m thá»§ cÃ´ng.",
        }


def score_answer_relevance(
    query: str,
    answer: str,
) -> Dict[str, Any]:
    """
    Answer Relevance: Answer cÃ³ tráº£ lá»i Ä‘Ãºng cÃ¢u há»i ngÆ°á»i dÃ¹ng há»i khÃ´ng?
    CÃ¢u há»i: Model cÃ³ bá»‹ láº¡c Ä‘á» hay tráº£ lá»i Ä‘Ãºng váº¥n Ä‘á» cá»‘t lÃµi khÃ´ng?

    Thang Ä‘iá»ƒm 1-5:
      5: Answer tráº£ lá»i trá»±c tiáº¿p vÃ  Ä‘áº§y Ä‘á»§ cÃ¢u há»i
      4: Tráº£ lá»i Ä‘Ãºng nhÆ°ng thiáº¿u vÃ i chi tiáº¿t phá»¥
      3: Tráº£ lá»i cÃ³ liÃªn quan nhÆ°ng chÆ°a Ä‘Ãºng trá»ng tÃ¢m
      2: Tráº£ lá»i láº¡c Ä‘á» má»™t pháº§n
      1: KhÃ´ng tráº£ lá»i cÃ¢u há»i

    TODO Sprint 4: Implement tÆ°Æ¡ng tá»± score_faithfulness
    """
    if not query or not query.strip():
        return {"score": 1, "notes": "Query rá»—ng."}

    if not answer or not answer.strip():
        return {"score": 1, "notes": "Answer rá»—ng."}

    from rag_answer import call_llm

    prompt = f"""You are evaluating answer relevance.

Task:
Rate how well the answer directly addresses the user's question on a scale of 1 to 5.

Scoring rubric:
5 = Directly and fully answers the question.
4 = Correctly answers the question but misses a minor detail.
3 = Related to the question but not fully focused on the core ask.
2 = Partially off-topic or only weakly answers the question.
1 = Does not answer the question.

Rules:
- Judge relevance to the question, not faithfulness to sources.
- Output ONLY valid JSON.
- Use this exact schema:
{{"score": <integer 1-5>, "notes": "<short reason>"}}

Question:
{query}

Answer:
{answer}

JSON:"""

    try:
        raw_output = call_llm(prompt)
        result = json.loads(raw_output)

        score = result.get("score")
        notes = result.get("notes", "")

        if not isinstance(score, int) or not (1 <= score <= 5):
            raise ValueError("Invalid score")

        return {
            "score": score,
            "notes": notes,
        }

    except Exception:
        return {
            "score": None,
            "notes": "LLM-as-judge failed. Cáº§n cháº¥m thá»§ cÃ´ng.",
        }


def score_context_recall(
    chunks_used: List[Dict[str, Any]],
    expected_sources: List[str],
) -> Dict[str, Any]:
    """
    Context Recall: Retriever cÃ³ mang vá» Ä‘á»§ evidence cáº§n thiáº¿t khÃ´ng?
    CÃ¢u há»i: Expected source cÃ³ náº±m trong retrieved chunks khÃ´ng?

    ÄÃ¢y lÃ  metric Ä‘o retrieval quality, khÃ´ng pháº£i generation quality.

    CÃ¡ch tÃ­nh Ä‘Æ¡n giáº£n:
        recall = (sá»‘ expected source Ä‘Æ°á»£c retrieve) / (tá»•ng sá»‘ expected sources)

    VÃ­ dá»¥:
        expected_sources = ["policy/refund-v4.pdf", "sla-p1-2026.pdf"]
        retrieved_sources = ["policy/refund-v4.pdf", "helpdesk-faq.md"]
        recall = 1/2 = 0.5

    TODO Sprint 4:
    1. Láº¥y danh sÃ¡ch source tá»« chunks_used
    2. Kiá»ƒm tra xem expected_sources cÃ³ trong retrieved sources khÃ´ng
    3. TÃ­nh recall score
    """
    if not expected_sources:
        # CÃ¢u há»i khÃ´ng cÃ³ expected source (vÃ­ dá»¥: "KhÃ´ng Ä‘á»§ dá»¯ liá»‡u" cases)
        return {"score": None, "recall": None, "notes": "No expected sources"}

    retrieved_sources = {
        c.get("metadata", {}).get("source", "")
        for c in chunks_used
    }

    # TODO: Kiá»ƒm tra matching theo partial path (vÃ¬ source paths cÃ³ thá»ƒ khÃ¡c format)
    found = 0
    missing = []
    for expected in expected_sources:
        # Kiá»ƒm tra partial match (tÃªn file)
        expected_name = expected.split("/")[-1].replace(".pdf", "").replace(".md", "")
        matched = any(expected_name.lower() in r.lower() for r in retrieved_sources)
        if matched:
            found += 1
        else:
            missing.append(expected)

    recall = found / len(expected_sources) if expected_sources else 0

    return {
        "score": round(recall * 5),  # Convert to 1-5 scale
        "recall": recall,
        "found": found,
        "missing": missing,
        "notes": f"Retrieved: {found}/{len(expected_sources)} expected sources" +
                 (f". Missing: {missing}" if missing else ""),
    }


def score_completeness(
    query: str,
    answer: str,
    expected_answer: str,
) -> Dict[str, Any]:
    """
    Completeness: Answer cÃ³ thiáº¿u Ä‘iá»u kiá»‡n ngoáº¡i lá»‡ hoáº·c bÆ°á»›c quan trá»ng khÃ´ng?
    CÃ¢u há»i: Answer cÃ³ bao phá»§ Ä‘á»§ thÃ´ng tin so vá»›i expected_answer khÃ´ng?

    Thang Ä‘iá»ƒm 1-5:
      5: Answer bao gá»“m Ä‘á»§ táº¥t cáº£ Ä‘iá»ƒm quan trá»ng trong expected_answer
      4: Thiáº¿u 1 chi tiáº¿t nhá»
      3: Thiáº¿u má»™t sá»‘ thÃ´ng tin quan trá»ng
      2: Thiáº¿u nhiá»u thÃ´ng tin quan trá»ng
      1: Thiáº¿u pháº§n lá»›n ná»™i dung cá»‘t lÃµi

    TODO Sprint 4:
    Option 1 â€” Cháº¥m thá»§ cÃ´ng: So sÃ¡nh answer vs expected_answer vÃ  cháº¥m.
    Option 2 â€” LLM-as-Judge:
        "Compare the model answer with the expected answer.
         Rate completeness 1-5. Are all key points covered?
         Output: {'score': int, 'missing_points': [str]}"
    """
    if not answer or not answer.strip():
        return {"score": 1, "notes": "Answer rá»—ng."}

    if not expected_answer or not expected_answer.strip():
        return {"score": None, "notes": "KhÃ´ng cÃ³ expected_answer Ä‘á»ƒ cháº¥m completeness."}

    from rag_answer import call_llm

    prompt = f"""You are evaluating completeness of a model answer.

Task:
Compare the model answer with the expected answer and rate completeness on a scale of 1 to 5.

Scoring rubric:
5 = Covers all important points from the expected answer.
4 = Missing one small detail.
3 = Missing some important information.
2 = Missing many important points.
1 = Misses most of the core content.

Rules:
- Focus on coverage of key points.
- Do not require identical wording.
- Output ONLY valid JSON.
- Use this exact schema:
{{"score": <integer 1-5>, "notes": "<short reason>"}}

Question:
{query}

Expected answer:
{expected_answer}

Model answer:
{answer}

JSON:"""

    try:
        raw_output = call_llm(prompt)
        result = json.loads(raw_output)

        score = result.get("score")
        notes = result.get("notes", "")

        if not isinstance(score, int) or not (1 <= score <= 5):
            raise ValueError("Invalid score")

        return {
            "score": score,
            "notes": notes,
        }

    except Exception:
        return {
            "score": None,
            "notes": "LLM-as-judge failed. Cáº§n cháº¥m thá»§ cÃ´ng.",
        }


# =============================================================================
# SCORECARD RUNNER
# =============================================================================

def run_scorecard(
    config: Dict[str, Any],
    test_questions: Optional[List[Dict]] = None,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    Cháº¡y toÃ n bá»™ test questions qua pipeline vÃ  cháº¥m Ä‘iá»ƒm.

    Args:
        config: Pipeline config (retrieval_mode, top_k, use_rerank, ...)
        test_questions: List cÃ¢u há»i (load tá»« JSON náº¿u None)
        verbose: In káº¿t quáº£ tá»«ng cÃ¢u

    Returns:
        List scorecard results, má»—i item lÃ  má»™t row

    TODO Sprint 4:
    1. Load test_questions tá»« data/test_questions.json
    2. Vá»›i má»—i cÃ¢u há»i:
       a. Gá»i rag_answer() vá»›i config tÆ°Æ¡ng á»©ng
       b. Cháº¥m 4 metrics
       c. LÆ°u káº¿t quáº£
    3. TÃ­nh average scores
    4. In báº£ng káº¿t quáº£
    """
    if test_questions is None:
        with open(TEST_QUESTIONS_PATH, "r", encoding="utf-8") as f:
            test_questions = json.load(f)

    results = []
    label = config.get("label", "unnamed")

    print(f"\n{'='*70}")
    print(f"Cháº¡y scorecard: {label}")
    print(f"Config: {config}")
    print('='*70)

    for q in test_questions:
        question_id = q["id"]
        query = q["question"]
        expected_answer = q.get("expected_answer", "")
        expected_sources = q.get("expected_sources", [])
        category = q.get("category", "")

        if verbose:
            print(f"\n[{question_id}] {query}")

        # --- Gá»i pipeline ---
        try:
            result = rag_answer(
                query=query,
                retrieval_mode=config.get("retrieval_mode", "dense"),
                top_k_search=config.get("top_k_search", 10),
                top_k_select=config.get("top_k_select", 3),
                use_rerank=config.get("use_rerank", False),
                verbose=False,
            )
            answer = result["answer"]
            chunks_used = result["chunks_used"]

        except NotImplementedError:
            answer = "PIPELINE_NOT_IMPLEMENTED"
            chunks_used = []
        except Exception as e:
            answer = f"ERROR: {e}"
            chunks_used = []

        # --- Cháº¥m Ä‘iá»ƒm ---
        faith = score_faithfulness(answer, chunks_used)
        relevance = score_answer_relevance(query, answer)
        recall = score_context_recall(chunks_used, expected_sources)
        complete = score_completeness(query, answer, expected_answer)

        row = {
            "id": question_id,
            "category": category,
            "query": query,
            "answer": answer,
            "expected_answer": expected_answer,
            "faithfulness": faith["score"],
            "faithfulness_notes": faith["notes"],
            "relevance": relevance["score"],
            "relevance_notes": relevance["notes"],
            "context_recall": recall["score"],
            "context_recall_notes": recall["notes"],
            "completeness": complete["score"],
            "completeness_notes": complete["notes"],
            "config_label": label,
        }
        results.append(row)

        if verbose:
            print(f"  Answer: {answer[:100]}...")
            print(f"  Faithful: {faith['score']} | Relevant: {relevance['score']} | "
                  f"Recall: {recall['score']} | Complete: {complete['score']}")

    # TÃ­nh averages (bá» qua None)
    for metric in ["faithfulness", "relevance", "context_recall", "completeness"]:
        scores = [r[metric] for r in results if r[metric] is not None]
        avg = sum(scores) / len(scores) if scores else None
        print(f"\nAverage {metric}: {avg:.2f}" if avg else f"\nAverage {metric}: N/A (chÆ°a cháº¥m)")

    return results


# =============================================================================
# A/B COMPARISON
# =============================================================================

def compare_ab(
    baseline_results: List[Dict],
    variant_results: List[Dict],
    output_csv: Optional[str] = None,
) -> None:
    """
    So sÃ¡nh baseline vs variant theo tá»«ng cÃ¢u há»i vÃ  tá»•ng thá»ƒ.

    TODO Sprint 4:
    Äiá»n vÃ o báº£ng sau Ä‘á»ƒ trÃ¬nh bÃ y trong bÃ¡o cÃ¡o:

    | Metric          | Baseline | Variant | Delta |
    |-----------------|----------|---------|-------|
    | Faithfulness    |   ?/5    |   ?/5   |  +/?  |
    | Answer Relevance|   ?/5    |   ?/5   |  +/?  |
    | Context Recall  |   ?/5    |   ?/5   |  +/?  |
    | Completeness    |   ?/5    |   ?/5   |  +/?  |

    CÃ¢u há»i cáº§n tráº£ lá»i:
    - Variant tá»‘t hÆ¡n baseline á»Ÿ cÃ¢u nÃ o? VÃ¬ sao?
    - Biáº¿n nÃ o (chunking / hybrid / rerank) Ä‘Ã³ng gÃ³p nhiá»u nháº¥t?
    - CÃ³ cÃ¢u nÃ o variant láº¡i kÃ©m hÆ¡n baseline khÃ´ng? Táº¡i sao?
    """
    metrics = ["faithfulness", "relevance", "context_recall", "completeness"]

    print(f"\n{'='*70}")
    print("A/B Comparison: Baseline vs Variant")
    print('='*70)
    print(f"{'Metric':<20} {'Baseline':>10} {'Variant':>10} {'Delta':>8}")
    print("-" * 55)

    for metric in metrics:
        b_scores = [r[metric] for r in baseline_results if r[metric] is not None]
        v_scores = [r[metric] for r in variant_results if r[metric] is not None]

        b_avg = sum(b_scores) / len(b_scores) if b_scores else None
        v_avg = sum(v_scores) / len(v_scores) if v_scores else None
        delta = (v_avg - b_avg) if (b_avg and v_avg) else None

        b_str = f"{b_avg:.2f}" if b_avg else "N/A"
        v_str = f"{v_avg:.2f}" if v_avg else "N/A"
        d_str = f"{delta:+.2f}" if delta else "N/A"

        print(f"{metric:<20} {b_str:>10} {v_str:>10} {d_str:>8}")

    # Per-question comparison
    print(f"\n{'CÃ¢u':<6} {'Baseline F/R/Rc/C':<22} {'Variant F/R/Rc/C':<22} {'Better?':<10}")
    print("-" * 65)

    b_by_id = {r["id"]: r for r in baseline_results}
    for v_row in variant_results:
        qid = v_row["id"]
        b_row = b_by_id.get(qid, {})

        b_scores_str = "/".join([
            str(b_row.get(m, "?")) for m in metrics
        ])
        v_scores_str = "/".join([
            str(v_row.get(m, "?")) for m in metrics
        ])

        # So sÃ¡nh Ä‘Æ¡n giáº£n
        b_total = sum(b_row.get(m, 0) or 0 for m in metrics)
        v_total = sum(v_row.get(m, 0) or 0 for m in metrics)
        better = "Variant" if v_total > b_total else ("Baseline" if b_total > v_total else "Tie")

        print(f"{qid:<6} {b_scores_str:<22} {v_scores_str:<22} {better:<10}")

    # Export to CSV
    if output_csv:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = RESULTS_DIR / output_csv
        combined = baseline_results + variant_results
        if combined:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=combined[0].keys())
                writer.writeheader()
                writer.writerows(combined)
            print(f"\nKáº¿t quáº£ Ä‘Ã£ lÆ°u vÃ o: {csv_path}")


# =============================================================================
# REPORT GENERATOR
# =============================================================================

def generate_scorecard_summary(results: List[Dict], label: str) -> str:
    """
    Táº¡o bÃ¡o cÃ¡o tÃ³m táº¯t scorecard dáº¡ng markdown.

    TODO Sprint 4: Cáº­p nháº­t template nÃ y theo káº¿t quáº£ thá»±c táº¿ cá»§a nhÃ³m.
    """
    metrics = ["faithfulness", "relevance", "context_recall", "completeness"]
    averages = {}
    for metric in metrics:
        scores = [r[metric] for r in results if r[metric] is not None]
        averages[metric] = sum(scores) / len(scores) if scores else None

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    md = f"""# Scorecard: {label}
Generated: {timestamp}

## Summary

| Metric | Average Score |
|--------|--------------|
"""
    for metric, avg in averages.items():
        avg_str = f"{avg:.2f}/5" if avg else "N/A"
        md += f"| {metric.replace('_', ' ').title()} | {avg_str} |\n"

    md += "\n## Per-Question Results\n\n"
    md += "| ID | Category | Faithful | Relevant | Recall | Complete | Notes |\n"
    md += "|----|----------|----------|----------|--------|----------|-------|\n"

    for r in results:
        md += (f"| {r['id']} | {r['category']} | {r.get('faithfulness', 'N/A')} | "
               f"{r.get('relevance', 'N/A')} | {r.get('context_recall', 'N/A')} | "
               f"{r.get('completeness', 'N/A')} | {r.get('faithfulness_notes', '')[:50]} |\n")

    return md


# =============================================================================
# MAIN â€” Cháº¡y evaluation
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 4: Evaluation & Scorecard")
    print("=" * 60)

    # Kiá»ƒm tra test questions
    print(f"\nLoading test questions tá»«: {TEST_QUESTIONS_PATH}")
    try:
        with open(TEST_QUESTIONS_PATH, "r", encoding="utf-8") as f:
            test_questions = json.load(f)
        print(f"TÃ¬m tháº¥y {len(test_questions)} cÃ¢u há»i")

        # In preview
        for q in test_questions[:3]:
            print(f"  [{q['id']}] {q['question']} ({q['category']})")
        print("  ...")

    except FileNotFoundError:
        print("KhÃ´ng tÃ¬m tháº¥y file test_questions.json!")
        test_questions = []

    # --- Cháº¡y Baseline ---
    print("\n--- Cháº¡y Baseline ---")
    print("LÆ°u Ã½: Cáº§n hoÃ n thÃ nh Sprint 2 trÆ°á»›c khi cháº¡y scorecard!")
    try:
        baseline_results = run_scorecard(
            config=BASELINE_CONFIG,
            test_questions=test_questions,
            verbose=True,
        )

        # Save scorecard
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        baseline_md = generate_scorecard_summary(baseline_results, "baseline_dense")
        scorecard_path = RESULTS_DIR / "scorecard_baseline.md"
        scorecard_path.write_text(baseline_md, encoding="utf-8")
        print(f"\nScorecard lÆ°u táº¡i: {scorecard_path}")

    except NotImplementedError:
        print("Pipeline chÆ°a implement. HoÃ n thÃ nh Sprint 2 trÆ°á»›c.")
        baseline_results = []

    # --- Cháº¡y Variant (sau khi Sprint 3 hoÃ n thÃ nh) ---
    # TODO Sprint 4: Uncomment sau khi implement variant trong rag_answer.py
    print("\n--- Cháº¡y Variant ---")
    variant_results = run_scorecard(
        config=VARIANT_CONFIG,
        test_questions=test_questions,
        verbose=True,
    )
    variant_md = generate_scorecard_summary(variant_results, VARIANT_CONFIG["label"])
    (RESULTS_DIR / "scorecard_variant.md").write_text(variant_md, encoding="utf-8")

    # --- A/B Comparison ---
    # TODO Sprint 4: Uncomment sau khi cÃ³ cáº£ baseline vÃ  variant
    if baseline_results and variant_results:
        compare_ab(
            baseline_results,
            variant_results,
            output_csv="ab_comparison.csv"
        )

    # print("\n\nViá»‡c cáº§n lÃ m Sprint 4:")
    # print("  1. HoÃ n thÃ nh Sprint 2 + 3 trÆ°á»›c")
    # print("  2. Cháº¥m Ä‘iá»ƒm thá»§ cÃ´ng hoáº·c implement LLM-as-Judge trong score_* functions")
    # print("  3. Cháº¡y run_scorecard(BASELINE_CONFIG)")
    # print("  4. Cháº¡y run_scorecard(VARIANT_CONFIG)")
    # print("  5. Gá»i compare_ab() Ä‘á»ƒ tháº¥y delta")
    # print("  6. Cáº­p nháº­t docs/tuning-log.md vá»›i káº¿t quáº£ vÃ  nháº­n xÃ©t")

