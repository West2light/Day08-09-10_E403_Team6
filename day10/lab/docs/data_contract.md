# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

**version:** 1.0  
**dataset:** `kb_chunk_export`  
**owner_team:** Nhóm 6  
**freshness SLA:** 24 giờ (measured_at: publish)

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | `doc_id` | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|---------|-------------------|-------------------|----------------|
| `data/docs/policy_refund_v4.txt` | `policy_refund_v4` | CSV export → `load_raw_csv` | Chunk cũ "14 ngày làm việc" từ policy-v3 lọt vào do migration sai | Expectation E3 `refund_no_stale_14d_window` HALT; eval `hits_forbidden=yes` |
| `data/docs/sla_p1_2026.txt` | `sla_p1_2026` | CSV export → `load_raw_csv` | Thiếu `effective_date` hoặc sai format (dd/mm/yyyy) | Expectation E5 `effective_date_iso_yyyy_mm_dd` HALT; quarantine `missing_effective_date` |
| `data/docs/it_helpdesk_faq.txt` | `it_helpdesk_faq` | CSV export → `load_raw_csv` | `effective_date` sai format `01/02/2026` → rule R2 normalize → `2026-02-01` | Log `effective_date_normalized`; quarantine nếu không parse được |
| `data/docs/hr_leave_policy.txt` | `hr_leave_policy` | CSV export → `load_raw_csv` | Xung đột version: bản HR 2025 (10 ngày phép) vs bản 2026 (12 ngày phép) | Rule R3 quarantine `effective_date < 2026-01-01`; Expectation E6 `hr_leave_no_stale_10d_annual` HALT |
| `data/raw/policy_export_dirty.csv` | *(nhiều doc_id)* | File CSV tổng hợp từ DB/API | `doc_id` lạ không thuộc allowlist (`legacy_catalog_xyz_zzz`) | Rule R1 quarantine `unknown_doc_id`; quarantine_records tăng |

**Allowlist `doc_id`** (đồng bộ với `ALLOWED_DOC_IDS` trong `transform/cleaning_rules.py`):
```
policy_refund_v4 | sla_p1_2026 | it_helpdesk_faq | hr_leave_policy
```
Thêm `doc_id` mới phải cập nhật đồng thời: `cleaning_rules.py` → `ALLOWED_DOC_IDS`, `data_contract.yaml` → `allowed_doc_ids`, và `data/test_questions.json`.

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ràng buộc | Ghi chú |
|-----|------|----------|-----------|---------|
| `chunk_id` | string | Có | Unique, stable | Sinh bởi `_stable_chunk_id(doc_id, chunk_text, seq)` = `{doc_id}_{seq}_{sha256[:16]}`; cùng nội dung → cùng ID → upsert idempotent |
| `doc_id` | string | Có | Thuộc `ALLOWED_DOC_IDS` | Khóa logic tài liệu nguồn; record không hợp lệ bị quarantine lý do `unknown_doc_id` |
| `chunk_text` | string | Có | `len >= 8` (E4 warn), `len >= 20` (R8 quarantine) | Không chứa ký tự BOM `\ufeff` / control `\x00–\x08` (R7 strip); không chứa "14 ngày làm việc" sau fix (E3 halt) |
| `effective_date` | date | Có | Format `YYYY-MM-DD` (ISO 8601) | Rule R2 normalize `dd/mm/yyyy → yyyy-mm-dd`; `hr_leave_policy` phải ≥ `2026-01-01` (policy_versioning) |
| `exported_at` | datetime | Có | Không rỗng (R9 quarantine, E8 warn) | Dùng để tính `latest_exported_at` trong manifest → freshness check |

**Điều kiện bổ sung theo `contracts/data_contract.yaml`:**
- `hr_leave_min_effective_date: 2026-01-01` — bản HR có `effective_date` trước ngày này bị coi là stale
- Chunk `policy_refund_v4` sau clean không được chứa chuỗi "14 ngày làm việc" (quality rule `no_stale_refund_window`, severity: halt)

---

## 3. Quy tắc quarantine vs drop

