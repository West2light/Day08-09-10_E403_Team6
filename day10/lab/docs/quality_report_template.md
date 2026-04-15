# Quality report — Lab Day 10 (nhóm)

**run_id:** sprint4-final  
**Ngày:** 15/04/2026

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (inject-bad) | Sau (sprint4-final) | Ghi chú |
|--------|-------------------|---------------------|---------|
| raw_records | 10 | 10 | `data/raw/policy_export_dirty.csv` |
| cleaned_records | 6 | 6 | Sau khi lọc quarantine |
| quarantine_records | 4 | 4 | duplicate, missing_date, stale_hr, unknown_doc_id |
| Expectation halt? | **YES** — E3 FAIL (`violations=1`) | **NO** — tất cả PASS | `inject-bad` bật `--skip-validate` nên chunk sai lọt qua |

**Chi tiết 4 chunk bị cách ly (quarantine):**

| chunk_id | doc_id | Lý do cách ly |
|----------|--------|---------------|
| 2 | policy_refund_v4 | `duplicate_chunk_text` — nội dung trùng chunk 1 |
| 5 | policy_refund_v4 | `missing_effective_date` — thiếu ngày hiệu lực |
| 7 | hr_leave_policy | `stale_hr_policy_effective_date` — bản HR 2025 (effective_date = 2025-01-01 < 2026-01-01) |
| 9 | legacy_catalog_xyz_zzz | `unknown_doc_id` — không thuộc allowlist |

---

## 2. Before / after retrieval (bắt buộc)

Nguồn dữ liệu: `artifacts/eval/eval_bad.csv` (trước) và `artifacts/eval/eval_clean.csv` (sau).

### Câu hỏi then chốt: refund window (`q_refund_window`)

**Câu hỏi:** *"Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền kể từ khi xác nhận đơn?"*

**Trước — run `inject-bad` (`eval_bad.csv`):**
```
top1_doc_id=policy_refund_v4
top1_preview=Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.
contains_expected=yes  |  hits_forbidden=YES  |  top_k_used=3
```
> Chunk chứa "14 ngày làm việc" (bản cũ policy-v3) có mặt trong ChromaDB — retrieval bao gồm cả chunk sai khiến `hits_forbidden=yes`.

**Sau — run `sprint4-final` (`eval_clean.csv`):**
```
top1_doc_id=policy_refund_v4
top1_preview=Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.
contains_expected=yes  |  hits_forbidden=NO  |  top_k_used=3
```
> Chunk "14 ngày" đã bị xử lý bởi rule R6 (`apply_refund_window_fix`) — không còn trong index.

---

### Merit: versioning HR — `q_leave_version`

**Câu hỏi:** *"Theo chính sách nghỉ phép hiện hành (2026), nhân viên dưới 3 năm kinh nghiệm được bao nhiêu ngày phép năm?"*

**Trước — run `inject-bad` (`eval_bad.csv`):**
```
top1_doc_id=hr_leave_policy
top1_preview=Nhân viên dưới 3 năm kinh nghiệm được 12 ngày phép năm theo chính sách 2026.
contains_expected=yes  |  hits_forbidden=no  |  top1_doc_expected=yes  |  top_k_used=3
```

**Sau — run `sprint4-final` (`eval_clean.csv`):**
```
top1_doc_id=hr_leave_policy
top1_preview=Nhân viên dưới 3 năm kinh nghiệm được 12 ngày phép năm theo chính sách 2026.
contains_expected=yes  |  hits_forbidden=no  |  top1_doc_expected=yes  |  top_k_used=3
```
> Bản HR cũ (10 ngày, effective_date=2025-01-01) đã bị cách ly bởi rule R3 (`stale_hr_policy_effective_date`). Cả hai run đều trả về bản 2026 đúng — xác nhận versioning hoạt động chính xác.

---

## 3. Freshness & monitor

**Kết quả:** `FAIL`

```json
{
  "latest_exported_at": "2026-04-10T08:00:00",
  "age_hours": 120.239,
  "sla_hours": 24.0,
  "reason": "freshness_sla_exceeded"
}
```

**SLA chọn:** 24 giờ — phù hợp với môi trường nội bộ cần cập nhật chính sách hàng ngày (theo `contracts/data_contract.yaml`).

**Giải thích:** Timestamp `latest_exported_at = 2026-04-10T08:00:00` (thời điểm export raw CSV) cách thời điểm chạy lab (2026-04-15) khoảng **120 giờ**, vượt SLA 24 giờ → flag FAIL. Trong môi trường production, pipeline batch sẽ chạy định kỳ (mỗi 2-6 giờ) để giữ `age_hours` trong ngưỡng.

**Module:** `monitoring/freshness_check.py` — đọc trường `latest_exported_at` từ manifest JSON và so sánh với `datetime.now(UTC)`.

---

## 4. Corruption inject (Sprint 3)

**Lệnh inject:**
```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
```

**Các lỗi được cố ý inject:**

| Loại lỗi | Chunk / Dữ liệu bị inject | Cách phát hiện |
|----------|--------------------------|----------------|
| **Stale refund window** | `policy_refund_v4` — chunk chứa "14 ngày làm việc" (bản policy-v3) không bị fix do `--no-refund-fix` | Expectation **E3** `refund_no_stale_14d_window` FAIL (`violations=1`, severity: halt); eval `hits_forbidden=yes` |
| **Skip validation** | Toàn bộ pipeline bỏ qua expectation suite do `--skip-validate` | So sánh `manifest.skipped_validate=true` (inject-bad) vs `false` (sprint4-final) |
| **Chunk sai lọt vào embed** | Chunk "14 ngày" được nạp lên ChromaDB thay vì bị chặn | `eval_bad.csv`: câu hỏi `q_refund_window` có `hits_forbidden=yes` — khác với `eval_clean.csv` |

**Bài học:** Khi `--skip-validate` được bật, expectation halt không có hiệu lực → chunk sai lọt vào vector store → retrieval trả về thông tin sai cho agent/user. Đây là lỗ hổng cần được chặn ở CI/CD (không cho phép `--skip-validate` trên nhánh production).

---

## 5. Hạn chế & việc chưa làm

- **Great Expectations / Pandera chưa dùng:** Expectation suite hiện tại được viết thủ công (`quality/expectations.py`). Lý tưởng nên dùng thư viện chuẩn để có dashboard, profiling tự động và tích hợp CI tốt hơn.
- **Versioning ChromaDB còn thủ công:** Khi upsert theo `chunk_id`, các chunk bị xóa ở nguồn chỉ được prune thủ công — dễ gây vector "ma" trong kiến trúc HA lớn.
- **`owner_team` và `alert_channel` chưa điền:** `contracts/data_contract.yaml` còn placeholder `__TODO__` — chưa gắn owner cụ thể theo từng `doc_id`.
- **Freshness alert chưa tích hợp CI:** `freshness_check.py` chỉ chạy độc lập, chưa fail build tự động khi `age_hours > sla_hours`.
- **Eval chỉ dùng keyword matching:** `eval_retrieval.py` kiểm tra top-k bằng `must_contain_any` / `must_not_contain` — chưa có LLM-based eval để đánh giá chất lượng câu trả lời cuối cùng.
