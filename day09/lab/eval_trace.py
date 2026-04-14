"""
eval_trace.py — Trace Evaluation & Comparison
Sprint 4: Chạy pipeline với test questions, phân tích trace, so sánh single vs multi.

Chạy:
    python eval_trace.py                  # Chạy 15 test questions
    python eval_trace.py --grading        # Chạy grading questions (sau 17:00)
    python eval_trace.py --analyze        # Phân tích trace đã có
    python eval_trace.py --compare        # So sánh single vs multi

Outputs:
    artifacts/traces/          — trace của từng câu hỏi
    artifacts/grading_run.jsonl — log câu hỏi chấm điểm
    artifacts/eval_report.json  — báo cáo tổng kết
"""

import json
import os
import sys
import argparse
from datetime import datetime
from typing import Optional

# Import graph
sys.path.insert(0, os.path.dirname(__file__))
from graph import run_graph, save_trace


# ─────────────────────────────────────────────
# 1. Run Pipeline on Test Questions
# ─────────────────────────────────────────────

def run_test_questions(questions_file: str = "data/test_questions.json") -> list:
    """
    Chạy pipeline với danh sách câu hỏi, lưu trace từng câu.

    Returns:
        list of (question, result) tuples
    """
    with open(questions_file, encoding="utf-8") as f:
        questions = json.load(f)

    print(f"\n📋 Running {len(questions)} test questions from {questions_file}")
    print("=" * 60)

    results = []
    for i, q in enumerate(questions, 1):
        question_text = q["question"]
        q_id = q.get("id", f"q{i:02d}")

        print(f"[{i:02d}/{len(questions)}] {q_id}: {question_text[:65]}...")

        try:
            result = run_graph(question_text)
            result["question_id"] = q_id

            # Save individual trace
            trace_file = save_trace(result, f"artifacts/traces")
            print(f"  ✓ route={result.get('supervisor_route', '?')}, "
                  f"conf={result.get('confidence', 0):.2f}, "
                  f"{result.get('latency_ms', 0)}ms")

            results.append({
                "id": q_id,
                "question": question_text,
                "expected_answer": q.get("expected_answer", ""),
                "expected_sources": q.get("expected_sources", []),
                "difficulty": q.get("difficulty", "unknown"),
                "category": q.get("category", "unknown"),
                "result": result,
            })

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results.append({
                "id": q_id,
                "question": question_text,
                "error": str(e),
                "result": None,
            })

    print(f"\n✅ Done. {sum(1 for r in results if r.get('result'))} / {len(results)} succeeded.")
    return results


# ─────────────────────────────────────────────
# 2. Run Grading Questions (Sprint 4)
# ─────────────────────────────────────────────

def run_grading_questions(questions_file: str = "data/grading_questions.json") -> str:
    """
    Chạy pipeline với grading questions và lưu JSONL log.
    Dùng cho chấm điểm nhóm (chạy sau khi grading_questions.json được public lúc 17:00).

    Returns:
        path tới grading_run.jsonl
    """
    if not os.path.exists(questions_file):
        print(f"❌ {questions_file} chưa được public (sau 17:00 mới có).")
        return ""

    with open(questions_file, encoding="utf-8") as f:
        questions = json.load(f)

    os.makedirs("artifacts", exist_ok=True)
    output_file = "artifacts/grading_run.jsonl"

    print(f"\n🎯 Running GRADING questions — {len(questions)} câu")
    print(f"   Output → {output_file}")
    print("=" * 60)

    with open(output_file, "w", encoding="utf-8") as out:
        for i, q in enumerate(questions, 1):
            q_id = q.get("id", f"gq{i:02d}")
            question_text = q["question"]
            print(f"[{i:02d}/{len(questions)}] {q_id}: {question_text[:65]}...")

            try:
                result = run_graph(question_text)
                record = {
                    "id": q_id,
                    "question": question_text,
                    "answer": result.get("final_answer", "PIPELINE_ERROR: no answer"),
                    "sources": result.get("retrieved_sources", []),
                    "supervisor_route": result.get("supervisor_route", ""),
                    "route_reason": result.get("route_reason", ""),
                    "workers_called": result.get("workers_called", []),
                    "mcp_tools_used": [t.get("tool") for t in result.get("mcp_tools_used", [])],
                    "confidence": result.get("confidence", 0.0),
                    "hitl_triggered": result.get("hitl_triggered", False),
                    "latency_ms": result.get("latency_ms"),
                    "timestamp": datetime.now().isoformat(),
                }
                print(f"  ✓ route={record['supervisor_route']}, conf={record['confidence']:.2f}")
            except Exception as e:
                record = {
                    "id": q_id,
                    "question": question_text,
                    "answer": f"PIPELINE_ERROR: {e}",
                    "sources": [],
                    "supervisor_route": "error",
                    "route_reason": str(e),
                    "workers_called": [],
                    "mcp_tools_used": [],
                    "confidence": 0.0,
                    "hitl_triggered": False,
                    "latency_ms": None,
                    "timestamp": datetime.now().isoformat(),
                }
                print(f"  ✗ ERROR: {e}")

            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n✅ Grading log saved → {output_file}")
    return output_file


