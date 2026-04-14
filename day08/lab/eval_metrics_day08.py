"""
eval_metrics_day08.py — Tính metrics Day 08 để so sánh với Day 09
==================================================================
Script chỉ ĐỌC kết quả đã có (ab_comparison.csv, logs/grading_run.json),
KHÔNG chạy lại pipeline hay sửa bất kỳ file nào khác.

Output: results/day08_metrics.json
  Dùng bởi Day 09 eval_trace.py → compare_single_vs_multi()

Chạy:
    python eval_metrics_day08.py
"""

import csv
import json
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
LOGS_DIR = Path(__file__).parent / "logs"
AB_CSV = RESULTS_DIR / "ab_comparison.csv"
GRADING_JSON = LOGS_DIR / "grading_run.json"
OUTPUT_JSON = RESULTS_DIR / "day08_metrics.json"


# =============================================================================
# 1. Đọc ab_comparison.csv — lấy scores và timestamps
# =============================================================================

def load_ab_csv(path: Path) -> tuple[list[dict], list[dict]]:
    """Đọc CSV, tách baseline và variant rows."""
    baseline, variant = [], []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("config_label") == "baseline_dense":
                baseline.append(row)
            elif row.get("config_label") == "variant_hybrid":
                variant.append(row)
    return baseline, variant


def avg(values: list) -> float | None:
    """Tính trung bình, bỏ qua None và empty string."""
    nums = []
    for v in values:
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            pass
    return round(sum(nums) / len(nums), 3) if nums else None


# =============================================================================
# 2. Tính confidence tương đương (normalize faithfulness 1-5 → 0-1)
# =============================================================================

def compute_confidence(rows: list[dict]) -> float | None:
    """
    Day 08 không có confidence 0-1.
    Dùng trung bình faithfulness/5 làm proxy để so sánh với Day 09.
    """
    scores = [row.get("faithfulness") for row in rows]
    a = avg(scores)
    return round(a / 5, 3) if a is not None else None


# =============================================================================
# 3. Tính abstain rate
# q09 (ERR-403-AUTH) và q10 (VIP refund) là abstain cases theo test_questions.json
# =============================================================================

ABSTAIN_IDS = {"q09", "q10"}   # category "Insufficient Context" + hard VIP case

def compute_abstain_rate(rows: list[dict]) -> str:
    """
    Đếm số câu model trả lời "Tôi không biết" hoặc relevance=1.
    """
    abstain_count = 0
    total = len(rows)
    for row in rows:
        qid = row.get("id", "")
        relevance = row.get("relevance", "")
        answer = row.get("answer", "").lower()
        # Câu thuộc abstain set HOẶC relevance=1 (không trả lời được)
        if qid in ABSTAIN_IDS or relevance == "1" or "không biết" in answer:
            abstain_count += 1
    return f"{abstain_count}/{total} ({round(abstain_count/total*100)}%)" if total else "0/0"


# =============================================================================
# 4. Tính latency từ grading_run.json (timestamps liên tiếp)
# =============================================================================

def compute_latency_from_grading(path: Path) -> float | None:
    """
    Tính avg latency (ms) dựa vào diff timestamp giữa các câu trong grading_run.json.
    Đây là ước tính vì Day 08 không log latency trực tiếp.
    """
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    if len(records) < 2:
        return None

    deltas = []
    for i in range(1, len(records)):
        try:
            t1 = datetime.fromisoformat(records[i - 1]["timestamp"])
            t2 = datetime.fromisoformat(records[i]["timestamp"])
            delta_ms = (t2 - t1).total_seconds() * 1000
            if 0 < delta_ms < 60_000:   # bỏ outlier > 1 phút
                deltas.append(delta_ms)
        except (KeyError, ValueError):
            pass
    return round(sum(deltas) / len(deltas), 1) if deltas else None


# =============================================================================
# 5. Multi-hop accuracy
# Câu multi-hop: q07 (tên cũ → tên mới), q09, q10 (cross-doc/context)
# Đánh giá dựa vào context_recall + completeness >= 3
# =============================================================================

MULTIHOP_IDS = {"q07", "q09", "q10"}

def compute_multihop_accuracy(rows: list[dict]) -> str:
    """
    Multi-hop = câu hỏi khó cần suy luận cross-doc hoặc context thiếu.
    Coi là "đúng" nếu completeness >= 3 HOẶC câu hỏi abstain đúng (relevant=1 + abstain case).
    """
    multihop_rows = [r for r in rows if r.get("id") in MULTIHOP_IDS]
    if not multihop_rows:
        return "N/A"

    correct = 0
    for r in multihop_rows:
        qid = r.get("id", "")
        completeness = r.get("completeness", "")
        relevance = r.get("relevance", "")
        answer = r.get("answer", "").lower()
        try:
            comp_score = float(completeness)
        except (TypeError, ValueError):
            comp_score = 0

        # Abstain đúng: câu cần abstain và model trả "không biết" hoặc relevance=1
        if qid in ABSTAIN_IDS and (relevance == "1" or "không biết" in answer):
            correct += 1
        # Trả lời đúng: completeness >= 3
        elif comp_score >= 3:
            correct += 1

    total = len(multihop_rows)
    return f"{correct}/{total} ({round(correct/total*100)}%)"


