# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Lê Trung  
**Vai trò trong nhóm:** Trace & Docs Owner  
**Ngày nộp:** 14/4/2026  
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần mình làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- File chính: `eval_trace.py`, `eval_metrics_day08.py`, `docs/system_architecture.md`, `docs/routing_decisions.md`, `docs/single_vs_multi_comparison.md`
- Functions tôi implement: `analyze_traces()` — đọc toàn bộ file trace JSON, tổng hợp các chỉ số như tỷ lệ routing, độ trễ, tỷ lệ abstain, multi-hop accuracy; `compare_single_vs_multi()` — so sánh kết quả Day 08 và Day 09. Ngoài ra tôi tự tạo `eval_metrics_day08.py` để tính chỉ số cho Day 08 mà không cần chạy lại pipeline của ngày đó.

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Tôi phụ thuộc vào trace JSON do `graph.py` (Vương Hoàng Giang) sinh ra — đặc biệt cần field `question_id` trong mỗi trace để ghép với danh sách câu hỏi kiểm tra. Ngược lại, phần docs tôi viết tổng hợp kết quả từ tất cả thành viên, nên tôi là người cuối cùng hoàn thiện sau khi pipeline chạy xong.

**Bằng chứng:**

File `eval_metrics_day08.py` tôi tạo mới hoàn toàn (không có trong Day 08 gốc). Output xác nhận: `artifacts/eval_report.json` (generated_at: 2026-04-14T19:03:20), `day08/lab/results/day08_metrics.json` (generated_at: 2026-04-14T18:58:17).

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Cách tính `multi_hop_accuracy` cho Day 09 — đo dựa trên việc supervisor có route đúng worker hay không, thay vì nhờ AI chấm nội dung câu trả lời.

**Lý do:**

Ban đầu tôi cần thêm chỉ số `multi_hop_accuracy` vào `analyze_traces()` nhưng không biết nên đo theo cách nào. Có hai lựa chọn: (1) dùng AI đọc câu trả lời và đánh giá xem có đúng không, hoặc (2) so sánh worker thực tế được gọi với worker kỳ vọng ghi trong `test_questions.json`. Tôi chọn cách 2 vì đơn giản hơn, không tốn thêm API, và kết quả luôn giống nhau mỗi lần chạy.

Tuy nhiên tôi cũng nhận ra trade-off: cách này chỉ đo "có route đúng không" chứ không đo "câu trả lời có đúng không". Ví dụ câu gq09 supervisor route đúng, 2 workers được gọi đúng, nhưng câu trả lời vẫn thiếu một số chi tiết và chỉ được 11/16 điểm. Tôi đã ghi chú sự khác biệt này trong file docs để tránh nhóm hiểu nhầm kết quả.

**Bằng chứng từ code:**

```python
# eval_trace.py
MULTIHOP_TYPES = {"multi_worker", "multi_worker_multi_doc", "temporal_scoping", "multi_detail"}

for fname in trace_files:
    qid = trace.get("question_id", "")
    test_type = test_q_map.get(qid, {}).get("test_type", "")
    expected_route = test_q_map.get(qid, {}).get("expected_route", "")
    actual_route = trace.get("supervisor_route", "")

    if test_type in MULTIHOP_TYPES:
        multihop_total += 1
        if actual_route == expected_route:
            multihop_correct += 1

# Kết quả: "multi_hop_accuracy": "24/24 (100%)"
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** `multi_hop_accuracy` bị thiếu hoàn toàn trong kết quả `eval_report.json`.

**Symptom:**

Chạy `eval_trace.py` ra file `eval_report.json` nhưng không có dòng `multi_hop_accuracy`, `abstain_rate`, `abstain_accuracy`. Phần so sánh D08 vs D09 bị trống ở cột này.

**Root cause:**

`analyze_traces()` chỉ đọc các trường có sẵn trong trace JSON (`supervisor_route`, `confidence`, `latency_ms`...) mà không load file `test_questions.json`. Vì vậy hàm không biết câu nào là multi-hop, câu nào cần abstain — không tính được.

**Cách sửa:**

Tôi thêm bước load `test_questions.json` vào đầu hàm, tạo bảng tra cứu `test_q_map = {q["id"]: q}`, rồi với mỗi trace, ghép theo `question_id` để lấy `test_type` và `expected_route`. Từ đó tính được các chỉ số còn thiếu.

**Bằng chứng trước/sau:**

```
# TRƯỚC — eval_report.json không có:
"day09_multi_agent": {
    "avg_confidence": 0.3,
    "avg_latency_ms": 11319,
    ...
    # thiếu: multi_hop_accuracy, abstain_rate, abstain_accuracy
}

# SAU — đầy đủ:
"day09_multi_agent": {
    "avg_confidence": 0.3,
    "avg_latency_ms": 11319,
    "abstain_rate": "41/95 (43%)",
    "multi_hop_accuracy": "24/24 (100%)",
    "abstain_accuracy": "5/6 (83%)"
}
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Khi viết `eval_metrics_day08.py`, tôi cẩn thận không đụng vào bất kỳ file nào của Day 08 — chỉ đọc file kết quả đã có. Điều này giúp pipeline Day 08 không bị ảnh hưởng và số liệu so sánh vẫn trung thực. Ngoài ra tôi ghi chú rõ ở mọi chỗ rằng cách tính confidence của Day 08 và Day 09 khác nhau — để nhóm không hiểu nhầm con số.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Cách tôi phát hiện câu abstain khá thô — chỉ tìm từ khóa "không đủ thông tin" trong câu trả lời. Nếu model diễn đạt khác đi thì bị bỏ sót.

**Nhóm phụ thuộc vào tôi ở đâu?**

Nếu `eval_metrics_day08.py` chưa xong thì không có số liệu Day 08 để điền vào bảng so sánh — `single_vs_multi_comparison.md` sẽ trống một cột.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi cần `graph.py` sinh trace JSON có field `question_id`. Nếu field này bị thiếu thì `multi_hop_accuracy` và `abstain_accuracy` đều tính về 0.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ thêm bước chấm điểm tự động vào `eval_trace.py` — so sánh câu trả lời của pipeline với tiêu chí chấm trong `grading_questions.json`. Lý do cụ thể: câu gq09 supervisor route đúng, gọi đúng 2 workers, nhưng câu trả lời vẫn thiếu chi tiết và chỉ được 11/16 điểm. Chỉ số routing correctness 100% không phát hiện được vấn đề này. Nếu có bước chấm điểm tự động thì nhóm sẽ biết sớm hơn chỗ nào cần cải thiện.

---
