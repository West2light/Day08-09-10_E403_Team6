# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** Nhóm 6  
**Ngày:** 14/4/2026  

> **Hướng dẫn:** So sánh Day 08 (single-agent RAG) với Day 09 (supervisor-worker).
> Phải có **số liệu thực tế** từ trace — không ghi ước đoán.
> Chạy cùng test questions cho cả hai nếu có thể.

---

## 1. Metrics Comparison

> Điền vào bảng sau. Lấy số liệu từ:
> - Day 08: chạy `python eval.py` từ Day 08 lab
> - Day 09: chạy `python eval_trace.py` từ lab này

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | 0.90 | 0.30 | -0.60 | D08: avg_faithfulness/5 (thang 1-5 → 0-1). D09: tính từ cosine similarity chunks + penalty. Hai cách tính khác nhau, delta chỉ mang tính tham khảo. |
| Avg latency (ms) | 1681.9 | 11319 | +9637 | D08: ước tính từ diff timestamp grading_run.json. D09: đo trực tiếp qua langgraph invoke. |
| Abstain rate (%) | 20% (2/10) | 43% (41/95) | +23% | D08: câu relevance=1 hoặc "không biết" trong abstain set (q09, q10). D09: câu trả lời có "không đủ thông tin" hoặc "không có trong tài liệu". |
| Multi-hop accuracy | 67% (2/3) | 100% (24/24) | +33% | D08: completeness≥3 hoặc abstain đúng trên q07/q09/q10. D09: route đúng với expected_route trên test_type multi_worker/multi_doc/temporal/multi_detail. Định nghĩa khác nhau. |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | |
| Debug time (estimate) | ~30 phút | ~10 phút | -20 phút | D08: phải đọc toàn bộ pipeline không có trace. D09: đọc trace → xác định ngay worker sai → test độc lập. |
| MCP tool usage | N/A | 32% (31/95) | N/A | D09 có thể gọi get_ticket_info, search_kb, check_access_permission qua MCP interface. |

> **Lưu ý:** Nếu không có Day 08 kết quả thực tế, ghi "N/A" và giải thích.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | 9/9 (100%) — faithfulness≥4 trên tất cả câu đơn (SLA, Refund, Access Control, IT Helpdesk, HR Policy) | 100% routing đúng trên test_type=single_worker (q01–q08, q10, q14) |
| Latency | ~1682 ms (ước tính) | ~8000–21000 ms (đo thực tế, vd: q01=20775ms, q14=8572ms) |
| Observation | Pipeline đơn giản, ít bước, nhanh | Phải qua supervisor → retrieval → (policy) → synthesis; thêm overhead LangGraph + OpenAI call |

**Kết luận:** Multi-agent KHÔNG cải thiện về accuracy cho câu đơn giản (cả hai đều đúng), nhưng latency cao hơn đáng kể (~5–12x). Đối với câu hỏi single-document không cần policy check, multi-agent không mang lại lợi ích rõ ràng so với overhead phát sinh.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | 2/3 (67%) — q07 đúng (completeness≥3), q09 đúng (abstain), q10 sai (không abstain đúng) | 24/24 (100%) — route đúng với expected_route trên tất cả câu multi_worker, multi_worker_multi_doc, temporal_scoping, multi_detail |
| Routing visible? | ✗ | ✓ |
| Observation | Single agent không phân biệt được câu cross-doc vs đơn giản — cùng một pipeline cho tất cả | Supervisor phân tách đúng: câu cross-doc (q13, q15) route policy_tool_worker + retrieval_worker; có route_reason rõ ràng trong trace |

**Kết luận:** Multi-agent cải thiện rõ rệt cho câu multi-hop. Supervisor routing cho phép phối hợp đúng worker theo loại câu hỏi, đồng thời trace cho thấy rõ lý do quyết định nếu cần debug.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | 2/10 (20%) — q09 (ERR-403-AUTH) và q10 (VIP refund) được định nghĩa là abstain cases | 41/95 (43%) câu trả lời chứa tín hiệu abstain; abstain_accuracy = 5/6 (83%) trên test_type=abstain |
| Hallucination cases | 1 — q10 (VIP refund không có trong docs, nhưng model không abstain đúng) | Có kiểm soát qua _should_abstain() và CẢNH BÁO block cho policy v3 cases |
| Observation | Không có cơ chế explicit abstain — model phụ thuộc vào faithfulness của LLM grader | D09: supervisor route ERR-403-AUTH → human_review (HITL triggered); synthesis.py có _should_abstain() cho financial penalty; policy_tool.py xử lý temporal scoping v3 |

