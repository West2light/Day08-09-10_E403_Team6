"""
workers/synthesis.py — Synthesis Worker
Sprint 2: Tổng hợp câu trả lời từ retrieved_chunks và policy_result.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: evidence từ retrieval_worker
    - policy_result: kết quả từ policy_tool_worker

Output (vào AgentState):
    - final_answer: câu trả lời cuối với citation
    - sources: danh sách nguồn tài liệu được cite
    - confidence: mức độ tin cậy (0.0 - 1.0)

Gọi độc lập để test:
    python workers/synthesis.py
"""

import os
from typing import Optional

WORKER_NAME = "synthesis_worker"

SYSTEM_PROMPT = """Bạn là trợ lý IT Helpdesk nội bộ.

Quy tắc nghiêm ngặt:
1. CHỈ trả lời dựa vào context được cung cấp. TUYỆT ĐỐI không dùng kiến thức ngoài hoặc suy diễn thêm.
2. Nếu POLICY RESULT có ghi "policy_applies: None" hoặc "policy_version_note" → PHẢI nêu rõ phiên bản chính sách không có trong tài liệu, KHÔNG kết luận được/không được, KHÔNG áp dụng thông tin từ phiên bản khác.
3. Nếu thông tin cụ thể được hỏi KHÔNG xuất hiện trong context → nói "Thông tin này không có trong tài liệu nội bộ hiện có." Không bịa số liệu, con số, điều kiện.
4. Nếu câu hỏi yêu cầu liệt kê nhiều chi tiết (ai, kênh nào, thời gian, điều kiện) → liệt kê ĐẦY ĐỦ tất cả chi tiết có trong context, không bỏ sót.
5. Với exception override: nếu có exception (Flash Sale, digital product...) → exception LUÔN thắng, dù sản phẩm lỗi hay trong thời hạn.
6. Kết luận phải RÕ RÀNG: "Được" / "Không được" / "Không thể kết luận (thiếu tài liệu phiên bản X)" — không mơ hồ.
7. Dùng citation dạng [1], [2] theo thứ tự evidence trong context.
"""


def _ordered_sources(chunks: list) -> list:
    """Lấy danh sách source theo thứ tự xuất hiện, không lặp."""
    sources = []
    seen = set()

    for chunk in chunks:
        source = chunk.get("source", "unknown")
        if source not in seen:
            seen.add(source)
            sources.append(source)

    return sources


