# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** E403 Team 6  
**Thành viên:**
| Tên | Vai trò (Day 10) | MSSV |
|-----|------------------|------|
| Trịnh Kế Tiến | Pipeline End-to-end + Embed Owner | 2A202600500 |
| Nguyễn Lê Trung | Ingestion Owner | 2A202600349 |
| Vương Hoàng Giang | Monitoring / Docs Owner | 2A202600349 |
| Phạm Anh Dũng | Cleaning Owner | 2A202600349 |
| Dương Quang Đông | Expectations (E7–E8) + Inject Sprint 3 | 2A202600445 |

**Ngày nộp:** 15/04/2026  
**Repo:** https://github.com/West2light/Day08-09-10_E403_Team6  
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Pipeline tổng quan

**Tóm tắt luồng:**

Pipeline ETL xử lý file export raw dạng CSV (`data/raw/policy_export_dirty.csv`) chứa 10 bản ghi chính sách công ty (Refund Policy v4, SLA P1 2026, IT Helpdesk FAQ, HR Leave Policy). Luồng xử lý end-to-end gồm 4 bước:

1. **Ingest**: Đọc CSV raw qua `load_raw_csv()` — thu được 10 raw records.
2. **Clean**: Hàm `clean_rows()` áp dụng 9 quy tắc (6 baseline + 3 mới R7–R9) để chuẩn hóa ngày ISO, loại doc_id lạ, fix refund 14→7 ngày, strip BOM, chặn chunk ngắn, reject thiếu exported_at. Kết quả: **6 cleaned + 4 quarantine**.
3. **Validate**: Module `run_expectations()` chạy 8 expectations (6 baseline + 2 mới E7–E8). Nếu có halt → pipeline dừng, không embed dữ liệu lỗi.
4. **Embed**: Upsert 6 chunks sạch vào ChromaDB collection `day10_kb` dùng model `all-MiniLM-L6-v2`. Strategy idempotent: upsert theo `chunk_id` + prune vector cũ không còn trong batch.

`run_id` được ghi trong mọi log và manifest JSON tại `artifacts/manifests/`.

**Lệnh chạy một dòng:**

```bash
python etl_pipeline.py run --run-id sprint4-final
```

---

## 2. Cleaning & expectation

Baseline đã có 6 rule (allowlist doc_id, normalize effective_date, HR stale <2026, missing chunk_text, dedupe, refund 14→7). Nhóm thêm **3 rule mới** + **2 expectation mới**:

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới | Trước (sprint1) | Sau inject (inject-bad) | Chứng cứ |
|-------------------------|:-----:|:-----:|------|
| **R7** `strip_bom_control_chars` | quarantine=4 | Quarantine tăng khi inject BOM (row 11 trong more_inject) | `transform/cleaning_rules.py` L125–L135 |
| **R8** `min_chunk_content_length(<20)` | quarantine=4 | Quarantine tăng khi inject chunk "Qua ngan" (row 12) | `transform/cleaning_rules.py` L137–L145 |
| **R9** `reject_missing_exported_at` | quarantine=4 | Quarantine tăng khi inject row thiếu exported_at (row 13) | `transform/cleaning_rules.py` L147–L152 |
| **E7** `no_bom_control_in_chunk_text` (halt) | OK | FAIL khi bypass R7 | `quality/expectations.py` L115–L130 |
| **E8** `all_rows_have_exported_at` (warn) | OK | FAIL khi bypass R9 | `quality/expectations.py` L132–L143 |

**Rule chính (baseline + mở rộng):**

- R1: allowlist doc_id → quarantine unknown_doc_id
- R2–R3: normalize effective_date ISO + quarantine invalid format
- R4: HR leave policy effective_date < 2026-01-01 → quarantine stale
- R5: missing chunk_text → quarantine
- R6: deduplicate chunk_text
- R7–R9: BOM strip, min length 20, reject missing exported_at **(MỚI)**

**Ví dụ 1 lần expectation fail và cách xử lý:**

