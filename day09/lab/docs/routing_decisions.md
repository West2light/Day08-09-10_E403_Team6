# Routing Decisions Log — Lab Day 09

**Nhóm:** Nhóm 6  
**Ngày:** 14/4/2026  

> **Hướng dẫn:** Ghi lại ít nhất **3 quyết định routing** thực tế từ trace của nhóm.
> Không ghi giả định — phải từ trace thật (`artifacts/traces/`).
> 
> Mỗi entry phải có: task đầu vào → worker được chọn → route_reason → kết quả thực tế.

---

## Routing Decision #1

**Task đầu vào:**
> SLA xử lý ticket P1 là bao lâu?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `SLA/ticket retrieval signal detected: p1, sla, ticket → route retrieval_worker | choose MCP=no`  
**MCP tools được gọi:** Không có  
**Workers called sequence:** retrieval_worker → synthesis_worker

**Kết quả thực tế:**
- final_answer (ngắn): SLA P1 — phản hồi 15 phút, resolution 4 giờ, escalate Senior Engineer sau 10 phút, Jira/Slack/#incident-p1/PagerDuty/hotline ext.9999
- confidence: 0.35
- Correct routing? Yes

**Nhận xét:** Routing đúng. Câu hỏi SLA đơn giản, chỉ cần tra cứu tài liệu, không cần policy check hay MCP tool. Retrieval lấy đúng chunk từ `support/sla-p1-2026.pdf` với score cao nhất 0.644. Answer đầy đủ gồm cả kênh liên lạc (PagerDuty, hotline ext.9999) nhờ top-k=5.

---

## Routing Decision #2

**Task đầu vào:**
> Store credit khi hoàn tiền có giá trị bao nhiêu so với tiền gốc?

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `policy/access signal detected: hoàn tiền, store credit → route policy_tool_worker (prefer MCP) | choose MCP=yes`  
**MCP tools được gọi:** Không có (MCP chỉ được gọi khi task có "ticket"/"p1"/"jira"; câu này không trigger)  
**Workers called sequence:** retrieval_worker → policy_tool_worker → synthesis_worker

**Kết quả thực tế:**
- final_answer (ngắn): Store credit có giá trị 110% so với số tiền gốc. Khách hàng chọn nhận thay vì hoàn tiền qua phương thức gốc.
- confidence: 0.34
- Correct routing? Yes

**Nhận xét:** Routing đúng — câu hỏi về policy hoàn tiền cần policy_tool_worker để kiểm tra exception. Policy_tool phát hiện 2 exceptions (flash_sale, digital_product) từ context chunk mặc dù task không đề cập — do keyword "license key" và "flash sale" xuất hiện trong retrieved chunks. Policy_applies=False nhưng synthesis vẫn trả lời đúng câu hỏi (store credit 110%) vì chunk [1] có score 0.78 chứa thông tin trực tiếp.

---

## Routing Decision #3

**Task đầu vào:**
> ERR-403-AUTH là lỗi gì và cách xử lý?

**Worker được chọn:** `human_review` (HITL triggered)  
**Route reason (từ trace):** `unknown error code without policy/SLA context → human review | choose MCP=no | human approved → retrieval`  
**MCP tools được gọi:** Không có  
**Workers called sequence:** human_review → retrieval_worker → synthesis_worker

**Kết quả thực tế:**
- final_answer (ngắn): "Không đủ thông tin trong tài liệu nội bộ để trả lời câu hỏi này."
- confidence: 0.15
- Correct routing? Yes

**Nhận xét:** Routing đúng theo design — regex `\berr-[a-z0-9-]+\b` phát hiện mã lỗi không rõ, không có policy/SLA keyword → route human_review, HITL triggered. Sau khi auto-approve (lab mode), retrieval_worker tìm không ra chunk liên quan (0 chunks) → synthesis abstain đúng. Đây là behavior mong muốn: thay vì hallucinate, hệ thống thừa nhận không đủ thông tin.

