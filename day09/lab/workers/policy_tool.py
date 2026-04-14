"""
workers/policy_tool.py — Policy & Tool Worker
Sprint 2+3: Kiểm tra policy dựa vào context, gọi MCP tools khi cần.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: context từ retrieval_worker
    - needs_tool: True nếu supervisor quyết định cần tool call

Output (vào AgentState):
    - policy_result: {"policy_applies", "policy_name", "exceptions_found", "source", "rule"}
    - mcp_tools_used: list of tool calls đã thực hiện
    - worker_io_log: log

Gọi độc lập để test:
    python workers/policy_tool.py
"""

import re
from datetime import datetime
from typing import Optional

WORKER_NAME = "policy_tool_worker"
POLICY_V4_CUTOFF = datetime(2026, 2, 1)


# ─────────────────────────────────────────────
# MCP Client — Sprint 3 Standard
# ─────────────────────────────────────────────

def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Gọi MCP tool.

    Sprint 3 Standard:
    - Import trực tiếp dispatch_tool từ mcp_server.py (mock in-process)

    Sprint 3 Advanced:
    - Có thể thay bằng HTTP client / MCP client thật sau
    """
    try:
        from mcp_server import dispatch_tool
        result = dispatch_tool(tool_name, tool_input)
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": result,
            "error": None,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": None,
            "error": {"code": "MCP_CALL_FAILED", "reason": str(e)},
            "timestamp": datetime.now().isoformat(),
        }


def _record_mcp_call(state: dict, mcp_result: dict) -> None:
    """
    Ghi log MCP theo cả schema cũ lẫn alias trace mới.
    """
    state.setdefault("mcp_tools_used", [])
    state.setdefault("mcp_tool_called", [])
    state.setdefault("mcp_result", [])

    state["mcp_tools_used"].append(mcp_result)
    state["mcp_tool_called"].append(mcp_result.get("tool"))

    if mcp_result.get("error") is None:
        state["mcp_result"].append(mcp_result.get("output"))
    else:
        state["mcp_result"].append(mcp_result)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _extract_order_date(text: str) -> Optional[datetime]:
    """
    Tìm ngày đơn hàng trong text.
    Hỗ trợ các format phổ biến:
      - 31/01/2026
      - 31-01-2026
      - 2026-01-31
    """
    if not text:
        return None

    patterns = [
        r"\b(\d{2}/\d{2}/\d{4})\b",
        r"\b(\d{2}-\d{2}-\d{4})\b",
        r"\b(\d{4}-\d{2}-\d{2})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue

        raw = match.group(1)
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue

    return None


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _has_activated_indicator(text: str) -> bool:
    """
    Chỉ coi là đã kích hoạt nếu có tín hiệu khẳng định rõ.
    Tránh bắt nhầm 'chưa kích hoạt'.
    """
    text = text.lower()

    negative_patterns = [
        "chưa kích hoạt",
        "chưa đăng ký",
        "chưa sử dụng",
        "not activated",
        "unused",
    ]
    if any(p in text for p in negative_patterns):
        # Có phủ định rõ ràng thì không coi là activated
        return False

    positive_patterns = [
        "đã kích hoạt",
        "đã đăng ký",
        "đã sử dụng",
        "already activated",
        "activated",
        "already registered",
        "already used",
    ]
    return any(p in text for p in positive_patterns)


# ─────────────────────────────────────────────
# Policy Analysis Logic
# ─────────────────────────────────────────────

def analyze_policy(task: str, chunks: list) -> dict:
    """
    Phân tích policy dựa trên context chunks.

    Standard implementation:
    - Rule-based check
    - Có xử lý exceptions chính
    - Có xử lý temporal scoping cho policy v3 / v4

    Lưu ý:
    - Nếu đơn hàng trước 01/02/2026 thì áp dụng v3
    - Vì docs hiện tại không có v3, worker không được kết luận chắc chắn
    """
    task = task or ""
    task_lower = task.lower()

    chunk_texts = [c.get("text", "") for c in chunks if isinstance(c, dict)]
    context_text = "\n".join(chunk_texts)
    context_lower = context_text.lower()

    combined_text = f"{task}\n{context_text}".strip()
    combined_lower = combined_text.lower()

    sources = list({c.get("source", "unknown") for c in chunks if isinstance(c, dict)})
    exceptions_found = []

    # ── 1) Temporal scoping: policy v3 nếu đơn hàng trước 01/02/2026 ──
    order_date = _extract_order_date(combined_text)
    if order_date and order_date < POLICY_V4_CUTOFF:
        return {
            "policy_applies": None,
            "policy_name": "refund_policy_v3",
            "exceptions_found": [],
            "source": sources,
            "policy_version_note": (
                f"Phát hiện đơn hàng ngày {order_date.strftime('%d/%m/%Y')} "
                "→ thuộc phạm vi policy v3 (trước 01/02/2026). "
                "Policy v3 không có trong bộ tài liệu hiện tại nên chưa thể kết luận chắc chắn."
            ),
            "needs_human_review": True,
            "explanation": (
                "Không đủ căn cứ kết luận vì đơn hàng thuộc policy v3, "
                "trong khi tài liệu hiện có chỉ phản ánh policy mới hơn."
            ),
        }

    # Nếu người dùng nêu mơ hồ 'trước 01/02' mà không parse được ngày cụ thể
    if "trước 01/02" in combined_lower or "trước 01/02/2026" in combined_lower:
        return {
            "policy_applies": None,
            "policy_name": "refund_policy_v3",
            "exceptions_found": [],
            "source": sources,
            "policy_version_note": (
                "Task cho biết đơn hàng trước 01/02/2026 → cần áp dụng policy v3, "
                "nhưng policy v3 không có trong tài liệu hiện tại."
            ),
            "needs_human_review": True,
            "explanation": (
                "Không đủ căn cứ kết luận vì thiếu policy v3 trong knowledge base hiện tại."
            ),
        }

    # ── 2) Rule-based exceptions cho policy v4 ──
    if "flash sale" in combined_lower:
        exceptions_found.append({
            "type": "flash_sale_exception",
            "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
            "source": "policy_refund_v4.txt",
        })

    if _contains_any(
        combined_lower,
        ["license key", "license", "subscription", "kỹ thuật số", "digital product"],
    ):
        exceptions_found.append({
            "type": "digital_product_exception",
            "rule": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3, chính sách v4).",
            "source": "policy_refund_v4.txt",
        })

    if _has_activated_indicator(combined_lower):
        exceptions_found.append({
            "type": "activated_exception",
            "rule": "Sản phẩm đã kích hoạt / đăng ký / sử dụng không được hoàn tiền (Điều 3, chính sách v4).",
            "source": "policy_refund_v4.txt",
        })

    policy_applies = len(exceptions_found) == 0

    explanation = "Analyzed via rule-based policy check."
    if policy_applies:
        explanation += " Không phát hiện exception rõ ràng trong task/context hiện tại."
    else:
        explanation += " Phát hiện exception nên policy hoàn tiền không áp dụng."

    return {
        "policy_applies": policy_applies,
        "policy_name": "refund_policy_v4",
        "exceptions_found": exceptions_found,
        "source": sources,
        "policy_version_note": "",
        "needs_human_review": False,
        "explanation": explanation,
    }


# ─────────────────────────────────────────────
# Worker Entry Point
# ─────────────────────────────────────────────

def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với policy_result và mcp_tools_used
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])
    state.setdefault("retrieved_sources", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "needs_tool": needs_tool,
        },
        "output": None,
        "error": None,
    }

    try:
        # Step 1: Nếu chưa có chunks và supervisor cho phép dùng tool → gọi MCP search_kb
        if not chunks and needs_tool:
            mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
            _record_mcp_call(state, mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP search_kb")

            if mcp_result.get("output") and mcp_result["output"].get("chunks"):
                chunks = mcp_result["output"]["chunks"]
                state["retrieved_chunks"] = chunks
                state["retrieved_sources"] = mcp_result["output"].get("sources", [])

        # Nếu state chưa có retrieved_sources thì tự suy ra từ chunks
        if not state.get("retrieved_sources") and chunks:
            state["retrieved_sources"] = list({
                c.get("source", "unknown") for c in chunks if isinstance(c, dict)
            })

        # Step 2: Phân tích policy
        policy_result = analyze_policy(task, chunks)
        state["policy_result"] = policy_result

        # Step 3: Nếu query liên quan ticket/P1/Jira thì lấy thêm ticket info qua MCP
        if needs_tool and any(kw in task.lower() for kw in ["ticket", "p1", "jira"]):
            mcp_result = _call_mcp_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
            _record_mcp_call(state, mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP get_ticket_info")

        worker_io["output"] = {
            "policy_applies": policy_result.get("policy_applies"),
            "policy_name": policy_result.get("policy_name"),
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "mcp_calls": len(state.get("mcp_tools_used", [])),
            "needs_human_review": policy_result.get("needs_human_review", False),
        }

        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result.get('policy_applies')}, "
            f"exceptions={len(policy_result.get('exceptions_found', []))}, "
            f"policy={policy_result.get('policy_name')}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
        state["policy_result"] = {
            "policy_applies": None,
            "policy_name": "unknown",
            "exceptions_found": [],
            "source": [],
            "policy_version_note": "",
            "needs_human_review": True,
            "explanation": f"Policy worker failed: {e}",
            "error": str(e),
        }
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Policy Tool Worker — Standalone Test")
    print("=" * 50)

    test_cases = [
        {
            "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
            "retrieved_chunks": [
                {
                    "text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền.",
                    "source": "policy_refund_v4.txt",
                    "score": 0.90,
                }
            ],
        },
        {
            "task": "Khách hàng muốn hoàn tiền license key đã kích hoạt.",
            "retrieved_chunks": [
                {
                    "text": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền.",
                    "source": "policy_refund_v4.txt",
                    "score": 0.88,
                }
            ],
        },
        {
            "task": "Khách hàng yêu cầu hoàn tiền trong 5 ngày, sản phẩm lỗi, chưa kích hoạt.",
            "retrieved_chunks": [
                {
                    "text": "Yêu cầu trong 7 ngày làm việc, sản phẩm lỗi nhà sản xuất, chưa dùng.",
                    "source": "policy_refund_v4.txt",
                    "score": 0.85,
                }
            ],
        },
        {
            "task": "Đơn hàng ngày 31/01/2026 yêu cầu hoàn tiền vì sản phẩm lỗi.",
            "retrieved_chunks": [
                {
                    "text": "Chính sách refund v4 áp dụng từ 01/02/2026.",
                    "source": "policy_refund_v4.txt",
                    "score": 0.80,
                }
            ],
        },
    ]

    for tc in test_cases:
        print(f"\n▶ Task: {tc['task'][:70]}...")
        result = run(tc.copy())
        pr = result.get("policy_result", {})

        print(f"  policy_applies: {pr.get('policy_applies')}")
        print(f"  policy_name   : {pr.get('policy_name')}")

        if pr.get("policy_version_note"):
            print(f"  version_note  : {pr.get('policy_version_note')}")

        if pr.get("exceptions_found"):
            for ex in pr["exceptions_found"]:
                print(f"  exception: {ex['type']} — {ex['rule'][:60]}...")

        print(f"  MCP calls: {len(result.get('mcp_tools_used', []))}")

    print("\n✅ policy_tool_worker test done.")