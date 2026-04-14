# Báo Cáo Nhóm — Lab Day 08: Full RAG Pipeline

**Tên nhóm:** Nhóm 6  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Vương Hoàng Giang | Tech Lead | gvuonghoang123@gmail.com |
| Dương Quang Đông | Retrieval Owner | quangdong010203@gmail.com |
| Phạm Anh Dũng | Eval Owner | panhdung2511@gmail.com |
| Nguyễn Lê Trung | Documentation Owner | nguyenletrung2002@gmail.com |

**Ngày nộp:** 14/4/2026  
**Repo:** [Day08-09-10_E403_Team6](https://github.com/West2light/Day08-09-10_E403_Team6/tree/main/day08)  

---

## 1. Pipeline nhóm đã xây dựng (150–200 từ)

**Chunking decision:**
Nhóm dùng `chunk_size = 500 tokens`, `overlap = 100 tokens`; code quy đổi xấp xỉ 2000 và 400 ký tự. Chunking ưu tiên heading/section `=== ... ===`; nếu section dài thì cắt theo ranh giới tự nhiên. Metadata gồm `source`, `section`, `effective_date`, `department`, `access`.

**Embedding model:**
`paraphrase-multilingual-MiniLM-L12-v2`

**Retrieval variant (Sprint 3):**
Nhóm chọn variant là hybrid: dense + sparse/BM25, giữ nguyên top-k, không bật rerank/query transform. Lý do: corpus có cả policy/SOP và keyword như SLA, P1, Level 3, ERR-403, Approval Matrix.

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

**Quyết định:** Chọn variant hybrid làm biến tuning chính của Sprint 3.

**Bối cảnh vấn đề:**

Baseline dense retrieve tốt phần lớn câu hỏi, nhưng vẫn có rủi ro ở truy vấn chứa keyword/alias như `Approval Matrix`, `Level 3`, `P1`, `ERR-403`.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Dense baseline | Đơn giản, ổn định, recall cao | Có thể bỏ lỡ keyword/alias |
| Hybrid dense + BM25 | Kết hợp semantic và keyword search | Có thể thêm noise |
| Rerank / query transform | Tăng precision hoặc xử lý alias | Tốn thêm model/logic |

**Phương án đã chọn và lý do:**

Nhóm chọn hybrid vì chỉ đổi một biến, dễ A/B với baseline. Dense tìm theo nghĩa, BM25 bắt keyword như SLA, P1, Level 3, Approval Matrix.

**Bằng chứng từ scorecard/tuning-log:**

Kết quả thực tế chạy thực tế cho thấy hybrid chưa cải thiện điểm trung bình. Faithfulness 4.50, Relevance 4.20, Context Recall 5.00, Completeness 3.80, bằng baseline. Lỗi còn lại nghiêng về completeness/generation hoặc thiếu evidence.

---

## 3. Kết quả grading questions (100–150 từ)

Điểm dưới đây được nhóm ước tính thủ công bằng cách đối chiếu answer trong `logs/grading_run.json` với `grading_criteria` và `points` trong `data/grading_questions.json`.

| ID | Điểm tối đa | Điểm ước tính | Nhận xét |
|----|-------------|---------------|---------------|
| gq01 | 10 | 8 | Đúng 6 giờ → 4 giờ, nhưng thiếu rõ `v2026.1` hoặc effective date. |
| gq02 | 10 | 3 | Nêu đúng giới hạn 2 thiết bị, nhưng thiếu VPN bắt buộc, Cisco AnyConnect và citation 2 nguồn. |
| gq03 | 10 | 10 | Đúng kết luận không hoàn tiền, nêu đủ Flash Sale và sản phẩm đã kích hoạt. |
| gq04 | 8 | 5 | Đúng 110%, có citation, nhưng chưa nói đây là tùy chọn không bắt buộc. |
| gq05 | 10 | 2 | Trả lời lệch sang quyền tạm thời khẩn cấp 24 giờ, thiếu IT Manager + CISO, 5 ngày và training. |
| gq06 | 12 | 10 | Đúng quy trình tạm thời, Tech Lead, 24 giờ và Security Audit; thiếu hotline ext. 9999. |
| gq07 | 10 | 5 | Abstain, không hallucinate mức phạt, nhưng quá ngắn và chưa nói rõ tài liệu không có thông tin penalty. |
| gq08 | 10 | 10 | Đúng nghỉ phép báo trước 3 ngày, nghỉ ốm trên 3 ngày cần giấy tờ, phân biệt hai ngữ cảnh. |
| gq09 | 8 | 6 | Đúng 90 ngày và nhắc trước 7 ngày, nhưng thiếu kênh đổi mật khẩu SSO/Helpdesk. |
| gq10 | 10 | 10 | Đúng không áp dụng trước 01/02/2026 và đơn cũ dùng chính sách phiên bản 3. |
| **Tổng** | **98** | **69** |  |

**Ước tính điểm raw:** 69 / 98

**Câu tốt nhất:** ID:gq03, gq08, gq10 - Lý do: đạt đủ criteria.

**Câu fail:** IDgq05 - Root cause: answer lấy nhầm quy trình escalation tạm thời thay vì Admin Access Level 4.

**Câu gq07 (abstain):** Có abstain và không bịa mức phạt, nhưng chỉ trả lời “Tôi không biết”, chưa nêu rõ thông tin penalty không có trong tài liệu hiện có.

---

## 4. A/B Comparison — Baseline vs Variant (150–200 từ)

**Biến đã thay đổi (chỉ 1 biến):** `retrieval_mode`: từ `dense` sang `hybrid`.

| Metric | Baseline | Variant | Delta |
|--------|---------|---------|-------|
| Faithfulness | 4.50/5 | 4.50/5 | 0.00 |
| Answer Relevance | 4.20/5 | 4.20/5 | 0.00 |
| Context Recall | 5.00/5 | 5.00/5 | 0.00 |
| Completeness | 3.80/5 | 3.80/5 | 0.00 |

**Kết luận:**
Variant hybrid chưa tốt hơn baseline: tất cả metric trung bình bằng nhau và q04, q07, q09, q10 không cải thiện. Hybrid vẫn giữ chất lượng baseline; q03 đổi citation từ `[2]` sang `[1]`. A/B cho thấy bottleneck không còn là context recall vì recall đã đạt 5.00. Vòng sau nên ưu tiên prompt grounding, query expansion hoặc rerank.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Vương Hoàng Giang | Tech Lead, dựng/review `index.py`, `rag_answer.py`, cross-check A/B | 1, 2 |
| Dương Quang Đông | Retrieval Owner, indexing/chunking/metadata, retrieval strategy | 1, 3 |
| Phạm Anh Dũng | Eval Owner, chạy `eval.py`, scorecard, A/B và grading log | 3, 4 |
| Nguyễn Lê Trung | Documentation Owner, `architecture.md`, `tuning-log.md`, báo cáo | 4 |

**Điều nhóm làm tốt:**

Nhóm đã chạy pipeline end-to-end, ChromaDB persistent, scorecard baseline/variant và log grading đủ 10 câu.

**Điều nhóm làm chưa tốt:**

Phân công và làm việc nhóm còn mâu thuẫn, dẫn đến một số lỗi kỹ thuật. Pipeline của nhóm còn chưa chạy tốt với grading_question.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

Nhóm sẽ thử query expansion cho alias như `Approval Matrix` → `Access Control SOP` và siết grounded prompt để trả lời đủ tên cũ/tên mới, điều kiện, ngoại lệ. Ngoài ra, nhóm sẽ thử rerank với `top_k_search = 20` để giảm noise BM25. Lý do: Context Recall đã đạt 5.00, nhưng Completeness vẫn thấp ở q04, q07, q10.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
