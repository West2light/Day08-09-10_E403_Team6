# System Architecture — Lab Day 09

**Nhóm:** Nhóm 6  
**Ngày:** 14/4/2026  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

> Mô tả ngắn hệ thống của nhóm: chọn pattern gì, gồm những thành phần nào.

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**

Câu hỏi trong domain IT Helpdesk có hai loại rõ ràng: câu cần tra cứu tài liệu (SLA, FAQ) và câu cần kiểm tra policy + gọi tool ngoài (hoàn tiền, cấp quyền). Single agent không phân biệt được hai loại này và không thể gọi tool có điều kiện. Supervisor-Worker cho phép định tuyến tường minh, mỗi worker có thể test độc lập, và dễ thêm worker/tool mới mà không sửa core pipeline.

---

## 2. Sơ đồ Pipeline

> Vẽ sơ đồ pipeline dưới dạng text, Mermaid diagram, hoặc ASCII art.
> Yêu cầu tối thiểu: thể hiện rõ luồng từ input → supervisor → workers → output.

**Ví dụ (ASCII art):**
```
User Request
     │
     ▼
┌──────────────┐
│  Supervisor  │  ← route_reason, risk_high, needs_tool
└──────┬───────┘
       │
   [route_decision]
       │
  ┌────┴────────────────────┐
  │                         │
  ▼                         ▼
Retrieval Worker     Policy Tool Worker
  (evidence)           (policy check + MCP)
  │                         │
  └─────────┬───────────────┘
            │
            ▼
      Synthesis Worker
        (answer + cite)
            │
            ▼
         Output
```

**Sơ đồ thực tế của nhóm:**

```
User Request (task: str)
     │
     ▼
┌─────────────────────────────────────────────────┐
│  Supervisor (graph.py::supervisor_node)          │
│  - Keyword matching → supervisor_route           │
│  - Đặt risk_high, needs_tool, route_reason       │
└──────────────────┬──────────────────────────────┘
                   │
          [route_decision]
                   │
     ┌─────────────┼──────────────┐
     ▼             ▼              ▼
retrieval_    policy_tool_    human_review
 worker        worker          (HITL node)
                                   │
                                   ▼
                           retrieval_worker
                                   │
     ◄─────────────────────────────┘
     │
     │  [post_retrieval_decision]
     │
     ├──→ policy_tool_worker (nếu supervisor_route=policy)
     │         │
     │         ▼
     └──→ synthesis_worker
               │
               ▼
        final_answer + confidence + sources
```

> Lưu ý: Tất cả câu đều đi qua retrieval_worker trước khi synthesis. Policy_tool_worker được gọi thêm khi route=policy_tool_worker (sau retrieval). Human_review redirect về retrieval sau khi approve.

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích task, quyết định route sang worker nào, đánh giá risk, xác định cần MCP tool không |
| **Input** | task (str) — câu hỏi đầu vào từ user |
| **Output** | supervisor_route, route_reason, risk_high, needs_tool |
| **Routing logic** | Keyword matching: policy_keywords (hoàn tiền, refund, access, level 2/3/4...) → policy_tool_worker; retrieval_keywords (p1, sla, ticket, password...) → retrieval_worker; unknown ERR-XXX code không có policy/SLA context → human_review; risk_keywords (emergency, 2am, khẩn cấp) → đặt risk_high=True |
| **HITL condition** | Khi task chứa mã lỗi không rõ (`err-[a-z0-9-]+`) mà không có policy/SLA keyword → route human_review |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Embed query, query ChromaDB, trả về top-k chunks với text, source, score, metadata |
| **Embedding model** | `paraphrase-multilingual-MiniLM-L12-v2` (Sentence Transformers, multilingual, offline) |
| **Top-k** | 5 (DEFAULT_TOP_K) |
| **Stateless?** | Yes — không giữ state giữa các lần gọi, nhận input từ AgentState và trả về state mới |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích policy từ retrieved chunks, phát hiện exceptions, xử lý temporal scoping (v3/v4), gọi MCP tools khi cần |
| **MCP tools gọi** | `get_ticket_info` (khi task có "ticket"/"p1"/"jira"); `search_kb` (khi chưa có chunks và needs_tool=True) |
| **Exception cases xử lý** | flash_sale_exception (đơn Flash Sale không hoàn tiền); digital_product_exception (license key, subscription không hoàn tiền); activated_exception (sản phẩm đã kích hoạt không hoàn tiền); temporal_scoping (đơn trước 01/02/2026 → policy v3 → policy_applies=None, needs_human_review=True) |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | GPT-4o-mini |
| **Temperature** | 0.1 (deterministic, ít hallucination) |
| **Grounding strategy** | Context = EVIDENCE (numbered chunks với source và score) + POLICY RESULT; Strict system prompt 7 rules cấm suy diễn ngoài context; CẢNH BÁO block lên đầu context khi policy_applies=None (v3 case); citation [1][2] bắt buộc |
| **Abstain condition** | `_should_abstain()`: phát hiện câu hỏi về financial penalty/phạt tài chính khi chunks không chứa thông tin đó; policy_applies=None từ policy_tool → tự động không kết luận; empty chunks → confidence=0.15, trả "không đủ thông tin" |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| search_kb | query (str), top_k (int=3) | chunks (list), sources (list), total_found (int) — delegate sang ChromaDB qua retrieval.py |
| get_ticket_info | ticket_id (str, vd: "P1-LATEST", "IT-1234") | ticket_id, priority, status, assignee, created_at, sla_deadline, escalated, notifications_sent |
| check_access_permission | access_level (int: 1/2/3), requester_role (str), is_emergency (bool=False) | can_grant, required_approvers, approver_count, emergency_override, notes |
| create_ticket | priority (P1/P2/P3/P4), title (str), description (str) | ticket_id (mock), url, created_at — MOCK, không tạo thật |