# ─────────────────────────────────────────────
# 3. Analyze Traces
# ─────────────────────────────────────────────

def analyze_traces(traces_dir: str = "artifacts/traces") -> dict:
    """
    Đọc tất cả trace files và tính metrics tổng hợp.

    Metrics:
    - routing_distribution: % câu đi vào mỗi worker
    - avg_confidence: confidence trung bình
    - avg_latency_ms: latency trung bình
    - mcp_usage_rate: % câu có MCP tool call
    - hitl_rate: % câu trigger HITL
    - abstain_rate: % câu trả về "không đủ thông tin"
    - multi_hop_accuracy: % câu multi-hop (test_type multi_worker/temporal_scoping) route đúng
    - source_coverage: các tài liệu nào được dùng nhiều nhất

    Returns:
        dict of metrics
    """
    if not os.path.exists(traces_dir):
        print(f"⚠️  {traces_dir} không tồn tại. Chạy run_test_questions() trước.")
        return {}

    trace_files = [f for f in os.listdir(traces_dir) if f.endswith(".json")]
    if not trace_files:
        print(f"⚠️  Không có trace files trong {traces_dir}.")
        return {}

    traces = []
    for fname in trace_files:
        with open(os.path.join(traces_dir, fname), encoding="utf-8") as f:
            traces.append(json.load(f))

    # Load test_questions để biết test_type và expected_route của từng câu
    test_q_path = os.path.join(os.path.dirname(__file__), "data", "test_questions.json")
    test_q_map = {}   # id -> question metadata
    if os.path.exists(test_q_path):
        with open(test_q_path, encoding="utf-8") as f:
            for q in json.load(f):
                test_q_map[q["id"]] = q

    # Compute metrics
    routing_counts = {}
    confidences = []
    latencies = []
    mcp_calls = 0
    hitl_triggers = 0
    source_counts = {}
    abstain_count = 0

    # Multi-hop: test_type thuộc các loại cần cross-doc reasoning
    MULTIHOP_TYPES = {"multi_worker", "multi_worker_multi_doc", "temporal_scoping", "multi_detail"}
    multihop_correct = 0
    multihop_total = 0

    # Abstain: câu hỏi không có thông tin trong docs
    ABSTAIN_TYPES = {"abstain"}
    abstain_correct = 0
    abstain_total = 0

    for t in traces:
        route = t.get("supervisor_route", "unknown")
        routing_counts[route] = routing_counts.get(route, 0) + 1

        conf = t.get("confidence", 0)
        if conf:
            confidences.append(conf)

        lat = t.get("latency_ms")
        if lat:
            latencies.append(lat)

        if t.get("mcp_tools_used"):
            mcp_calls += 1

        if t.get("hitl_triggered"):
            hitl_triggers += 1

        for src in t.get("retrieved_sources", []):
            source_counts[src] = source_counts.get(src, 0) + 1

        # Abstain rate: answer chứa "không đủ thông tin" hoặc "không có trong tài liệu"
        answer = (t.get("final_answer") or "").lower()
        if "không đủ thông tin" in answer or "không có trong tài liệu" in answer:
            abstain_count += 1

        # Multi-hop accuracy và abstain accuracy dựa theo test_questions metadata
        qid = t.get("question_id", "")
        q_meta = test_q_map.get(qid, {})
        test_type = q_meta.get("test_type", "")
        expected_route = q_meta.get("expected_route", "")

        if test_type in MULTIHOP_TYPES:
            multihop_total += 1
            # Coi là "đúng" nếu route khớp expected_route
            if expected_route and route == expected_route:
                multihop_correct += 1

        if test_type in ABSTAIN_TYPES:
            abstain_total += 1
            # Coi là "đúng" nếu model abstain
            if "không đủ thông tin" in answer or "không có trong tài liệu" in answer:
                abstain_correct += 1

    total = len(traces)

    multihop_acc = (
        f"{multihop_correct}/{multihop_total} ({100*multihop_correct//multihop_total}%)"
        if multihop_total else "N/A (không có trace multi-hop)"
    )
    abstain_acc = (
        f"{abstain_correct}/{abstain_total} ({100*abstain_correct//abstain_total}%)"
        if abstain_total else "N/A"
    )

    metrics = {
        "total_traces": total,
        "routing_distribution": {k: f"{v}/{total} ({100*v//total}%)" for k, v in routing_counts.items()},
        "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        "mcp_usage_rate": f"{mcp_calls}/{total} ({100*mcp_calls//total}%)" if total else "0%",
        "hitl_rate": f"{hitl_triggers}/{total} ({100*hitl_triggers//total}%)" if total else "0%",
        "abstain_rate": f"{abstain_count}/{total} ({100*abstain_count//total}%)" if total else "0%",
        "multi_hop_accuracy": multihop_acc,
        "abstain_accuracy": abstain_acc,
        "top_sources": sorted(source_counts.items(), key=lambda x: -x[1])[:5],
    }

    return metrics


# ─────────────────────────────────────────────
# 4. Compare Single vs Multi Agent
# ─────────────────────────────────────────────

def compare_single_vs_multi(
    multi_traces_dir: str = "artifacts/traces",
    day08_results_file: Optional[str] = None,
) -> dict:
    """
    So sánh Day 08 (single agent RAG) vs Day 09 (multi-agent).

    Day 08 metrics được load từ:
        ../../day08/lab/results/day08_metrics.json   (tạo bởi eval_metrics_day08.py)
    Hoặc truyền qua tham số day08_results_file.

    Returns:
        dict của comparison metrics
    """
    multi_metrics = analyze_traces(multi_traces_dir)

    # Fallback mặc định nếu không tìm thấy file
    day08_baseline = {
        "total_questions": 10,
        "avg_confidence": None,
        "avg_latency_ms": None,
        "abstain_rate": "N/A",
        "multi_hop_accuracy": "N/A",
    }

    # Tìm file metrics Day 08 — thử theo thứ tự ưu tiên
    candidates = []
    if day08_results_file:
        candidates.append(day08_results_file)
    candidates += [
        os.path.join(os.path.dirname(__file__), "../../day08/lab/results/day08_metrics.json"),
        os.path.join(os.path.dirname(__file__), "../../../day08/lab/results/day08_metrics.json"),
    ]

    loaded_path = None
    for candidate in candidates:
        norm = os.path.normpath(candidate)
        if os.path.exists(norm):
            with open(norm, encoding="utf-8") as f:
                raw = json.load(f)
            # Lấy các trường cần thiết từ file
            day08_baseline = {
                "total_questions": raw.get("total_questions", 10),
                "avg_confidence": raw.get("avg_confidence"),
                "avg_latency_ms": raw.get("avg_latency_ms"),
                "abstain_rate": raw.get("abstain_rate", "N/A"),
                "multi_hop_accuracy": raw.get("multi_hop_accuracy", "N/A"),
                # Thêm scorecard đầy đủ nếu có
                "scorecard": raw.get("baseline_dense", {}),
            }
            loaded_path = norm
            break

    # Tính delta latency và confidence nếu có đủ dữ liệu
    d09_conf = multi_metrics.get("avg_confidence")
    d08_conf = day08_baseline.get("avg_confidence")
    conf_delta = (
        f"{d09_conf - d08_conf:+.3f}" if (d09_conf is not None and d08_conf is not None) else "N/A"
    )

    d09_lat = multi_metrics.get("avg_latency_ms")
    d08_lat = day08_baseline.get("avg_latency_ms")
    lat_delta = (
        f"{d09_lat - d08_lat:+.0f} ms" if (d09_lat is not None and d08_lat is not None) else "N/A"
    )

    comparison = {
        "generated_at": datetime.now().isoformat(),
        "day08_single_agent": day08_baseline,
        "day09_multi_agent": multi_metrics,
        "analysis": {
            "routing_visibility": "Day 09 có route_reason cho từng câu → dễ debug hơn Day 08",
            "latency_delta": lat_delta,
            "confidence_delta": conf_delta,
            "debuggability": "Multi-agent: có thể test từng worker độc lập. Single-agent: không thể.",
            "mcp_benefit": "Day 09 có thể extend capability qua MCP không cần sửa core. Day 08 phải hard-code.",
            "day08_metrics_source": loaded_path or "không tìm thấy — chạy day08/lab/eval_metrics_day08.py",
        },
    }

    return comparison


# ─────────────────────────────────────────────
# 5. Save Eval Report
# ─────────────────────────────────────────────

def save_eval_report(comparison: dict) -> str:
    """Lưu báo cáo eval tổng kết ra file JSON."""
    os.makedirs("artifacts", exist_ok=True)
    output_file = "artifacts/eval_report.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    return output_file


# ─────────────────────────────────────────────
# 6. CLI Entry Point
# ─────────────────────────────────────────────

def print_metrics(metrics: dict):
    """Print metrics đẹp."""
    if not metrics:
        return
    print("\n📊 Trace Analysis:")
    for k, v in metrics.items():
        if isinstance(v, list):
            print(f"  {k}:")
            for item in v:
                print(f"    • {item}")
        elif isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Day 09 Lab — Trace Evaluation")
    parser.add_argument("--grading", action="store_true", help="Run grading questions")
    parser.add_argument("--analyze", action="store_true", help="Analyze existing traces")
    parser.add_argument("--compare", action="store_true", help="Compare single vs multi")
    parser.add_argument("--test-file", default="data/test_questions.json", help="Test questions file")
    args = parser.parse_args()

    if args.grading:
        # Chạy grading questions
        log_file = run_grading_questions()
        if log_file:
            print(f"\n✅ Grading log: {log_file}")
            print("   Nộp file này trước 18:00!")

    elif args.analyze:
        # Phân tích traces
        metrics = analyze_traces()
        print_metrics(metrics)

    elif args.compare:
        # So sánh single vs multi
        comparison = compare_single_vs_multi()
        report_file = save_eval_report(comparison)
        print(f"\n📊 Comparison report saved → {report_file}")
        print("\n=== Day 08 vs Day 09 ===")
        for k, v in comparison.get("analysis", {}).items():
            print(f"  {k}: {v}")

    else:
        # Default: chạy test questions
        results = run_test_questions(args.test_file)

        # Phân tích trace
        metrics = analyze_traces()
        print_metrics(metrics)

        # Lưu báo cáo
        comparison = compare_single_vs_multi()
        report_file = save_eval_report(comparison)
        print(f"\n📄 Eval report → {report_file}")
        print("\n✅ Sprint 4 complete!")
        print("   Next: Điền docs/ templates và viết reports/")