**Các record bị flag đi vào** `artifacts/quarantine/quarantine_{run_id}.csv` kèm cột `reason`:

| Lý do (`reason`) | Quy tắc nguồn | Severity | Xử lý tiếp theo |
|-----------------|--------------|----------|-----------------|
| `unknown_doc_id` | R1 — allowlist | Quarantine | Xem xét thêm vào allowlist hoặc xóa khỏi export nguồn; cần approval từ owner |
| `missing_effective_date` | R2 — normalize date | Quarantine | Bổ sung `effective_date` ở hệ nguồn rồi re-export |
| `invalid_effective_date_format` | R2 — normalize date | Quarantine | Sửa format ở hệ nguồn hoặc thêm parser mới vào `_normalize_effective_date` |
| `stale_hr_policy_effective_date` | R3 — HR version | Quarantine | Không dùng; bản canonical là bản 2026 (`effective_date ≥ 2026-01-01`) |
| `missing_chunk_text` | R4 — empty text | Quarantine | Kiểm tra export pipeline nguồn — chunk trống không có giá trị retrieval |
| `bom_control_only_content` | R7 — BOM strip | Quarantine | Chunk chỉ chứa ký tự BOM/control; xóa ở hệ nguồn |
| `chunk_too_short` | R8 — min length | Quarantine | Chunk < 20 ký tự sau strip — không đủ thông tin cho retrieval; merge hoặc bỏ |
| `missing_exported_at` | R9 — exported_at | Quarantine | Bổ sung timestamp export ở hệ nguồn; thiếu field này không thể kiểm tra freshness |
| `duplicate_chunk_text` | R5 — dedupe | Quarantine | Giữ bản đầu tiên; các bản sau bị drop — không cần approve, đây là behavior đúng |

**Ai approve merge lại?**
- Record quarantine **không tự động được merge** trở lại cleaned — phải sửa ở **hệ nguồn** và re-export.
- Ngoại lệ: `duplicate_chunk_text` là behavior bình thường (giữ bản đầu) — không cần can thiệp.
- Owner theo `doc_id` (xem Section 1) phải review và approve trước khi thêm doc mới hoặc thay đổi cleaning rule ảnh hưởng đến allowlist.

---

## 4. Phiên bản & canonical

**Source of truth theo từng `doc_id`:**

| `doc_id` | File canonical | Version hiện hành | Ghi chú |
|---------|---------------|-------------------|---------|
| `policy_refund_v4` | `data/docs/policy_refund_v4.txt` | v4 (2026-02-01) | Cửa sổ hoàn tiền = **7 ngày làm việc**; bản v3 "14 ngày" là lỗi migration — bị cleaning rule R6 fix và expectation E3 chặn |
| `sla_p1_2026` | `data/docs/sla_p1_2026.txt` | 2026 (2026-02-01) | SLA P1: phản hồi ≤ 15 phút, resolution ≤ 4 giờ |
| `it_helpdesk_faq` | `data/docs/it_helpdesk_faq.txt` | 2026 (2026-02-01) | Khóa tài khoản sau 5 lần sai; đồng bộ mật khẩu tối đa 24 giờ |
| `hr_leave_policy` | `data/docs/hr_leave_policy.txt` | 2026 (effective ≥ 2026-01-01) | Nhân viên < 3 năm = **12 ngày phép/năm**; bản 2025 "10 ngày" bị quarantine theo `hr_leave_min_effective_date` |

**Quy tắc versioning:**
- Cột `effective_date` trong cleaned CSV là nguồn chính xác định version tài liệu.
- Với `hr_leave_policy`, cutoff `2026-01-01` được định nghĩa trong `contracts/data_contract.yaml` (`policy_versioning.hr_leave_min_effective_date`) — không hard-code trong code, tham chiếu từ config để dễ cập nhật.
- Khi có version mới (vd: `policy_refund_v5`), phải cập nhật `doc_id` trong allowlist, thêm test question, và kiểm tra không còn chunk version cũ trong ChromaDB sau pipeline run.
