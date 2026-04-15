# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Dương Quang Đông  
**MSSV:** 2A202600445  
**Vai trò:** Sprint 2 (Expectations mới) + Sprint 3 nửa đầu (Inject corruption & before/after)  
**Ngày nộp:** 15/04/2026

---

## 1. Tôi phụ trách phần nào?

**File / module:**

- `quality/expectations.py` — Tôi thêm **E7** (`no_bom_control_in_chunk_text`, severity `halt`) và **E8** (`all_rows_have_exported_at`, severity `warn`) vào expectation suite. E7 ngăn toàn bộ pipeline embed nếu chunk_text vẫn còn ký tự BOM/control sau khi cleaning. E8 cảnh báo nếu bất kỳ row nào thiếu `exported_at` — thiếu trường này làm freshness check không có timestamp để tính age.

- `transform/cleaning_rules.py` — Hỗ trợ phần cleaning tương ứng: R7 (`strip_bom_control_chars`), R8 (`min_chunk_content_length`), R9 (`reject_missing_exported_at`) để đảm bảo E7 và E8 không bao giờ nhận vào dữ liệu bẩn từ phía trên.

- Sprint 3: Tôi chạy lệnh inject (`run_id=inject-bad`) để tạo ra `eval_bad.csv` làm bằng chứng "trước", sau đó chạy lại pipeline sạch để có `eval_clean.csv` làm bằng chứng "sau".

**Kết nối với thành viên khác:**

Cleaning rules R7–R9 do tôi thêm phải đồng bộ với expectation E7–E8. Nếu cleaning strip BOM nhưng expectation không kiểm tra lại thì vẫn có thể lọt chunk bẩn (ví dụ khi chạy `--skip-validate`). Tôi trao đổi với người phụ trách embed để đảm bảo flag `halt=True` được bắt đúng trong `etl_pipeline.py` — block embed, không cho dữ liệu lỗi lên ChromaDB.

**Bằng chứng — đoạn code trực tiếp trong file:**

```python
# quality/expectations.py — E7 (line 115–130)
bom_rows = [
    r
    for r in cleaned_rows
    if re.search(r"[\x00-\x08\ufeff]", r.get("chunk_text") or "")
]
ok7 = len(bom_rows) == 0
results.append(ExpectationResult(
    "no_bom_control_in_chunk_text", ok7, "halt",
    f"bom_rows={len(bom_rows)}"
))

# quality/expectations.py — E8 (line 132–143)
missing_export = [r for r in cleaned_rows if not (r.get("exported_at") or "").strip()]
ok8 = len(missing_export) == 0
results.append(ExpectationResult(
    "all_rows_have_exported_at", ok8, "warn",
    f"missing_exported_at_rows={len(missing_export)}"
))
```

---

## 2. Một quyết định kỹ thuật

Quyết định phân cấp severity giữa E7 và E8 là không tầm thường.

**E7 → `halt`:** BOM/control character trong `chunk_text` là lỗi dữ liệu nghiêm trọng — nếu vector embedding nhận vào chunk có `\ufeff` ở đầu, similarity score sẽ bị lệch vì tokenizer xử lý ký tự ẩn khác nhau giữa các model. Hệ quả: retrieval trả về chunk sai thứ tự ưu tiên, agent tư vấn sai policy. Do đó tôi quyết định `halt` — block toàn bộ pipeline, không embed.

**E8 → `warn`:** Thiếu `exported_at` ảnh hưởng freshness check nhưng không làm sai nội dung policy. Một chunk vẫn có thể hữu ích cho retrieval dù không biết chính xác khi nào nó được export. Vì vậy tôi chọn `warn` — pipeline vẫn chạy tiếp, nhưng log ghi nhận để ops team biết mà điều tra nguồn.

Nếu đổi E8 thành `halt` thì mọi run thiếu timestamp sẽ chặn cả pipeline, gây over-blocking trong giai đoạn migration data — đây là trade-off có chủ đích.

---

## 3. Một lỗi / anomaly đã xử lý

**Symptom:** Khi chạy inject (`run_id=inject-bad`), chunk sau đây lọt qua cleaning và vào ChromaDB:

```
chunk_id: policy_refund_v4_2_45eb043f3cd16916
chunk_text: "Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc
             kể từ xác nhận đơn (ghi chú: bản sync cũ policy-v3 — lỗi migration)."
```

**Nguyên nhân:** Flag `--no-refund-fix` tắt rule fix 14→7, flag `--skip-validate` bỏ qua HALT từ expectation `refund_no_stale_14d_window`. Chunk "14 ngày" này không bị quarantine vì nó không vi phạm các rule khác (doc_id hợp lệ, date đúng ISO, text đủ dài, có `exported_at`).

**Phát hiện:** Sau khi chạy `eval_retrieval.py`, file `eval_bad.csv` báo `hits_forbidden=yes` cho câu `q_refund_window` — retrieval engine đã kéo lên chunk chứa "14 ngày" lẫn với chunk đúng "7 ngày".

**Fix:** Chạy lại pipeline sạch (không có flag inject). Pipeline halt đúng chỗ khi expectation `refund_no_stale_14d_window` phát hiện `violations=1`, block embed, ChromaDB chỉ còn chunk đúng.

---

## 4. Bằng chứng trước / sau

**Trước — `run_id=inject-bad`** (`artifacts/eval/eval_bad.csv`):

```
question_id,    contains_expected, hits_forbidden, top1_doc_expected
q_refund_window,       yes,              yes,
q_leave_version,       yes,              no,             yes
```

Cột `hits_forbidden=yes` trên `q_refund_window` xác nhận: top-k retrieval kéo lên cả chunk "14 ngày làm việc" — dữ liệu bẩn đã ô nhiễm vector store.

**Sau — `run_id=sprint4-final`** (`artifacts/eval/eval_clean.csv`):

```
question_id,    contains_expected, hits_forbidden, top1_doc_expected
q_refund_window,       yes,              no,
q_leave_version,       yes,              no,             yes
```

Cột `hits_forbidden=no` — pipeline sạch đã prune hết chunk cũ (`embed_prune_removed`), chỉ còn "7 ngày làm việc" trong ChromaDB. Câu `q_leave_version` cũng `top1_doc_expected=yes` — HR policy đúng version 2026 (12 ngày) được truy xuất chính xác.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ thêm expectation **E9: kiểm tra phân phối doc_id** — ví dụ yêu cầu tối thiểu mỗi `doc_id` trong allowlist phải có ít nhất 1 chunk trong cleaned output. Hiện tại nếu toàn bộ chunk của một document bị quarantine (ví dụ import lỗi), pipeline vẫn `exit 0` nhưng agent sẽ không có knowledge về document đó — lỗi âm thầm, khó debug sau khi lên production.
