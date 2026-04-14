# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Nhóm 6  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Vương Hoàng Giang | Supervisor Owner | gvuonghoang123@gmail.com |
| Phạm Anh Dũng | Worker Owner | panhdung2511@gmail.com |
| Dương Quang Đông | MCP Owner | quangdong010203@gmail.com |
| Nguyễn Lê Trung | Trace & Docs Owner | nguyenletrung2002@gmail.com |

**Ngày nộp:** 14/4/2026  
**Repo:** [Day08-09-10_E403_Team6](https://github.com/West2light/Day08-09-10_E403_Team6/tree/main/day09)    
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Hướng dẫn nộp group report:**
> 
> - File này nộp tại: `reports/group_report.md`
> - Deadline: Được phép commit **sau 18:00** (xem SCORING.md)
> - Tập trung vào **quyết định kỹ thuật cấp nhóm** — không trùng lặp với individual reports
> - Phải có **bằng chứng từ code/trace** — không mô tả chung chung
> - Mỗi mục phải có ít nhất 1 ví dụ cụ thể từ code hoặc trace thực tế của nhóm

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

> Mô tả ngắn gọn hệ thống nhóm: bao nhiêu workers, routing logic hoạt động thế nào,
> MCP tools nào được tích hợp. Dùng kết quả từ `docs/system_architecture.md`.

**Hệ thống tổng quan:**

Nhóm xây dựng hệ thống gồm 4 thành phần chính: (1) **Supervisor** phân tích câu hỏi và quyết định chuyển cho worker nào xử lý; (2) **Retrieval Worker** tìm kiếm tài liệu liên quan trong ChromaDB; (3) **Policy Tool Worker** kiểm tra các điều kiện chính sách, phát hiện ngoại lệ và gọi MCP tool khi cần; (4) **Synthesis Worker** tổng hợp câu trả lời cuối qua GPT-4o-mini chỉ dựa trên thông tin đã tìm được. Ngoài ra có thêm **Human Review node** cho các câu hỏi có mã lỗi không rõ — hệ thống sẽ tự đánh dấu cần xem lại thay vì tự đoán. Mỗi lần chạy đều xuất ra file trace JSON ghi lại toàn bộ quá trình xử lý.

**Routing logic cốt lõi:**

Supervisor dùng **keyword matching** để phân loại câu hỏi — nhanh và không tốn thêm API call. Các từ khóa liên quan chính sách (hoàn tiền, refund, cấp quyền, level 2/3...) → chuyển cho `policy_tool_worker`; từ khóa liên quan tra cứu (p1, sla, ticket, mật khẩu...) → `retrieval_worker`; câu có mã lỗi không rõ (dạng ERR-XXX) → `human_review`. Nếu câu có từ khóa rủi ro cao (emergency, 2am, khẩn cấp) thì hệ thống đánh dấu thêm để xử lý cẩn thận hơn. Mọi câu đều tìm kiếm tài liệu trước, sau đó mới kiểm tra policy hoặc tổng hợp câu trả lời.

**MCP tools đã tích hợp:**

- `search_kb`: Tìm kiếm tài liệu trong Knowledge Base, dùng khi cần tra cứu thêm ngoài kết quả retrieval ban đầu.
- `get_ticket_info`: Tra cứu thông tin ticket từ hệ thống Jira (mock). Được gọi tự động khi câu hỏi đề cập đến ticket P1. Ví dụ: trace gq09 ghi `"mcp_tools_used": ["get_ticket_info"]` — tool trả về trạng thái ticket, deadline SLA, và các kênh đã gửi thông báo.
- `check_access_permission`: Kiểm tra điều kiện cấp quyền theo từng level (1/2/3), kèm danh sách người cần phê duyệt. Đã implement nhưng chưa được gọi tự động trong routing hiện tại.
- `create_ticket`: Tạo ticket mới (mock, không tạo thật trong lab).

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

> Chọn **1 quyết định thiết kế** mà nhóm thảo luận và đánh đổi nhiều nhất.
> Phải có: (a) vấn đề gặp phải, (b) các phương án cân nhắc, (c) lý do chọn phương án đã chọn.

**Quyết định:** Cách xử lý khi đơn hàng thuộc chính sách cũ (v3) nhưng tài liệu hiện có chỉ có chính sách mới (v4).

**Bối cảnh vấn đề:**

Câu gq02 hỏi về đơn hàng đặt ngày 31/01/2026 — trước ngày chính sách v4 có hiệu lực (01/02/2026). Nếu pipeline không nhận ra điều này, AI sẽ tự áp các điều kiện của v4 (7 ngày, lỗi nhà sản xuất...) vào đơn hàng thuộc v3 — tức là đưa ra kết luận sai dựa trên tài liệu không phù hợp.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Để AI tự nhận ra từ nội dung context | Không cần code thêm | AI dễ bị ảnh hưởng bởi tài liệu v4 đang có và kết luận sai |
| Tự động đọc ngày đơn, nếu thuộc v3 thì báo "không đủ tài liệu" | Chắc chắn, không phụ thuộc AI | Cần viết thêm code đọc ngày |
| Bổ sung tài liệu v3 vào hệ thống | Giải quyết triệt để | Không có tài liệu v3 trong phạm vi lab |

**Phương án đã chọn và lý do:**

Chọn phương án 2: worker tự đọc ngày trong câu hỏi, nếu phát hiện đơn trước 01/02/2026 thì đánh dấu "không đủ căn cứ kết luận" và truyền tín hiệu đó sang bước tổng hợp. Bước tổng hợp nhận được tín hiệu này sẽ không đưa ra kết luận, thay vào đó giải thích lý do. Cách này đảm bảo AI không tự bịa đặt.

**Bằng chứng từ trace/code:**

```
# policy_tool.py — đọc ngày đơn hàng
order_date = _extract_order_date(combined_text)  # tìm thấy: 31/01/2026
if order_date < POLICY_V4_CUTOFF:               # trước 01/02/2026
    return {"policy_applies": None, ...}         # báo: không đủ tài liệu

# Kết quả câu gq02:
# "Chính sách áp dụng là v3, nhưng tài liệu hiện có chỉ có v4.
#  Kết luận: Không thể kết luận (thiếu tài liệu phiên bản v3)."
# → Đúng 10/10 điểm theo grading_criteria
```

---

## 3. Kết quả grading questions (150–200 từ)

> Sau khi chạy pipeline với grading_questions.json (public lúc 17:00):
> - Nhóm đạt bao nhiêu điểm raw?
> - Câu nào pipeline xử lý tốt nhất?
> - Câu nào pipeline fail hoặc partial?

**Tổng điểm raw ước tính:** 80 / 96

**Bảng chấm điểm ước tính:**

| ID | Điểm tối đa | Ước tính | Lý do |
|----|------------|----------|-------------------|
| gq01 | 10 | 7 | Đúng Slack + email + escalation 10 phút + Senior Engineer. **Thiếu PagerDuty** (không nêu kênh thứ 3). -3đ. |
| gq02 | 10 | 10 | Đúng hoàn toàn: nhận ra v3, nêu rõ tài liệu hiện có chỉ có v4, kết luận "Không thể kết luận (thiếu tài liệu v3)", không bịa nội dung v3. |
| gq03 | 10 | 7 | Đúng 3 người (Line Manager, IT Admin, IT Security). Tuy nhiên đề cập thêm "emergency bypass với Tech Lead" gây nhầm lẫn — Level 3 KHÔNG có emergency bypass theo SOP. -3đ. |
| gq04 | 6 | 6 | Đúng hoàn toàn: 110%, giải thích thêm 10% bonus so với hoàn tiền gốc, có citation [1] từ `policy/refund-v4.pdf`. |
| gq05 | 8 | 8 | Đúng hoàn toàn: tự động escalate lên Senior Engineer sau 10 phút không phản hồi, không nêu sai đối tượng hay thời gian. |
| gq06 | 8 | 8 | Đúng hoàn toàn: kết luận "Không được", nêu phải qua probation period, tối đa 2 ngày/tuần, Team Lead phê duyệt qua HR Portal. |
| gq07 | 10 | 10 | Đúng hoàn toàn: "Thông tin này không có trong tài liệu nội bộ hiện có." Không bịa số liệu phạt. `_should_abstain()` hoạt động đúng. |
| gq08 | 8 | 8 | Đúng hoàn toàn: đổi mật khẩu mỗi 90 ngày, cảnh báo trước 7 ngày, cite `helpdesk-faq.md`. |
| gq09 | 16 | 11 | SLA P1: đúng Slack + email, escalation 10 phút → Senior Engineer. **Thiếu PagerDuty** (-2đ). Level 2 access: đúng có emergency bypass, đúng điều kiện Tech Lead phê duyệt, **nhưng không phân biệt rõ "Line Manager + IT Admin on-call" vs quy trình thường, không nêu "không cần IT Security"** (-3đ). 2 workers được gọi đúng (policy_tool_worker + retrieval_worker). |
| gq10 | 10 | 5 | Kết luận đúng "Không được". Nêu đúng Flash Sale là ngoại lệ. **Tuy nhiên trình bày lẫn lộn: đề cập cả "điều kiện hoàn tiền thông thường" (7 ngày, lỗi nhà sản xuất) trước khi kết luận exception** — dễ gây nhầm rằng lỗi nhà sản xuất được hoàn tiền. Không cite rõ `policy_refund_v4.txt`. -5đ. |

**Câu pipeline xử lý tốt nhất:**
- **gq02** và **gq07**: Cả hai đều test anti-hallucination. gq02 nhận diện đúng temporal scoping → abstain đúng. gq07 phát hiện đúng câu hỏi về tài chính không có trong tài liệu → trả lời 1 câu ngắn gọn, không bịa.

**Câu pipeline fail hoặc partial:**
- **gq01 / gq09**: Thiếu PagerDuty trong danh sách kênh thông báo. Root cause: retrieval lấy đúng chunk nhưng synthesis không liệt kê đủ 3 kênh từ "Phần 4: Công cụ và kênh liên lạc" — do system prompt chưa ép buộc đủ mạnh phần liệt kê kênh.
- **gq10**: LLM trình bày cả điều kiện thông thường lẫn exception trong cùng câu trả lời — gây nhầm lẫn. Root cause: policy_tool trả `policy_applies=False` nhưng synthesis vẫn include evidence điều kiện thông thường từ chunks, không ưu tiên exception override ngay từ đầu.

**Câu gq07 (abstain):** Pipeline xử lý đúng: supervisor route `retrieval_worker`, retrieval không tìm thấy thông tin về financial penalty, `_should_abstain()` trong synthesis phát hiện signal ("phạt", "tài chính") không có trong chunk content → trả "Thông tin này không có trong tài liệu nội bộ hiện có." Không HITL triggered vì không có pattern ERR-XXX.

**Câu gq09 (multi-hop khó nhất):** Trace ghi đúng 2 workers: `workers_called: ["retrieval_worker", "policy_tool_worker", "synthesis_worker"]`. MCP `get_ticket_info` được gọi do task có "P1". Supervisor route đúng `policy_tool_worker` với `risk_high=True` (phát hiện "emergency", "2am"). Kết quả partial: SLA đúng nhưng Level 2 access thiếu chi tiết phân biệt emergency bypass.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

> Dựa vào `docs/single_vs_multi_comparison.md` — trích kết quả thực tế.

**Metric thay đổi rõ nhất (có số liệu):**

Câu hỏi phức tạp cần nhiều bước xử lý (multi-hop accuracy) tăng từ **67% → 100%**, và khả năng nhận biết câu không có thông tin để trả lời (abstain accuracy) đạt **83%**. Đây là lợi thế rõ nhất của multi-agent: mỗi loại câu hỏi được xử lý bởi đúng worker phù hợp. Đổi lại, thời gian xử lý tăng từ **~1.7 giây lên ~11 giây** — lâu hơn khoảng 6–7 lần.

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

Chỉ số "độ tin cậy" (confidence) giảm từ 0.90 xuống 0.30, nhưng câu trả lời thực tế không hề tệ hơn — thậm chí tốt hơn ở câu phức tạp. Lý do: Day 08 và Day 09 tính chỉ số này theo hai cách hoàn toàn khác nhau nên không so sánh trực tiếp được. Bài học: cùng tên metric nhưng cách đo khác nhau thì số liệu không có ý nghĩa khi đặt cạnh nhau.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

Câu hỏi đơn giản, chỉ cần tra một tài liệu (ví dụ: gq04 "store credit bao nhiêu %", gq05 "escalation sau 10 phút làm gì") — Day 08 trả lời đúng trong ~1.7 giây, Day 09 mất 10–20 giây qua 3 workers mà kết quả như nhau. Với những câu hỏi dạng FAQ đơn giản, multi-agent chỉ làm chậm thêm mà không tạo ra giá trị mới.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

> Đánh giá trung thực về quá trình làm việc nhóm.

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Vương Hoàng Giang | graph.py — supervisor_node, route_decision, AgentState; routing keyword tuning; LangGraph StateGraph setup | Sprint 1 + 2 |
| Phạm Anh Dũng | workers/retrieval.py — ChromaDB integration, embedding model; workers/synthesis.py — LLM call, fallback, _should_abstain, CẢNH BÁO block | Sprint 2 |
| Dương Quang Đông | mcp_server.py — 4 tools (search_kb, get_ticket_info, check_access_permission, create_ticket); workers/policy_tool.py — analyze_policy, temporal scoping, exception detection | Sprint 3 |
| Nguyễn Lê Trung | eval_trace.py — analyze_traces, compare_single_vs_multi; docs (system_architecture.md, routing_decisions.md, single_vs_multi_comparison.md); eval_metrics_day08.py | Sprint 2 + Docs Sprint 4 |

**Điều nhóm làm tốt:**

Phân công rõ ràng theo từng thành phần — mỗi người có thể chạy và kiểm tra phần mình độc lập mà không cần chờ người khác. Việc ghi trace JSON đầy đủ giúp khi có lỗi thì biết ngay vấn đề nằm ở bước nào thay vì phải đọc lại toàn bộ code.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**

Ban đầu phần lập chỉ mục tài liệu (Day 08) và phần tìm kiếm (Day 09) dùng hai model embedding khác nhau — kết quả là tìm kiếm trả về trống hoàn toàn trong nhiều giờ đầu mà không rõ lý do. Đây là lỗi phối hợp giữa hai thành viên phụ trách hai phần khác nhau.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**

Thống nhất các thông số kỹ thuật dùng chung (embedding model, ChromaDB path, top-k...) vào một file cấu hình chung ngay từ đầu, tránh mỗi người tự chọn một kiểu khác nhau.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

Có hai điểm cụ thể cần sửa dựa trên kết quả grading. Thứ nhất: câu gq10 (Flash Sale) bị trừ 5 điểm vì AI liệt kê cả điều kiện hoàn tiền thông thường lẫn ngoại lệ trong cùng một câu trả lời — đọc xong không biết kết luận là được hay không được. Cần sửa để khi đã có ngoại lệ thì chỉ nêu ngoại lệ, bỏ phần điều kiện thông thường. Thứ hai: câu gq01 và gq09 đều thiếu PagerDuty — thông tin này có trong tài liệu (tìm được với điểm số 0.53) nhưng bị bỏ qua khi tổng hợp. Cần yêu cầu AI liệt kê đủ tất cả kênh thông báo từ mọi đoạn văn đã tìm được.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