**Kết luận:** Multi-agent có cơ chế abstain tường minh hơn (HITL node, _should_abstain, policy version gating), nhưng abstain_accuracy 83% cho thấy vẫn còn 1/6 câu abstain chưa đúng. Day 08 thiếu cơ chế explicit nên chỉ dựa vào LLM generation.

---

## 3. Debuggability Analysis

> Khi pipeline trả lời sai, mất bao lâu để tìm ra nguyên nhân?

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: ~30 phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic
  → Nếu retrieval sai → test retrieval_worker độc lập
  → Nếu synthesis sai → test synthesis_worker độc lập
Thời gian ước tính: ~10 phút
```

**Câu cụ thể nhóm đã debug:** Câu q02 (hoàn tiền đơn hàng 31/01/2026) — LLM ban đầu áp sai policy v4 (điều kiện 7 ngày) cho đơn hàng thuộc v3. Debug: đọc trace → thấy synthesis_worker nhận policy_applies=True thay vì None → nguyên nhân: policy_tool.py chưa parse được ngày → thêm logic temporal scoping + CẢNH BÁO block vào synthesis context. Thời gian tìm ra bug ~10 phút nhờ trace rõ ràng.

---

## 4. Extensibility Analysis

> Dễ extend thêm capability không?

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ — swap worker |

**Nhận xét:** Multi-agent architecture phân tách mỗi concern thành một worker riêng, cho phép sửa đổi có định hướng và kiểm tra độc lập mà không ảnh hưởng toàn hệ thống. Single agent tích hợp tất cả trong một pipeline nên mỗi thay đổi có thể gây side-effect không lường trước.

---

## 5. Cost & Latency Trade-off

> Multi-agent thường tốn nhiều LLM calls hơn. Nhóm đo được gì?

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query (retrieval_worker path) | 1 LLM call | 1 LLM call (synthesis GPT-4o-mini) + 1 embedding call |
| Complex query (policy_tool_worker path) | 1 LLM call | 1 LLM call (synthesis GPT-4o-mini) + 1 embedding call + 1 MCP tool call (mock, không tốn API) |
| MCP tool call | N/A | 0–2 MCP calls/query (get_ticket_info khi có "ticket"/"p1"/"jira"; search_kb khi chưa có chunks) |

**Nhận xét về cost-benefit:** Số LLM call thực tế giữa D08 và D09 tương đương (cùng 1 generation call/query). Chi phí tăng chủ yếu từ latency (overhead LangGraph state transitions, ~9637ms), không phải từ số API call. MCP tools hiện là mock in-process nên không phát sinh API cost thêm. Trade-off: latency cao hơn đổi lấy observability (trace), khả năng mở rộng (thêm worker/tool mà không sửa core), và HITL capability.

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. **Observability & debuggability:** Mỗi trace ghi rõ supervisor_route, route_reason, workers_called, mcp_tools_used → khi sai biết ngay bước nào lỗi, không cần đọc toàn bộ pipeline.
2. **Multi-hop và temporal scoping:** Supervisor phối hợp đúng worker theo loại câu hỏi; policy_tool_worker xử lý temporal scoping v3/v4 mà single agent không có cơ chế tương đương; multi_hop_accuracy tăng từ 67% → 100%.
3. **Khả năng mở rộng:** Thêm MCP tool hoặc worker mới mà không sửa core pipeline; có HITL node cho câu hỏi không đủ context (ERR-403-AUTH tự route human_review).

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. **Latency cao hơn ~6x:** Từ ~1682ms lên ~11319ms do overhead LangGraph state transitions và nhiều bước xử lý tuần tự. Với câu đơn giản, single agent nhanh hơn đáng kể mà accuracy tương đương.
2. **Avg confidence thấp hơn:** 0.30 vs 0.90 — do cách tính khác nhau (D09 dùng cosine similarity + penalty, D08 dùng faithfulness grader thang 1-5). Không phản ánh chất lượng thực sự kém hơn.

> **Khi nào KHÔNG nên dùng multi-agent?**

Khi tất cả câu hỏi đều đơn giản, single-document, không cần routing logic hay policy check — ví dụ FAQ lookup thuần túy. Chi phí overhead LangGraph + latency tăng ~6x không được bù đắp bởi lợi ích routing. Cũng không nên dùng khi latency là ưu tiên hàng đầu (real-time chat, SLA <2 giây).

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Thêm MCP tool thật (kết nối Jira API thật thay vì mock) và implement check_access_permission call trong policy_tool_worker để tự động tra cứu thay vì chỉ rule-based. Thêm caching layer cho embedding để giảm latency với câu hỏi lặp lại.