Khi chạy `python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate`:
```
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1
WARN: expectation failed but --skip-validate -> continuing embed (only for Sprint 3 demo).
```
Expectation E3 phát hiện 1 chunk refund còn chứa "14 ngày làm việc". Nếu không có `--skip-validate`, pipeline sẽ HALT — bảo vệ ChromaDB khỏi dữ liệu sai.

---

## 3. Before / after ảnh hưởng retrieval hoặc agent

**Kịch bản inject (Sprint 3):**

Nhóm cố ý tắt rule fix refund 14→7 ngày bằng flag `--no-refund-fix` và bỏ qua halt bằng `--skip-validate`. Dữ liệu bẩn (chunk chứa "14 ngày làm việc") được embed trực tiếp vào ChromaDB.

**Kết quả định lượng (từ CSV):**

| Câu hỏi | Metric | eval_bad (inject) | eval_clean (sprint4-final) |
|----------|--------|:---:|:---:|
| q_refund_window | contains_expected | yes | yes |
| q_refund_window | **hits_forbidden** | **yes** ❌ | **no** ✅ |
| q_leave_version | contains_expected | yes | yes |
| q_leave_version | top1_doc_expected | yes | yes |

**Phân tích:** Khi inject dữ liệu bẩn, câu `q_refund_window` hit forbidden keyword ("14 ngày làm việc") → Agent nhận thông tin mâu thuẫn. Sau clean pipeline (`sprint4-final`), `hits_forbidden=no`.

**Grading run chính thức** (`artifacts/eval/grading_run.jsonl`):

| ID | Câu hỏi | contains_expected | hits_forbidden | top1_doc_matches | Điểm |
|----|---------|:-:|:-:|:-:|:---:|
| `gq_d10_01` | Hoàn tiền bao nhiêu ngày? | ✅ true | ✅ false | ✅ true | 4đ |
| `gq_d10_02` | SLA P1 bao lâu? | ✅ true | — | ✅ true | 3đ |
| `gq_d10_03` | Phép năm 2026? | ✅ true | ✅ false | ✅ true | 3đ |

**3/3 câu PASS — đạt hạng MERIT.**

---

## 4. Freshness & monitoring

Module `monitoring/freshness_check.py` đọc manifest JSON và so sánh `latest_exported_at` với thời gian hiện tại. SLA mặc định: **24 giờ**.

Kết quả chạy trên manifest `sprint4-final`:
```
freshness_check=FAIL {
  "latest_exported_at": "2026-04-10T08:00:00",
  "age_hours": 123.025,
  "sla_hours": 24.0,
  "reason": "freshness_sla_exceeded"
}
```

FAIL là hợp lý vì CSV mẫu có `exported_at` ngày 10/04, kiểm tra ngày 15/04 → cách 123 giờ > SLA 24 giờ. Production cần cronjob mỗi 2–4h.

---

## 5. Liên hệ Day 09

Dữ liệu sau embed nằm trong ChromaDB collection `day10_kb`. Collection này phục vụ Retrieval Worker và Synthesis Worker trong kiến trúc multi-agent Day 09. Pipeline ETL Day 10 đóng vai trò "upstream guardian": mọi dữ liệu từ hệ thống nguồn phải qua Clean → Validate → Embed trước khi Agent truy vấn.

---

## 6. Rủi ro còn lại & việc chưa làm

- **Freshness SLA**: Dữ liệu lab mẫu cách 123 giờ → luôn FAIL. Production cần cronjob tự động refresh.
- **Versioning VectorDB**: Upsert + prune thủ công. Cần snapshot/rollback mechanism cho collection Chroma.
- **Expectation framework**: Dùng code Python thuần. Nên chuyển sang Great Expectations hoặc Pandera cho reporting HTML.
- **Data encoding**: File `policy_export_dirty_more_inject.csv` dùng tiếng Việt không dấu gây lỗi grading. Đã fix về file gốc có dấu.
