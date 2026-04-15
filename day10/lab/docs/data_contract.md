# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| `data/raw/policy_export_dirty.csv` — CSV export từ hệ thống nội bộ (policy & HR) | Batch CSV, đọc bằng `load_raw_csv()` trong `transform/cleaning_rules.py` | **unknown_doc_id**: doc_id không thuộc allowlist (vd `legacy_catalog_xyz_zzz`) → quarantine; **missing/invalid effective_date**: ngày rỗng hoặc sai định dạng (vd `01/02/2026`) → quarantine | `quarantine_records` trong log + manifest; alert khi `quarantine_records > 0` |
| `data/docs/*.txt` — Tài liệu canonical (policy_refund_v4, sla_p1_2026, it_helpdesk_faq, hr_leave_policy) | Đọc trực tiếp làm ground-truth để verify nội dung chunk; không ingest lại qua pipeline | **stale_refund_window**: chunk chứa "14 ngày làm việc" thay vì "7 ngày" (lỗi migration từ policy-v3); **stale_hr_policy**: `effective_date < 2026-01-01` → bản HR 2025 lọt vào | `expectation[no_stale_refund_window]` severity=halt; log `PIPELINE_HALT` nếu fail |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | ID ổn định sau clean — hash SHA-256(doc_id \| chunk_text \| seq)[:16], dạng `{doc_id}_{seq}_{hash}` |
| doc_id | string | Có | Khóa logic tài liệu nguồn; phải thuộc `allowed_doc_ids` trong `data_contract.yaml` |
| chunk_text | string | Có | Nội dung chunk sau clean; `min_length = 8` ký tự; chunk refund v4 được fix `14 ngày → 7 ngày` + tag `[cleaned: stale_refund_window]` |
| effective_date | date | Có | Chuẩn hoá sang `YYYY-MM-DD`; chấp nhận input `DD/MM/YYYY` (tự động convert); không được rỗng |
| exported_at | datetime | Có | Timestamp xuất từ hệ thống nguồn, định dạng ISO-8601; dùng để tính `latest_exported_at` trong manifest |

---

## 3. Quy tắc quarantine vs drop

Record **bị quarantine** (không vào cleaned, lưu vào `artifacts/quarantine/`) khi gặp một trong các lý do sau:

| Lý do (`reason`) | Điều kiện | Hành động |
|------------------|-----------|-----------|
| `unknown_doc_id` | `doc_id` không thuộc allowlist | Quarantine — có thể là export nhầm catalog; cần owner_team xác nhận thêm doc mới vào `allowed_doc_ids` |
| `missing_effective_date` | `effective_date` rỗng | Quarantine — thiếu metadata bắt buộc |
| `invalid_effective_date_format` | Không parse được (không phải ISO hay DD/MM/YYYY) | Quarantine — ghi thêm `effective_date_raw` để trace |
| `stale_hr_policy_effective_date` | `doc_id = hr_leave_policy` AND `effective_date < 2026-01-01` | Quarantine — bản HR 2025 conflict với bản 2026; cutoff lấy từ `policy_versioning.hr_leave_min_effective_date` trong contract |
| `missing_chunk_text` | `chunk_text` rỗng sau strip | Quarantine |
| `duplicate_chunk_text` | Nội dung chunk đã xuất hiện trong cùng run (normalize lowercase + collapse whitespace) | Quarantine — giữ bản đầu tiên |

**Vị trí lưu:** `artifacts/quarantine/quarantine_{run_id}.csv`

**Ai approve merge lại:** Owner team (`Nhóm 6`) review file quarantine sau mỗi run. Merge lại bằng cách sửa nguồn gốc (CSV raw hoặc doc canonical) rồi chạy lại pipeline — **không sửa thủ công** file cleaned.

Record bị **drop hoàn toàn** (không lưu): không có — mọi record lỗi đều được giữ trong quarantine để audit.

---

## 4. Phiên bản & canonical

**Source of truth cho policy refund:** `data/docs/policy_refund_v4.txt` — phiên bản **v4**, cửa sổ hoàn tiền **7 ngày làm việc**. Bất kỳ chunk nào chứa "14 ngày làm việc" là lỗi migration từ v3 và phải được fix bởi cleaning rule `stale_refund_window` (severity = halt nếu sót qua).

| doc_id | File canonical | Phiên bản / ghi chú |
|--------|---------------|---------------------|
| `policy_refund_v4` | `data/docs/policy_refund_v4.txt` | v4 — cửa sổ 7 ngày làm việc (v3 đã lỗi thời) |
| `sla_p1_2026` | `data/docs/sla_p1_2026.txt` | 2026 — SLA P1: phản hồi 15 phút, resolution 4 giờ |
| `it_helpdesk_faq` | `data/docs/it_helpdesk_faq.txt` | Hiện hành — khoá tài khoản sau 5 lần sai |
| `hr_leave_policy` | `data/docs/hr_leave_policy.txt` | 2026 (`effective_date ≥ 2026-01-01`) — 12 ngày phép; cutoff cấu hình tại `policy_versioning.hr_leave_min_effective_date` trong `contracts/data_contract.yaml` |

> Khi nhóm bổ sung tài liệu mới: (1) thêm file vào `data/docs/`, (2) đăng ký `doc_id` vào `allowed_doc_ids` + `canonical_sources` trong `data_contract.yaml`, (3) đồng bộ `ALLOWED_DOC_IDS` trong `transform/cleaning_rules.py`.
