# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Vương Hoàng Giang
**Vai trò:** Monitoring — Docs Owner
**Ngày nộp:** 15/4/2026  
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `monitoring/freshness_check.py` — Viết hàm `check_manifest_freshness`: đọc `latest_exported_at` từ manifest JSON, tính `age_hours`, so sánh với SLA 24h và trả về `("PASS"|"WARN"|"FAIL", detail_dict)`.
- `docs/runbook.md` — Điền 5 mục: Symptom (agent trả lời "14 ngày"), Detection (5 metric bao gồm E7/E8 mới), Diagnosis (5 bước manifest → quarantine → eval), Mitigation (rerun + rollback embed), Prevention (E7 + E8 đã tích hợp; chặn `--skip-validate` trên CI).
- `docs/pipeline_architecture.md` — Vẽ Mermaid flowchart 7 bước, bảng ranh giới trách nhiệm (Transform: 9 rules R1–R9; Quality: 8 expectations E1–E8), giải thích idempotency và liên hệ Day 09.
- `docs/data_contract.md` — Source map nguồn, schema cleaned với ràng buộc đầy đủ (làm rõ R8 quarantine < 20 ký tự vs E4 warn < 8 ký tự; exported_at bắt buộc theo R9 + E8), bảng 9 lý do quarantine, bảng canonical version.
- `docs/quality_report_template.md` — Điền số liệu thực, bổ sung dòng "8 expectations (E1–E8)" vào bảng tóm tắt, ghi nhận E7/E8 cũng kiểm tra trên inject-bad run, giải thích log cũ chỉ có E1–E6 do E7/E8 thêm sau.
- `reports/group_report.md` — Tổng hợp pipeline, bảng metric_impact R7/R8/R9/E7/E8, before/after retrieval, rủi ro còn lại.

**Kết nối với thành viên khác:**
Sau khi nhóm Embed Owner chạy xong `sprint4-final`, tôi lấy `manifest_sprint4-final.json`, `artifacts/eval/eval_clean.csv` và `artifacts/eval/grading_run.jsonl` để điền số liệu thực vào toàn bộ docs. Runbook tôi viết là tài liệu nhóm Inject Owner dùng để mô tả kịch bản Sprint 3.

**Bằng chứng:**
Manifest `run_id=sprint4-final` ghi rõ `skipped_validate: false`, `no_refund_fix: false` — đây là run sạch tôi dùng làm baseline cho toàn bộ docs. Log freshness từ pipeline: `freshness_check=FAIL {"age_hours": 120.239, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}`.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

**Quyết định:** `freshness_check.py` đọc từ manifest thay vì truy vấn trực tiếp ChromaDB.

Có hai cách đo freshness: (1) truy vấn metadata `exported_at` từ ChromaDB sau embed, hoặc (2) đọc `latest_exported_at` từ manifest JSON. Tôi chọn cách (2) vì manifest là artifact độc lập — không cần ChromaDB đang chạy, phù hợp chạy trong CI/CD hoặc cron job riêng. Hàm nhận `manifest_path` và `sla_hours` (default 24.0), tính `age_hours = (now - dt).total_seconds() / 3600` và trả về tuple `(status, detail_dict)` — dễ log, dễ assert trong test tự động.

Khi manifest thiếu hoặc không có timestamp hợp lệ, hàm trả `WARN` thay vì crash, để pipeline vẫn tiếp tục nhưng có cảnh báo rõ ràng:

```python
if not manifest_path.is_file():
    return "FAIL", {"reason": "manifest_missing", "path": str(manifest_path)}
if dt is None:
    return "WARN", {"reason": "no_timestamp_in_manifest"}
```

Thiết kế này tách freshness check ra khỏi embed layer, giúp Monitoring Owner có thể chạy kiểm tra bất kỳ lúc nào mà không phụ thuộc vào trạng thái ChromaDB.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Symptom:** Khi điền `runbook.md`, tôi phát hiện run `inject-bad` có `manifest_inject-bad.json` ghi `skipped_validate: true` và `no_refund_fix: true`, nhưng `cleaned_inject-bad.csv` vẫn chứa chunk "14 ngày làm việc". Agent trả lời sai ("14 ngày") dù pipeline log ghi "PIPELINE_OK".

**Diagnosis:** Flag `--no-refund-fix` tắt cleaning rule R6 (fix "14 ngày → 7 ngày"), và `--skip-validate` bỏ qua expectation E3 halt (`refund_no_stale_14d_window`, `violations=1`). Hai flag kết hợp cho phép chunk stale lọt vào ChromaDB mà không có cơ chế chặn nào. Lỗi không nằm ở code — đây là lỗ hổng thiết kế: pipeline cho phép bypass hoàn toàn guardrail chỉ bằng CLI flag, và log "PIPELINE_OK" vẫn xuất hiện nên khó phát hiện nếu không đọc manifest.

**Fix (ghi vào runbook mục Prevention):** Thêm alert khi manifest ghi `skipped_validate: true`; cấm flag này trên CI/CD nhánh production. Bằng chứng đo được: rerun `sprint4-final` cho `artifacts/eval/eval_clean.csv` với `hits_forbidden=no` trên toàn bộ câu hỏi grading.

Ngoài ra, khi cập nhật docs tôi phát hiện `quality_report_template.md` tham chiếu `eval_bad.csv` nhưng file này không có trong `artifacts/eval/` (chỉ có `eval_clean.csv` và `grading_run.jsonl`). Tôi đã sửa lại — mục before dùng expectation log từ run `inject-bad` (`expectation[refund_no_stale_14d_window] FAIL`) thay vì reference file không tồn tại.

---

## 4. Bằng chứng trước / sau (80–120 từ)

**Freshness check** — manifest `run_id=sprint4-final`:
```
freshness_check=FAIL
  latest_exported_at: 2026-04-10T08:00:00
  age_hours: 120.239  (vượt SLA 24h)
  reason: freshness_sla_exceeded
```

**Retrieval eval** — câu hỏi then chốt `q_refund_window` / `gq_d10_01`:

| run_id | `hits_forbidden` | `contains_expected` | Nguồn bằng chứng |
|--------|-----------------|--------------------|----|
| `inject-bad` | **yes** | yes | Expectation log: `refund_no_stale_14d_window FAIL (halt) violations=1` |
| `sprint4-final` | **no** | yes | `artifacts/eval/eval_clean.csv` + `grading_run.jsonl` |

Sau khi pipeline chạy đúng (`sprint4-final`), chunk "14 ngày làm việc" không còn trong index ChromaDB → retrieval trả về đúng "7 ngày làm việc" → `hits_forbidden` chuyển từ `yes` sang `no`. Xác nhận thêm từ `grading_run.jsonl`: `gq_d10_01 hits_forbidden=false, contains_expected=true, top1_doc_matches=true`.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi sẽ tích hợp `freshness_check.py` thành bước CI tự động: sau mỗi pipeline run, CI đọc manifest vừa tạo, gọi `check_manifest_freshness` và fail build nếu kết quả là `FAIL`. Hiện tại hàm đã trả về exit code phù hợp (`etl_pipeline.py freshness` exit 1 khi FAIL) — chỉ cần thêm bước CI gọi lệnh này và route alert đến `alert_channel` trong `data_contract.yaml` là hoàn chỉnh vòng lặp monitoring.