# =============================================================================
# 6. Per-category accuracy (faithfulness >= 4 = "đúng")
# =============================================================================

def compute_category_accuracy(rows: list[dict]) -> dict:
    by_cat: dict[str, list] = {}
    for r in rows:
        cat = r.get("category", "unknown")
        by_cat.setdefault(cat, []).append(r)

    result = {}
    for cat, cat_rows in by_cat.items():
        correct = sum(1 for r in cat_rows
                      if r.get("faithfulness") and float(r["faithfulness"]) >= 4)
        result[cat] = f"{correct}/{len(cat_rows)}"
    return result


# =============================================================================
# 7. Main — tổng hợp và xuất JSON
# =============================================================================

def main():
    print("=" * 60)
    print("eval_metrics_day08.py — Tính metrics Day 08")
    print("=" * 60)

    if not AB_CSV.exists():
        print(f"Không tìm thấy {AB_CSV}. Chạy eval.py trước.")
        return

    baseline_rows, variant_rows = load_ab_csv(AB_CSV)
    print(f"Đọc ab_comparison.csv: {len(baseline_rows)} baseline rows, {len(variant_rows)} variant rows")

    # --- Baseline metrics ---
    b_faith    = avg([r.get("faithfulness") for r in baseline_rows])
    b_relevance = avg([r.get("relevance") for r in baseline_rows])
    b_recall   = avg([r.get("context_recall") for r in baseline_rows
                      if r.get("context_recall") not in (None, "", "None")])
    b_complete = avg([r.get("completeness") for r in baseline_rows])
    b_conf     = compute_confidence(baseline_rows)
    b_abstain  = compute_abstain_rate(baseline_rows)
    b_multihop = compute_multihop_accuracy(baseline_rows)
    b_latency  = compute_latency_from_grading(GRADING_JSON)
    b_cat      = compute_category_accuracy(baseline_rows)

    # --- Variant metrics ---
    v_faith    = avg([r.get("faithfulness") for r in variant_rows])
    v_relevance = avg([r.get("relevance") for r in variant_rows])
    v_recall   = avg([r.get("context_recall") for r in variant_rows
                      if r.get("context_recall") not in (None, "", "None")])
    v_complete = avg([r.get("completeness") for r in variant_rows])
    v_conf     = compute_confidence(variant_rows)
    v_cat      = compute_category_accuracy(variant_rows)

    metrics = {
        "generated_at": datetime.now().isoformat(),
        "source_files": {
            "ab_comparison_csv": str(AB_CSV),
            "grading_run_json": str(GRADING_JSON) if GRADING_JSON.exists() else None,
        },
        "note": (
            "avg_confidence = avg_faithfulness/5 (proxy, thang gốc Day08 là 1-5). "
            "avg_latency_ms ước tính từ diff timestamp grading_run.json. "
            "multi_hop_accuracy tính trên q07/q09/q10."
        ),

        # Metrics cho compare_single_vs_multi() trong Day 09
        "total_questions": len(baseline_rows),
        "avg_confidence": b_conf,
        "avg_latency_ms": b_latency,
        "abstain_rate": b_abstain,
        "multi_hop_accuracy": b_multihop,

        # Scorecard đầy đủ (thang 1-5)
        "baseline_dense": {
            "avg_faithfulness": b_faith,
            "avg_relevance": b_relevance,
            "avg_context_recall": b_recall,
            "avg_completeness": b_complete,
            "avg_confidence_proxy": b_conf,
            "abstain_rate": b_abstain,
            "multi_hop_accuracy": b_multihop,
            "avg_latency_ms_estimated": b_latency,
            "accuracy_by_category": b_cat,
        },
        "variant_hybrid": {
            "avg_faithfulness": v_faith,
            "avg_relevance": v_relevance,
            "avg_context_recall": v_recall,
            "avg_completeness": v_complete,
            "avg_confidence_proxy": v_conf,
            "abstain_rate": compute_abstain_rate(variant_rows),
            "multi_hop_accuracy": compute_multihop_accuracy(variant_rows),
            "accuracy_by_category": v_cat,
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print(f"\nOutput: {OUTPUT_JSON}")
    print(f"\n--- Baseline Dense ---")
    print(f"  avg_confidence (proxy) : {b_conf}")
    print(f"  avg_latency_ms (est.)  : {b_latency} ms")
    print(f"  abstain_rate           : {b_abstain}")
    print(f"  multi_hop_accuracy     : {b_multihop}")
    print(f"  avg_faithfulness       : {b_faith}/5")
    print(f"  avg_relevance          : {b_relevance}/5")
    print(f"  avg_context_recall     : {b_recall}/5")
    print(f"  avg_completeness       : {b_complete}/5")
    print(f"\n--- Variant Hybrid ---")
    print(f"  avg_faithfulness       : {v_faith}/5")
    print(f"  avg_relevance          : {v_relevance}/5")
    print(f"  avg_context_recall     : {v_recall}/5")
    print(f"  avg_completeness       : {v_complete}/5")
    print(f"\nDone.")


if __name__ == "__main__":
    main()
