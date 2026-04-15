# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Lê Trung  
**MSSV:** 2A202600174  
**Vai trò:** Ingestion Owner — Sprint 1 baseline  
**Ngày nộp:** 15/04/2026

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `transform/cleaning_rules.py` → hàm `load_raw_csv()` (dòng 63–69): lớp ingestion đọc file CSV raw, parse bằng `csv.DictReader`, strip whitespace toàn bộ field.
- `data/raw/policy_export_dirty.csv`: file raw 10 bản ghi đầu vào của pipeline, gồm đủ các dirty pattern cần test — trùng chunk, thiếu trường, doc_id lạ, ngày sai định dạng, HR stale version, refund 14 ngày.
- Chạy `run_id=sprint1` để tạo baseline đo được cho toàn nhóm (10 raw → 6 cleaned + 4 quarantine).

**Kết nối với thành viên khác:**

Output của tôi (`cleaned_sprint1.csv`, `quarantine_sprint1.csv`, `manifest_sprint1.json`) là chuẩn đo ban đầu. Cleaning Owner (Phạm Anh Dũng) dùng số baseline `quarantine_records=4` để chứng minh R7–R9 có tác động `+3`. Pipeline Engineer (Trịnh Kế Tiến) dùng manifest để thiết lập chuỗi sprint1 → inject-bad → sprint4-final.

**Bằng chứng:**

`run_id=sprint1` ghi trong `artifacts/manifests/manifest_sprint1.json` với `raw_records=10`, `cleaned_records=6`, `quarantine_records=4`.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

**Quyết định:** Strip whitespace tại tầng ingestion thay vì để cleaning rules xử lý.

Trong `load_raw_csv()`, tôi áp dụng `.strip()` cho mọi field ngay khi đọc vào:

```python
rows.append({k: (v or "").strip() for k, v in r.items()})
```

Thay vì để whitespace lọt vào và từng cleaning rule phải tự xử lý, tôi chuẩn hóa một lần duy nhất ở điểm vào. Điều này tạo ra **contract rõ ràng giữa ingestion và cleaning**: các rule R1–R9 luôn nhận input đã strip, không cần guard thêm.

Ví dụ cụ thể: row 10 trong CSV có ngày `01/02/2026` (DD/MM/YYYY), nhưng không có trailing space hay hidden tab. Nếu không strip sớm, một ngày dạng ` 01/02/2026 ` sẽ không match regex `_DMY_SLASH` trong `_normalize_effective_date()` → bị quarantine nhầm lý do `invalid_effective_date_format` thay vì được normalize đúng sang ISO `2026-02-01`. Strip tại ingestion loại bỏ nguyên nhân gốc, cleaning rule chỉ cần xử lý đúng nghiệp vụ.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** Khi thiết kế `policy_export_dirty.csv`, tôi phát hiện row 5 (chunk_id=5) gây ra **hai lỗi chồng nhau**: `chunk_text` rỗng VÀ `effective_date` rỗng. Nếu pipeline kiểm tra theo thứ tự R2 trước R4, row này sẽ bị quarantine với lý do `missing_effective_date` — bỏ qua hoàn toàn lỗi thiếu nội dung chunk.

**Metric phát hiện:** Xem `quarantine_sprint1.csv` — row 5 chỉ xuất hiện với `reason=missing_effective_date`, không có `reason=missing_chunk_text`. Điều này đúng theo thứ tự rule: R2 (`effective_date`) check trước R4 (`chunk_text`), nên pipeline dừng tại lỗi đầu tiên gặp.

**Xử lý:** Tôi giữ nguyên thứ tự rule hiện tại và ghi rõ trong comment code rằng mỗi row chỉ nhận **một lý do quarantine duy nhất** (first-match). Điều này là thiết kế có chủ đích: dễ debug hơn là gộp nhiều lý do, và log quarantine không bị ambiguous. Row 5 vẫn là bằng chứng hợp lệ cho `missing_effective_date`.

---

## 4. Bằng chứng trước / sau (80–120 từ)

**Run Sprint1 — baseline** (`run_id=sprint1`, `artifacts/manifests/manifest_sprint1.json`):

```
raw_records=10
cleaned_records=6
quarantine_records=4
latest_exported_at=2026-04-10T08:00:00
```

**Nội dung `quarantine_sprint1.csv`** — 4 lý do baseline:

| chunk_id | doc_id | reason |
|---|---|---|
| 2 | policy_refund_v4 | duplicate_chunk_text |
| 5 | policy_refund_v4 | missing_effective_date |
| 7 | hr_leave_policy | stale_hr_policy_effective_date |
| 9 | legacy_catalog_xyz_zzz | unknown_doc_id |

6 bản ghi cleaned đi vào ChromaDB, bao gồm row 10 với ngày `01/02/2026` được normalize thành `2026-02-01` và row 3 ("14 ngày") được fix thành "7 ngày" bởi rule R6. Baseline này là điểm xuất phát để Cleaning Owner chứng minh R7–R9 tăng `quarantine_records` thêm 3 khi chạy với `more_inject`.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi sẽ thêm **schema validation tại ingestion**: kiểm tra các cột bắt buộc (`doc_id`, `chunk_text`, `effective_date`, `exported_at`) tồn tại trong CSV header trước khi xử lý từng row. Hiện tại nếu file thiếu cột `exported_at`, `load_raw_csv()` vẫn đọc thành công nhưng mọi row trả về `exported_at=""` — R9 quarantine toàn bộ mà không có thông báo rõ ràng về nguyên nhân cấu trúc file.
