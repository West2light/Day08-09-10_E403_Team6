# Runbook — Lab Day 10 (incident tối giản)

---

## Symptom

Agent / chatbot trả lời sai thông tin chính sách hoàn tiền: trả lời **”14 ngày làm việc”** thay vì **”7 ngày làm việc”** khi người dùng hỏi về thời hạn yêu cầu hoàn tiền.

Nguyên nhân gốc: chunk `policy_refund_v4` bị nhiễm bản cũ (`policy-v3 — lỗi migration`) với nội dung “14 ngày làm việc” không bị lọc khi pipeline chạy với flag `--skip-validate` (run_id: `inject-bad`). Chunk sai này được embed vào ChromaDB và retrieval trả về trước chunk đúng.

---

## Detection

| Metric | Nguồn | Giá trị cảnh báo |
|--------|-------|-----------------|
| `hits_forbidden` = `yes` | `artifacts/eval/eval_bad.csv` | Câu hỏi `q_refund_window` trả về chunk chứa “14 ngày làm việc” |
| Expectation `refund_no_stale_14d_window` FAIL | `quality/expectations.py` (E3) | `violations=1` — severity: **halt** |
| Freshness SLA | `monitoring/freshness_check.py` | `age_hours` của `latest_exported_at=2026-04-10T08:00:00` vượt SLA 24h so với thời điểm kiểm tra |
| `quarantine_records = 4` | `artifacts/manifests/manifest_inject-bad.json` | Có 4 chunk bị cách ly — cần xác nhận lý do |

---

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/manifests/manifest_inject-bad.json` | Xác nhận `skipped_validate: true` và `no_refund_fix: true` — pipeline bỏ qua bước clean/validate |
| 2 | Mở `artifacts/quarantine/quarantine_inject-bad.csv` | Thấy 4 chunk bị cách ly: `duplicate_chunk_text`, `missing_effective_date`, `stale_hr_policy_effective_date`, `unknown_doc_id` |
| 3 | So sánh `artifacts/cleaned/cleaned_inject-bad.csv` | Chunk `policy_refund_v4` có nội dung “14 ngày làm việc” vẫn tồn tại trong cleaned — không bị lọc |
| 4 | Chạy `python eval_retrieval.py` | `eval_bad.csv`: câu hỏi `q_refund_window` có `hits_forbidden=yes` — khác với `eval_clean.csv` có `hits_forbidden=no` |
| 5 | Xác nhận expectation E3 | Chạy `quality/expectations.py` với cleaned data của `inject-bad`: `refund_no_stale_14d_window` FAIL, `violations=1` |

---

## Mitigation

1. **Rerun pipeline** với flag đúng: `python etl_pipeline.py --run-id sprint4-final` (không có `--skip-validate`, không có `--no-refund-fix`). Manifest `manifest_sprint4-final.json` xác nhận `no_refund_fix: false`, `skipped_validate: false`.
2. **Rollback embed**: xóa collection ChromaDB hiện tại và re-embed từ `cleaned_sprint4-final.csv` — đảm bảo chunk “14 ngày” không còn trong index.
3. **Kiểm tra lại eval**: chạy `python eval_retrieval.py` — tất cả câu hỏi phải có `hits_forbidden=no` (so với `eval_clean.csv`).
4. **Tạm thời**: trong khi rerun, đặt banner cảnh báo trên giao diện chatbot “Thông tin chính sách đang được cập nhật, vui lòng liên hệ bộ phận hỗ trợ để xác nhận”.

---

## Prevention

1. **Expectation E3** (`refund_no_stale_14d_window`, severity: `halt`) đã có sẵn — đảm bảo pipeline KHÔNG chạy với `--skip-validate`.
2. **Thêm alert**: nếu `skipped_validate: true` trong manifest → gửi cảnh báo ngay (Slack / email).
3. **Thêm expectation E6** (`hr_leave_no_stale_10d_annual`, severity: `halt`) để ngăn tương tự với HR policy (phép năm 10 ngày vs 12 ngày).
4. **Freshness check**: tích hợp `monitoring/freshness_check.py` vào CI — fail build nếu `age_hours > 24`.
5. **Owner**: gắn `doc_id` với owner cụ thể trong `contracts/data_contract.yaml`; owner phải approve trước khi merge chunk có conflict version.
6. **Day 11**: kết nối guardrail — mỗi câu trả lời của agent phải kèm `source_chunk_id` và `effective_date` để truy vết ngược về pipeline run.