---

## Routing Decision #4 (tuỳ chọn — bonus)

**Task đầu vào:**
> Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời cho contractor để thực hiện emergency fix. Đồng thời cần notify stakeholders theo SLA. Nêu đủ cả hai quy trình.

**Worker được chọn:** `policy_tool_worker` (với risk_high=True, MCP get_ticket_info được gọi)  
**Route reason:** `policy/access signal detected: access, level 2 → route policy_tool_worker (prefer MCP) | risk_high signals: emergency, 2am | choose MCP=yes`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**

Câu q15 là multi_worker_multi_doc — yêu cầu **hai quy trình song song** từ hai tài liệu khác nhau (SLA từ `sla-p1-2026.pdf` + access control từ `access-control-sop.md`). Supervisor phải nhận diện cả hai signal (access/level 2 → policy; p1/2am → SLA + risk_high) trong một câu. Routing đúng (policy_tool_worker), MCP get_ticket_info được gọi đúng (vì có "P1"), retrieval lấy được chunks từ cả hai nguồn. Answer cuối đúng cả hai quy trình. Tuy nhiên, policy_tool_worker vẫn trả policy_applies=True không chính xác (câu hỏi không liên quan hoàn tiền) vì logic policy chỉ check refund exceptions — đây là limitation của rule-based policy analysis. Latency = 14934ms (cao nhất trong test set).

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 41 | 43% |
| policy_tool_worker | 54 | 56% |
| human_review | 6 | 6% |

> Lưu ý: Human_review sau đó redirect về retrieval_worker nên một câu có thể xuất hiện trong cả hai worker lists. Total = 95 traces (eval run).

### Routing Accuracy

> Trong số 15 câu test (test_questions.json), bao nhiêu câu supervisor route đúng với expected_route?

- Câu route đúng: 14 / 15 (theo expected_route trong test_questions.json)
- Câu route sai: q14 (nhân viên thử việc muốn làm remote) — expected: retrieval_worker, thực tế: policy_tool_worker (do keywords "probation", "thử việc", "remote" nằm trong policy_keywords). Đã sửa: có thể thêm "probation" vào retrieval_keywords hoặc tách rule riêng. Kết quả vẫn đúng vì synthesis worker lấy được chunk từ `hr/leave-policy-2026.pdf`.
- Câu trigger HITL: 6 / 95 traces — tất cả là câu ERR-403-AUTH (q09) hoặc câu có mã lỗi không rõ

### Lesson Learned về Routing

> Quyết định kỹ thuật quan trọng nhất nhóm đưa ra về routing logic là gì?

1. **Dùng keyword matching thay vì LLM classifier:** Nhanh, deterministic, dễ debug, không tốn API call thêm. Nhược điểm: bỏ sót câu có cùng intent nhưng diễn đạt khác từ. Với 15 test cases có context rõ ràng (IT Helpdesk nội bộ), keyword matching đủ tốt (routing accuracy 93%).
2. **Regex pattern cho unknown error code → human_review:** `\berr-[a-z0-9-]+\b` là heuristic đơn giản nhưng hiệu quả cho trường hợp abstain cần HITL. Không cần LLM để quyết định — tránh chicken-and-egg problem (cần LLM để quyết định có cần LLM không).

### Route Reason Quality

> Nhìn lại các `route_reason` trong trace — chúng có đủ thông tin để debug không?

Route reason hiện tại đủ thông tin để debug: ghi rõ keywords detected, worker được chọn, risk signals, và MCP decision. Ví dụ: `"policy/access signal detected: access, level 2 → route policy_tool_worker (prefer MCP) | risk_high signals: emergency, 2am | choose MCP=yes"`. Nếu muốn cải tiến, có thể thêm field `matched_keywords_count` và `confidence_score` cho routing decision để dễ tune threshold hơn.
