# Quality report — Lab Day 10 (nhóm)

**run_id:** sprint4-final  
**Ngày:** 15/04/2026

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (inject-bad) | Sau (sprint4-final) | Ghi chú |
|--------|:---:|:---:|---------|
| raw_records | 10 | 10 | Cùng CSV source |
| cleaned_records | 6 | 6 | Số records hợp lệ |
| quarantine_records | 4 | 4 | 4 records lỗi bị cách ly |
| Expectation halt? | **YES** (refund stale) | **NO** (all OK) | inject-bad có violations=1 |

---

## 2. Before / after retrieval (bắt buộc)

> Đính kèm: `artifacts/eval/eval_bad.csv` và `artifacts/eval/eval_clean.csv`

**Câu hỏi then chốt:** refund window (`gq_d10_01`)

**Trước (inject-bad — `eval_bad.csv`):**
```csv
q_refund_window,policy_refund_v4,"Yêu cầu được gửi trong vòng 7 ngày làm việc...",yes,yes,,3
```
→ `hits_forbidden=yes` — chunk stale "14 ngày" đã lọt vào ChromaDB.

**Sau (sprint4-final — `eval_clean.csv`):**
```csv
q_refund_window,policy_refund_v4,"Yêu cầu được gửi trong vòng 7 ngày làm việc...",yes,no,,3
```
→ `hits_forbidden=no` — pipeline đã fix và loại bỏ thông tin sai.

**Merit: versioning HR — `gq_d10_03` (grading_run.jsonl):**

```json
{"id":"gq_d10_03","contains_expected":true,"hits_forbidden":false,"top1_doc_matches":true}
```
→ Top-1 document là `hr_leave_policy`, trả đúng "12 ngày phép năm", không dính "10 ngày" cũ. `top1_doc_expected=yes`.

---

## 3. Freshness & monitor

Kết quả `freshness_check` trên manifest `sprint4-final`:
```
freshness_check=FAIL
  latest_exported_at: 2026-04-10T08:00:00
  age_hours: 120.239
  sla_hours: 24.0
  reason: freshness_sla_exceeded
```

**Giải thích:** FAIL là hợp lý vì CSV mẫu có `exported_at` ngày 10/04, kiểm tra ngày 15/04 → cách 120 giờ > SLA 24h. Trong production, cronjob chạy mỗi 2h sẽ giữ `age_hours` dưới ngưỡng. Pipeline đo freshness tại thời điểm **publish** (sau embed xong, ghi manifest).

---

## 4. Corruption inject (Sprint 3)

Cố ý inject dữ liệu hỏng bằng flag `--no-refund-fix --skip-validate`:
```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
```

**Loại corruption:** Chunk refund policy chứa "14 ngày làm việc" (version cũ v3) không bị fix → embed trực tiếp vào ChromaDB.

**Phát hiện:** Expectation `refund_no_stale_14d_window` báo FAIL (halt) với `violations=1` trong log. Do `--skip-validate`, pipeline vẫn tiếp tục embed → `eval_bad.csv` ghi nhận `hits_forbidden=yes`.

**Khắc phục:** Chạy lại clean pipeline (`sprint4-final`) → expectation all OK → embed data sạch → `eval_clean.csv` xác nhận `hits_forbidden=no`.

---

## 5. Hạn chế & việc chưa làm

- Freshness đo tại 1 boundary (publish). Distinction yêu cầu 2 boundary (ingest + publish).
- Expectation dùng Python thuần. Bonus +2đ nếu tích hợp Great Expectations/Pydantic thật.
- Console Windows cp1258 gây crash Unicode → đã fix bằng ASCII log nhưng chưa elegant.
