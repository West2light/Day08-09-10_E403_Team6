# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** [TÊN ĐẦY ĐỦ CỦA BẠN]
**Mã số sinh viên:** [MSSV CỦA BẠN]
**Vai trò trong nhóm:** Worker Owner
**Ngày nộp:** 14/4/2026
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- `workers/retrieval.py` — Retrieval Worker: Dense retrieval từ ChromaDB, trả về chunks + sources cho graph
- `workers/policy_tool.py` — Policy Tool Worker: Kiểm tra policy, phát hiện exception cases, gọi MCP tools
- `workers/synthesis.py` — Synthesis Worker: Tổng hợp câu trả lời từ evidence + policy result, gọi LLM
- `contracts/worker_contracts.yaml` — Định nghĩa I/O contract cho cả 3 workers và supervisor

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Tôi phụ thuộc vào `graph.py` (Vương Hoàng Giang) để biết `AgentState` truyền những field gì sang worker — đặc biệt là `task`, `retrieved_chunks`, `needs_tool`. Ngược lại, `mcp_server.py` (Dương Quang Đông) phải export đúng hàm `dispatch_tool()` để `policy_tool.py` gọi qua `_call_mcp_tool()` được. Output của tôi — `final_answer`, `sources`, `confidence` — được Nguyễn Lê Trung dùng trong `eval_trace.py` để tính metrics.

**Bằng chứng:**

Commit của tôi (`padung25`) thêm 3 file workers: `policy_tool.py`, `synthesis.py`, `retrieval.py`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Trong `policy_tool.py`, tôi chọn dùng **rule-based keyword matching** thay vì gọi LLM để phát hiện exception cases (Flash Sale, digital product, activated product).

**Lý do:**

Ban đầu có hai lựa chọn: (1) gọi LLM để phân tích câu hỏi và tự xác định exception, hoặc (2) dùng keyword matching thuần Python. Tôi chọn cách 2 vì:
- **Deterministic**: Mỗi lần chạy cùng input cho cùng kết quả → giúp trace dễ debug hơn
- **Không tốn API call**: policy_tool_worker không tiêu thêm token để phân tích task  
- **Trace rõ ràng**: `exceptions_found` ghi rõ `type` và `rule` của từng exception → grader thấy ngay được lý do

Trade-off tôi chấp nhận: nếu user diễn đạt khác đi (ví dụ "chương trình giảm sốc" thay vì "Flash Sale") thì bị bỏ sót. Tuy nhiên với bộ test questions đã biết trước, keyword matching đủ để cover.

**Bằng chứng từ code (`workers/policy_tool.py`):**

```python
# Dùng keyword matching để phát hiện exception
if "flash sale" in combined_lower:
    exceptions_found.append({
        "type": "flash_sale_exception",
        "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
        "source": "policy_refund_v4.txt",
    })

if _contains_any(combined_lower, ["license key", "license", "subscription", "kỹ thuật số", "digital product"]):
    exceptions_found.append({
        "type": "digital_product_exception",
        "rule": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3, chính sách v4).",
        "source": "policy_refund_v4.txt",
    })
```

Ngoài ra tôi cũng implement **temporal scoping**: nếu phát hiện đơn hàng trước `01/02/2026` qua regex date parsing → `policy_applies=None`, `needs_human_review=True`, không kết luận chắc chắn. Đây là xử lý câu gq02 trong grading questions.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** `synthesis_worker` trong batch đầu trả về câu trả lời bị cắt cụt ở dấu `...` do `_fallback_answer()` giới hạn 600 ký tự mỗi chunk và không có LLM gọi được — output thiếu toàn bộ phần quy trình SLA notification cho câu q15 (multi-hop).

**Symptom từ trace cũ:**

```
"final_answer": "Theo tài liệu nội bộ, thông tin phù hợp nhất là: Escalation chỉ
 áp dụng khi cần thay đổi quyền hệ thống ngoài quy trình thông thường...
 [1]\nThông tin bổ sung: Bước 1: Nhân viên tạo Access Request ticket trên
 Jira (project IT-ACCESS). Bước 2: Line Manager phê duyệt yêu cầu trong
 1 ngày làm việc. Bước 3: IT Admin kiểm tra compliance và... [2]"
"confidence": 0.47
"workers_called": ["retrieval_worker", "policy_tool_worker", "synthesis_worker"]
```

