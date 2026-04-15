# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Trịnh Kế Tiến  
**MSSV:** 2A202600500  
**Vai trò:** Pipeline Engineer / Embed Owner  
**Ngày nộp:** 15/04/2026

---

## 1. Tôi phụ trách phần nào?

**File / module:**

- `etl_pipeline.py`: Tôi chạy pipeline end-to-end với 3 run_id khác nhau (`sprint1`, `inject-bad`, `sprint4-final`). Fix lỗi UnicodeEncodeError tại dòng 91 — console cp1258 trên Windows không encode được ký tự tiếng Việt có dấu khi log.
- `transform/cleaning_rules.py`: Thêm 3 quy tắc mới R7 (strip BOM/control chars, L125–L135), R8 (min chunk length 20, L137–L145), R9 (reject missing exported_at, L147–L152).
- `quality/expectations.py`: Thêm 2 expectations mới E7 (`no_bom_control_in_chunk_text`, halt, L115–L130) và E8 (`all_rows_have_exported_at`, warn, L132–L143).
- `data/grading_questions.json`: Tạo bộ câu hỏi grading 3 câu (`gq_d10_01`, `gq_d10_02`, `gq_d10_03`) theo đúng rubric SCORING.md.

**Kết nối với thành viên khác:**

Tôi build baseline pipeline, tạo `run_id=sprint1` (10 raw → 6 cleaned, 4 quarantine) làm chuẩn đo cho nhóm. Sau đó, Đông chạy inject (`inject-bad`) và tôi clean lại (`sprint4-final`) để có bằng chứng before/after. Giang dùng manifest + eval CSV tôi sinh ra để điền docs.

**Bằng chứng:** Commit trên repo Team6 — file `etl_pipeline.py` sửa dòng 35 (RAW_DEFAULT) và dòng 91 (Unicode fix).

---

## 2. Một quyết định kỹ thuật

**Phát hiện bug data encoding:** File `policy_export_dirty_more_inject.csv` chứa tiếng Việt **không dấu** (ví dụ "Yeu cau hoan tien" thay vì "Yêu cầu hoàn tiền"). Khi grading_run.py tìm keyword "7 ngày" trong ChromaDB, nó không match vì data chỉ có "7 ngay" (không dấu) → `contains_expected=false` trên cả 3 câu.

**Fix:** Đổi `RAW_DEFAULT` trong `etl_pipeline.py` về file gốc `policy_export_dirty.csv` (có dấu tiếng Việt đầy đủ). Chạy lại pipeline: prune 6 vectors cũ (không dấu), upsert 6 vectors mới (có dấu) → grading 3/3 PASS.

Bài học: embedding model `all-MiniLM-L6-v2` xử lý tiếng Việt có dấu khác không dấu — data source phải giữ nguyên encoding gốc, không được strip dấu.

---

## 3. Một lỗi hoặc anomaly đã xử lý

**Triệu chứng:** Pipeline crash tại dòng 91 với `UnicodeEncodeError: 'charmap' codec can't encode character '\u1ebf'`. Xảy ra khi `print()` cố ghi tiếng Việt có dấu ra console cp1258 (Windows).

**Metric/check phát hiện:** Pipeline đã chạy xong validation (ghi nhận `refund_no_stale_14d_window FAIL`) nhưng crash trước khi embed → manifest không được tạo → freshness check không có dữ liệu để đo.

**Fix:** Thay log message tiếng Việt bằng ASCII thuần:
```python
# Trước (crash):
log("WARN: expectation failed but --skip-validate → tiếp tục embed...")
# Sau (fix):
log("WARN: expectation failed but --skip-validate -> continuing embed (only for Sprint 3 demo).")
```

Sau fix, pipeline chạy xuyên suốt: embed thành công, manifest ghi đúng, eval CSV tạo được.

---

## 4. Bằng chứng trước / sau

**Trước — Data không dấu** (grading trên `policy_export_dirty_more_inject.csv`):
```json
{"id":"gq_d10_01","contains_expected":false,"hits_forbidden":false,"top1_doc_matches":true}
```
→ `contains_expected=false` vì keyword "7 ngày" không match "7 ngay".

**Sau — Data có dấu** (grading trên `policy_export_dirty.csv`, `run_id=sprint4-final`):
```json
{"id":"gq_d10_01","contains_expected":true,"hits_forbidden":false,"top1_doc_matches":true}
```
→ `contains_expected=true`, `hits_forbidden=false`, `top1_doc_matches=true` — all 3/3 PASS → hạng **MERIT**.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ tạo file `policy_export_dirty_more_inject.csv` mới với tiếng Việt **có dấu** để test đầy đủ 3 rules R7/R8/R9 mà vẫn đảm bảo grading match. Ngoài ra, sẽ thêm Slack webhook vào `freshness_check.py` để gửi alert tự động khi SLA vượt ngưỡng, thay vì chỉ ghi log thụ động.
