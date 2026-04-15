# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| `data/raw/policy_export_dirty.csv` | Batch CSV export | Format ngày sai, doc_id lạ, chunk trùng, refund stale 14→7 ngày | `quarantine_records`, `expectation[refund_no_stale_14d_window]` |
| `data/docs/*.txt` (5 files) | Canonical text files | Version conflict (HR 10 ngày vs 12 ngày) | `expectation[hr_leave_no_stale_10d_annual]` |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | SHA256 hash: `{doc_id}_{seq}_{hash16}` — ổn định cho upsert |
| doc_id | string | Có | Phải thuộc allowlist: `policy_refund_v4`, `sla_p1_2026`, `it_helpdesk_faq`, `hr_leave_policy` |
| chunk_text | string | Có | Cleaning rule R8: quarantine nếu < 20 ký tự; Expectation E4: WARN nếu < 8 ký tự; không chứa BOM/control chars (R7 + E7) |
| effective_date | date | Có | Format ISO `YYYY-MM-DD`; HR policy phải >= 2026-01-01 |
| exported_at | datetime | Có | Bắt buộc có giá trị (R9 + E8); dùng cho freshness SLA check và lineage tracking |

---

## 3. Quy tắc quarantine vs drop

Record bị flag sẽ được ghi vào file `artifacts/quarantine/quarantine_{run_id}.csv` kèm cột `reason`. Quarantine records KHÔNG bị xóa mà được lưu trữ để audit. Chỉ cleaned records mới được embed vào ChromaDB.

Các reason phổ biến: `unknown_doc_id`, `missing_effective_date`, `invalid_effective_date_format`, `stale_hr_policy_effective_date`, `missing_chunk_text`, `duplicate_chunk_text`, `bom_control_only_content`, `chunk_too_short`, `missing_exported_at`.

---

## 4. Phiên bản & canonical

Source of truth cho policy refund: file `data/docs/policy_refund_v4.txt` — version v4 quy định **7 ngày làm việc**. Pipeline tự động fix chunk chứa "14 ngày làm việc" (v3 cũ) thành "7 ngày làm việc" và gắn tag `[cleaned: stale_refund_window]`.

HR leave policy: cutoff `effective_date >= 2026-01-01`. Bản cũ (10 ngày phép) bị quarantine, giữ lại bản 2026 (12 ngày phép).