---

## 4. Shared State Schema

> Liệt kê các fields trong AgentState và ý nghĩa của từng field.

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| task | str | Câu hỏi đầu vào | supervisor đọc |
| supervisor_route | str | Worker được chọn (retrieval_worker / policy_tool_worker / human_review) | supervisor ghi |
| route_reason | str | Lý do route, keyword detected, MCP decision | supervisor ghi |
| risk_high | bool | True khi có risk keyword (emergency, 2am, khẩn cấp) | supervisor ghi |
| needs_tool | bool | True khi supervisor quyết định cần MCP tool | supervisor ghi, policy_tool đọc |
| hitl_triggered | bool | True khi human_review node được kích hoạt | human_review ghi |
| retrieved_chunks | list | Evidence từ retrieval (text, source, score, metadata) | retrieval ghi, policy_tool/synthesis đọc |
| retrieved_sources | list | Danh sách source filenames duy nhất | retrieval ghi |
| policy_result | dict | Kết quả kiểm tra policy (policy_applies, exceptions_found, version_note...) | policy_tool ghi, synthesis đọc |
| mcp_tools_used | list | Tool calls đã thực hiện (tool, input, output, timestamp) | policy_tool ghi |
| final_answer | str | Câu trả lời cuối | synthesis ghi |
| confidence | float | Mức tin cậy (0.0–1.0) dựa vào avg chunk score và penalty | synthesis ghi |
| sources | list | Sources được cite trong final_answer | synthesis ghi |
| history | list | Log từng bước theo thứ tự thực thi | tất cả workers append |
| workers_called | list | Tên các workers đã được gọi (theo thứ tự) | tất cả workers append |
| latency_ms | int | Tổng thời gian xử lý (ms) | graph.py ghi sau invoke |
| run_id | str | ID định danh run (run_YYYYMMDD_HHMMSS) | make_initial_state ghi |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — không rõ lỗi ở đâu | Dễ hơn — test từng worker độc lập |
| Thêm capability mới | Phải sửa toàn prompt | Thêm worker/MCP tool riêng |
| Routing visibility | Không có | Có route_reason trong trace |
| Temporal policy handling | Không có — LLM tự xử lý hoặc hallucinate | Policy_tool_worker phát hiện ngày đơn → trả policy_applies=None → synthesis không kết luận |
| HITL / human escalation | Không có cơ chế | Human_review node với auto-approve trong lab; có thể thay bằng interrupt_before thật |

**Nhóm điền thêm quan sát từ thực tế lab:**

Trong quá trình debug, việc đọc trace JSON trực tiếp (history, route_reason, workers_called) giúp xác định ngay bước nào sai mà không cần re-run pipeline. Cụ thể: bug LLM áp sai policy v4 cho đơn hàng v3 được phát hiện qua trace trong <5 phút, trong khi nếu là single agent sẽ phải đọc toàn bộ log RAG. Tuy nhiên, latency ~11 giây/câu là hạn chế thực tế đáng kể cho production use.

---

## 6. Giới hạn và điểm cần cải tiến

> Nhóm mô tả những điểm hạn chế của kiến trúc hiện tại.

1. **Latency cao (~11 giây/câu):** Overhead từ LangGraph state transitions + OpenAI API call + Sentence Transformer embedding. Chưa có caching; mỗi query chạy lại embedding và LLM từ đầu.
2. **Policy_tool_worker chỉ dựa rule-based:** Phát hiện exception bằng keyword matching trong task text — dễ bỏ sót nếu user diễn đạt khác (vd: "Đã activate" thay vì "đã kích hoạt"). Chưa dùng check_access_permission MCP tool trong thực tế.
3. **Confidence score không chuẩn hóa tốt:** avg_confidence=0.30 trong khi chất lượng câu trả lời thực tế cao hơn nhiều — do công thức tính từ cosine similarity chunks không phản ánh đúng chất lượng generation. Cần calibration riêng.