→ Câu trả lời bị cắt ở `...`, thiếu toàn bộ quy trình SLA notification (Bước 2–5 từ `sla-p1-2026.pdf`). Chỉ có 3 chunks retrieved thay vì 5.

**Root cause:** `DEFAULT_TOP_K=3` ở `retrieval.py` quá thấp cho câu multi-hop cần cross-doc reasoning. Đồng thời `_fallback_answer()` không gọi được LLM (thiếu API key lúc đó) và bị display_text giới hạn.

**Cách sửa:** Tăng `DEFAULT_TOP_K` từ 3 lên 5, và fix `SYSTEM_PROMPT` để yêu cầu LLM liệt kê đầy đủ cả hai quy trình thành 2 section rõ ràng.

**Bằng chứng trước/sau từ trace:**

```
# TRƯỚC:
"retrieved_chunks": 3 chunks  → thiếu SLA quy trình P1
"confidence": 0.47
"final_answer": bị cắt ở "..." — thiếu section notify stakeholders
"latency_ms": 8033ms

# SAU:
"retrieved_chunks": 5 chunks  → đủ cả access-control + SLA
"confidence": 0.52
"final_answer": 2 section đầy đủ (Emergency Escalation + SLA P1 notification)
"latency_ms": 14934–15162ms  # chấp nhận được; đánh đổi lấy completeness
```

Sau fix, câu q15 có đủ 2 phần được hỏi: quy trình cấp quyền tạm thời **và** quy trình thông báo SLA, khớp với yêu cầu của grading rubric.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Tôi thiết kế `synthesis.py` với **dual-mode**: nếu có API key thì gọi GPT-4o-mini hoặc Gemini 1.5 Flash, nếu không có thì fallback sang rule-based synthesis không hallucinate. Điều này giúp pipeline chạy được ngay cả khi không có API key — quan trọng cho môi trường thử nghiệm. Hàm `_estimate_confidence()` cũng tự tính confidence dựa trên cosine similarity từ ChromaDB chứ không hard-code.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

`SYSTEM_PROMPT` trong `synthesis.py` còn chưa tốt — dẫn đến việc worker đôi khi trả về câu trả lời không đúng với yêu cầu, khiến cả team mất thời gian debug. Cụ thể, trace cũ cho thấy câu q01 (SLA P1) bị latency đột biến lên **136,227ms** do LLM bị prompt mơ hồ, phải retry nhiều lần. Tôi đã phải chỉnh lại prompt để yêu cầu output structured hơn và kết quả latency giảm xuống ~20,000ms ở batch cuối.

**Nhóm phụ thuộc vào tôi ở đâu?**

Toàn bộ pipeline phụ thuộc vào output của `synthesis_worker` — nếu worker này crash thì `final_answer` không có và `eval_trace.py` không ghi được kết quả hoàn chỉnh.

**Phần tôi phụ thuộc vào thành viên khác:**

`policy_tool.py` gọi `dispatch_tool()` từ `mcp_server.py`. Nếu MCP server chưa implement thì `needs_tool=True` sẽ raise exception và worker phải fallback.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ cải thiện `retrieval_worker` để hỗ trợ **hybrid retrieval** — kết hợp dense (ChromaDB embedding) với sparse (BM25 keyword). Lý do cụ thể từ trace: câu q15 và gq09 hỏi về cả SLA escalation lẫn access control emergency — hai chủ đề dùng thuật ngữ khác nhau. Trace batch đầu chứng minh dense-only chỉ lấy được **3 chunks**, bỏ sót quy trình SLA P1 notification. Sau khi tăng `top_k=5` thì đủ 5 chunks, nhưng hybrid retrieval sẽ cải thiện thêm precision mà không cần tăng `top_k` thêm nữa.