def _call_llm(messages: list) -> Optional[str]:
    """
    Gọi LLM để tổng hợp câu trả lời.
    Trả về None nếu không gọi được model, để worker fallback sang rule-based synthesis.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,
                max_tokens=500,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()
        except Exception:
            pass

    gemini_key = os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            combined = "\n".join([m["content"] for m in messages])
            response = model.generate_content(combined)
            text = getattr(response, "text", None)
            if text and text.strip():
                return text.strip()
        except Exception:
            pass

    return None


def _build_context(chunks: list, policy_result: dict) -> str:
    """Xây dựng context string từ chunks và policy result."""
    parts = []

    # Nếu policy_applies=None (thiếu version), đặt cảnh báo LÊN ĐẦU để LLM không bị nhầm
    version_note = policy_result.get("policy_version_note") if policy_result else None
    policy_applies = policy_result.get("policy_applies") if policy_result else "N/A"
    if policy_result and policy_applies is None and version_note:
        parts.append(
            f"=== CẢNH BÁO QUAN TRỌNG ===\n"
            f"{version_note}\n"
            f"⚠️ EVIDENCE bên dưới thuộc policy phiên bản KHÁC — KHÔNG được dùng để kết luận cho câu hỏi này.\n"
            f"Kết luận bắt buộc: KHÔNG THỂ XÁC ĐỊNH vì thiếu tài liệu phiên bản áp dụng."
        )

    if chunks:
        parts.append("=== EVIDENCE ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            score = chunk.get("score", 0)
            parts.append(f"[{i}] Source: {source} | relevance={score:.2f}\n{text}")

    if policy_result:
        policy_lines = []

        if "policy_name" in policy_result:
            policy_lines.append(f"- policy_name: {policy_result.get('policy_name')}")

        if "policy_applies" in policy_result:
            policy_lines.append(f"- policy_applies: {policy_result.get('policy_applies')}")

        if version_note:
            policy_lines.append(f"- policy_version_note: {version_note}")

        if policy_result.get("needs_human_review") is True:
            policy_lines.append("- needs_human_review: True")

        if policy_result.get("exceptions_found"):
            policy_lines.append("- exceptions_found:")
            for ex in policy_result["exceptions_found"]:
                policy_lines.append(f"  * {ex.get('rule', '')}")

        if policy_lines:
            parts.append("=== POLICY RESULT ===")
            parts.extend(policy_lines)

    if not parts:
        return "(Không có context)"

    return "\n\n".join(parts)


_ABSTAIN_SIGNALS = [
    ("phạt", "tài chính"),
    ("penalty", "financial"),
    ("mức phạt",),
    ("fine",),
    ("compensation",),
    ("bồi thường",),
]

def _should_abstain(task: str, chunks: list) -> bool:
    """
    Phát hiện câu hỏi yêu cầu thông tin không có trong tài liệu.
    Trả về True nếu nên abstain.
    """
    task_lower = task.lower()
    for signals in _ABSTAIN_SIGNALS:
        if all(s in task_lower for s in signals):
            # Kiểm tra chunks có chứa thông tin trả lời không
            combined = " ".join(c.get("text", "").lower() for c in chunks)
            if not any(s in combined for s in signals):
                return True
    return False


def _fallback_answer(task: str, chunks: list, policy_result: dict) -> str:
    """
    Fallback không cần LLM:
    - Không hallucinate
    - Có citation [1], [2]
    - Ưu tiên policy_result nếu có
    """
    if not chunks and not policy_result:
        return "Không đủ thông tin trong tài liệu nội bộ để trả lời câu hỏi này."

    # Abstain nếu câu hỏi hỏi về thông tin không có trong tài liệu
    if _should_abstain(task, chunks):
        return "Thông tin này không có trong tài liệu nội bộ hiện có. Vui lòng liên hệ bộ phận liên quan để tra cứu."

    notes = []

    # Case 1: policy v3 / cần human review / chưa đủ căn cứ
    if policy_result:
        if policy_result.get("policy_applies") is None:
            note = policy_result.get("policy_version_note") or \
                   "Không đủ thông tin trong tài liệu nội bộ để kết luận chắc chắn."
            notes.append(note)

            if policy_result.get("needs_human_review"):
                notes.append("Cần human review hoặc tra cứu thêm policy tương ứng trước khi kết luận.")

            sources = policy_result.get("source", [])
            if sources:
                citations = " ".join(f"[{i+1}]" for i in range(min(len(sources), len(chunks) if chunks else len(sources))))
                if citations:
                    notes[-1] = notes[-1] + f" {citations}"

            return "\n".join(notes)

        # Case 2: policy không áp dụng vì có exception
        if policy_result.get("policy_applies") is False:
            exceptions = policy_result.get("exceptions_found", [])
            if exceptions:
                for ex in exceptions:
                    notes.append(f"Ngoại lệ áp dụng: {ex.get('rule', '')}")
            else:
                notes.append("Policy không áp dụng theo context hiện tại.")

            if chunks:
                first_source_cite = "[1]"
                notes.append(f"Kết luận: yêu cầu không thỏa điều kiện theo tài liệu hiện có. {first_source_cite}")
            else:
                notes.append("Kết luận: yêu cầu không thỏa điều kiện theo policy result hiện có.")

            return "\n".join(notes)

    # Case 3: có evidence bình thường → trả lời từ chunks, giữ đủ thông tin
    if chunks:
        answer_lines = []

        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "").strip()
            source = chunk.get("source", "unknown")
            if not text:
                continue
            # Giữ tối đa 600 ký tự mỗi chunk để không mất chi tiết quan trọng
            display_text = text.replace("\n", " ").strip()
            if len(display_text) > 600:
                display_text = display_text[:597].rstrip() + "..."

            if i == 1:
                answer_lines.append(f"Theo tài liệu nội bộ [{i}] ({source}): {display_text}")
            else:
                answer_lines.append(f"Bổ sung [{i}] ({source}): {display_text}")

        if not answer_lines:
            return "Không đủ thông tin trong tài liệu nội bộ để trả lời câu hỏi này."

        return "\n".join(answer_lines)

    return "Không đủ thông tin trong tài liệu nội bộ để trả lời câu hỏi này."


def _estimate_confidence(chunks: list, answer: str, policy_result: dict, used_llm: bool) -> float:
    """
    Ước tính confidence dựa vào:
    - Có evidence hay không
    - Có cần human review không
    - Có exception không
    - Có phải abstain không
    - Có dùng được LLM hay đang fallback
    """
    if not chunks:
        return 0.15

    answer_lower = answer.lower()

    if "không đủ thông tin" in answer_lower or "không có trong tài liệu" in answer_lower:
        return 0.3

    if policy_result.get("needs_human_review") or policy_result.get("policy_applies") is None:
        return 0.35

    avg_score = sum(c.get("score", 0) for c in chunks) / max(len(chunks), 1)

    exception_penalty = 0.05 * len(policy_result.get("exceptions_found", []))
    fallback_penalty = 0.08 if not used_llm else 0.0

    confidence = avg_score - exception_penalty - fallback_penalty

    return round(max(0.1, min(0.95, confidence)), 2)


def synthesize(task: str, chunks: list, policy_result: dict) -> dict:
    """
    Tổng hợp câu trả lời từ chunks và policy context.

    Returns:
        {"answer": str, "sources": list, "confidence": float}
    """
    context = _build_context(chunks, policy_result)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Câu hỏi: {task}

{context}

Yêu cầu trả lời:
- Liệt kê ĐẦY ĐỦ mọi chi tiết liên quan có trong context (kênh thông báo, tên người phê duyệt, điều kiện, thời gian...).
- Nếu policy result có "policy_applies: None" hoặc "policy_version_note" về version khác → PHẢI nêu rõ không thể kết luận vì thiếu tài liệu phiên bản đó, KHÔNG áp dụng thông tin từ policy khác.
- Nếu thông tin được hỏi KHÔNG có trong context → nói "Thông tin này không có trong tài liệu nội bộ hiện có."
- Với access control: nêu rõ từng level có bao nhiêu người phê duyệt và ai, phân biệt quy trình thường vs emergency bypass.
- Kết luận rõ ràng. Citation [1], [2] bắt buộc.""",
        },
    ]

    llm_answer = _call_llm(messages)
    used_llm = llm_answer is not None

    if llm_answer:
        answer = llm_answer
    else:
        answer = _fallback_answer(task, chunks, policy_result)

    sources = _ordered_sources(chunks)
    confidence = _estimate_confidence(chunks, answer, policy_result, used_llm)

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
    }


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "has_policy": bool(policy_result),
        },
        "output": None,
        "error": None,
    }

    try:
        result = synthesize(task, chunks, policy_result)
        state["final_answer"] = result["answer"]
        state["sources"] = result["sources"]
        state["confidence"] = result["confidence"]

        worker_io["output"] = {
            "answer_length": len(result["answer"]),
            "sources": result["sources"],
            "confidence": result["confidence"],
        }
        state["history"].append(
            f"[{WORKER_NAME}] answer generated, confidence={result['confidence']}, "
            f"sources={result['sources']}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
        state["final_answer"] = f"Không thể tổng hợp câu trả lời do lỗi synthesis: {e}"
        state["sources"] = _ordered_sources(chunks)
        state["confidence"] = 0.0
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Synthesis Worker — Standalone Test")
    print("=" * 50)

    test_state = {
        "task": "SLA ticket P1 là bao lâu?",
        "retrieved_chunks": [
            {
                "text": "Ticket P1: Phản hồi ban đầu 15 phút kể từ khi ticket được tạo. Xử lý và khắc phục 4 giờ. Escalation: tự động escalate lên Senior Engineer nếu không có phản hồi trong 10 phút.",
                "source": "sla_p1_2026.txt",
                "score": 0.92,
            }
        ],
        "policy_result": {},
    }

    result = run(test_state.copy())
    print(f"\nAnswer:\n{result['final_answer']}")
    print(f"\nSources: {result['sources']}")
    print(f"Confidence: {result['confidence']}")

    print("\n--- Test 2: Exception case ---")
    test_state2 = {
        "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì lỗi nhà sản xuất.",
        "retrieved_chunks": [
            {
                "text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền theo Điều 3 chính sách v4.",
                "source": "policy_refund_v4.txt",
                "score": 0.88,
            }
        ],
        "policy_result": {
            "policy_applies": False,
            "policy_name": "refund_policy_v4",
            "exceptions_found": [
                {"type": "flash_sale_exception", "rule": "Flash Sale không được hoàn tiền."}
            ],
            "source": ["policy_refund_v4.txt"],
            "policy_version_note": "",
            "needs_human_review": False,
        },
    }
    result2 = run(test_state2.copy())
    print(f"\nAnswer:\n{result2['final_answer']}")
    print(f"Confidence: {result2['confidence']}")

    print("\n--- Test 3: Missing historical policy ---")
    test_state3 = {
        "task": "Đơn hàng ngày 31/01/2026 có được hoàn tiền không?",
        "retrieved_chunks": [
            {
                "text": "Chính sách refund v4 áp dụng từ 01/02/2026.",
                "source": "policy_refund_v4.txt",
                "score": 0.80,
            }
        ],
        "policy_result": {
            "policy_applies": None,
            "policy_name": "refund_policy_v3",
            "exceptions_found": [],
            "source": ["policy_refund_v4.txt"],
            "policy_version_note": "Đơn hàng trước 01/02/2026 áp dụng policy v3, nhưng policy v3 không có trong tài liệu hiện tại.",
            "needs_human_review": True,
        },
    }
    result3 = run(test_state3.copy())
    print(f"\nAnswer:\n{result3['final_answer']}")
    print(f"Confidence: {result3['confidence']}")

    print("\n✅ synthesis_worker test done.")