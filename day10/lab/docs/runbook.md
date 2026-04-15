# Runbook — Lab Day 10 (incident tối giản)

---

## Symptom

User / agent thấy gì?
- Agent trả lời "14 ngày làm việc" thay vì 7 ngày khi hỏi về chính sách hoàn tiền.
- Agent trả lời "10 ngày phép năm" thay vì 12 ngày khi hỏi về nghỉ phép 2026.
- `eval_retrieval.py` báo `hits_forbidden=yes` trên câu `q_refund_window`.

---

## Detection

Metric nào báo?
- **Expectation**: `expectation[refund_no_stale_14d_window] FAIL (halt)` trong pipeline log.
- **Expectation E7**: `expectation[no_bom_control_in_chunk_text] FAIL (halt)` — chunk chứa BOM/control char sót sau clean.
- **Expectation E8**: `expectation[all_rows_have_exported_at] FAIL (warn)` — row thiếu `exported_at` (freshness lineage bị đứt).
- **Eval CSV**: `hits_forbidden=yes` trong `artifacts/eval/eval_clean.csv` hoặc output eval mới nhất.
- **Grading JSONL**: `hits_forbidden=true` trên `gq_d10_01`.
- **Freshness**: `freshness_check=FAIL` khi `age_hours > sla_hours` (24h).

---

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/manifests/manifest_{run_id}.json` | Xác nhận `no_refund_fix=true` hoặc `skipped_validate=true` |
| 2 | Mở `artifacts/quarantine/quarantine_{run_id}.csv` | Tìm rows có `reason=stale_refund_window` hoặc thiếu |
| 3 | Chạy `python eval_retrieval.py` | Xác nhận `hits_forbidden=yes` trên q_refund_window |
| 4 | Kiểm tra `artifacts/logs/run_{run_id}.log` | Tìm dòng `expectation[...] FAIL` |

---

## Mitigation

1. Rerun pipeline **KHÔNG** dùng `--no-refund-fix`:
   ```bash
   python etl_pipeline.py run --run-id fix-$(date +%s)
   ```
2. Pipeline sẽ tự fix "14 ngày" → "7 ngày" và embed lại ChromaDB.
3. Prune tự động xóa vector cũ không còn trong batch cleaned.
4. Chạy lại eval để confirm `hits_forbidden=no`:
   ```bash
   python eval_retrieval.py --out artifacts/eval/eval_after_fix.csv
   ```

---

## Prevention

- **KHÔNG** dùng `--skip-validate` trong production. Flag này chỉ dành cho demo Sprint 3.
- E7 (`no_bom_control_in_chunk_text`, halt) và E8 (`all_rows_have_exported_at`, warn) **đã được tích hợp** — pipeline tự bắt BOM/control chars và thiếu exported_at trên mọi clean run.
- Thiết lập alert khi freshness > SLA: tích hợp Slack webhook vào `freshness_check.py`.
- Owner team review quarantine CSV định kỳ trước khi approve merge.
