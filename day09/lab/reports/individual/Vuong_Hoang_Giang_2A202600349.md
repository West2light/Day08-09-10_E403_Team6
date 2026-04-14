# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Vương Hoàng Giang 
**Vai trò trong nhóm:** Supervisor Owner  
**Ngày nộp:** 14/04/2026 
**Độ dài ước tính:** ~650 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Trong Lab Day 09, với vai trò là Supervisor Owner, tôi chịu trách nhiệm độc quyền cho phần kiến trúc lõi điều phối của hệ thống: thiết kế và lập trình file `graph.py` (Sprint 1). 

Cụ thể, tôi đã định nghĩa cấu trúc `AgentState` để làm bộ nhớ dùng chung (shared state) cho toàn bộ graph, chứa các trường như `task`, `route_reason`, `retrieved_chunks`, và `workers_called`. Tiếp đó, tôi implement các hàm cốt lõi gồm `supervisor_node()` và logic điều hướng `route_decision()`. Chức năng này đóng vai trò như một người quản lý phân việc: nhận câu hỏi đầu vào, đánh giá, và "gửi gắm" cho đúng chuyên gia (như Retrieval Worker hay Policy Tool Worker).

Công việc của tôi là "xương sống" của hệ thống. Tôi kết nối trực tiếp với phần của Worker Owner bằng cách định nghĩa chuẩn đầu vào/đầu ra để họ có thể dễ dàng "cắm" các file `retrieval.py` hay `synthesis.py` vào graph mà tôi đã dựng sẵn.

**Bằng chứng:** Các commit ban đầu khởi tạo `graph.py`, định nghĩa class `AgentState` và logic routing mang tên tôi trên repository của nhóm.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi quyết định sử dụng **Keyword/Rule-based Routing** (Điều hướng bằng luật và từ khóa) trong hàm `route_decision()` thay vì dùng LLM làm Classifier để phân loại task.

**Lý do & Các lựa chọn thay thế:** 
Ban đầu, tôi cân nhắc việc truyền câu hỏi vào một LLM prompt yêu cầu nó chọn giữa `retrieval_worker` và `policy_tool_worker`. Lựa chọn này nghe có vẻ "AI" và thông minh hơn. Tuy nhiên, khi đọc kỹ yêu cầu bài Lab (cần ghi nhận `route_reason` minh bạch, hệ thống không được chậm trễ), tôi nhận thấy việc dùng LLM cho một công việc phân nhánh cấp 1 là quá lãng phí và chậm (~800ms đến 1s cho mỗi query). 
Vì vậy, tôi chọn Rule-based. Nếu trong `task` có các từ khóa như "hoàn tiền", "refund", "cấp quyền", tôi lập tức route sang `policy_tool_worker`. Nếu có "P1", "escalation", ưu tiên chuyển sang `retrieval_worker`.

**Trade-off đã chấp nhận:** 
Đánh đổi lại, supervisor của tôi sẽ hơi cứng nhắc. Nếu người dùng dùng từ đồng nghĩa mà không nằm trong tập keyword, hệ thống có thể route chưa tối ưu. Nhưng bù lại, tốc độ điều hướng gần như tức thời (0ms) và logic hoàn toàn kiểm soát được 100%.

**Bằng chứng từ trace/code:**
Trích xuất từ trace đối với câu hỏi gq01 (Ticket P1):
```json
"supervisor_route": "retrieval_worker",
"route_reason": "task contains 'P1' / 'escalation' keyword",
```
Trích xuất logic trong `graph.py`:
```python
def route_decision(state: AgentState):
    task = state["task"].lower()
    if any(kw in task for kw in ["hoàn tiền", "refund", "cấp quyền", "emergency"]):
        return "policy_tool_worker", "task contains policy/access keyword"
    elif any(kw in task for kw in ["p1", "escalation", "ticket"]):
        return "retrieval_worker", "task contains P1/escalation keyword"
    ...
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Supervisor không thể điều hướng các câu hỏi nằm ngoài tập keyword định trước, gây ra lỗi Crash Pipeline (Invalid node / Graph End bất ngờ).

**Symptom (pipeline làm gì sai?):** 
Khi nhóm chạy thử file `eval_trace.py` với các test questions ở Sprint 4, một số câu hỏi không chứa keyword quen thuộc (ví dụ quy định nghỉ phép của nhân viên thử việc). Lúc này pipeline ném ra exception và dừng hoàn toàn vì không biết đi tới node nào tiếp theo.

**Root cause:** 
Lỗi nằm ở hàm `route_decision()` trong `graph.py` do tôi lập trình. Tôi mải mê thiết lập các nhánh `if / elif` cho các trường hợp khẩn cấp (SLA, Refund, Policy) mà quên mất không định nghĩa nhánh `else` (default fallback). Do đó, hàm trả về `None`, và LangGraph (hoặc custom graph) không hiểu `None` là node nào.

**Cách sửa:** 
Tôi đã bổ sung một nhánh `else` mặc định ở cuối luồng để đẩy toàn bộ các query không xác định được intent rõ ràng về `retrieval_worker`. Đây là phương án an toàn nhất vì bản chất RAG luôn cần tìm kiếm tài liệu trước tiên nếu không biết phải gọi Tool gì.

**Bằng chứng trước/sau:**
*Code trước khi sửa:*
```python
    elif "mã lỗi" in task:
        return "human_review", "unknown error code"
    # Thiếu return mặc định
```
*Code sau khi sửa:*
```python
    elif "mã lỗi" in task:
        return "human_review", "unknown error code"
    else:
        return "retrieval_worker", "fallback to default retrieval"
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Tôi đã triển khai được bộ khung (Orchestrator) rất nhanh và chạy ổn định. Việc định nghĩa `AgentState` rõ ràng và cấu trúc rule-based minh bạch giúp dễ dàng ghi lại các trường như `route_reason` đáp ứng đúng yêu cầu khắt khe của grading trace.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Graph của tôi hiện tại khá "phẳng" (chỉ gồm supervisor điều hướng 1 chiều). Tôi chưa làm được luồng kiểm tra đệ quy (ví dụ: chạy policy worker xong thấy thiếu thông tin thì vòng ngược lại retrieval worker). 

**Nhóm phụ thuộc vào tôi ở đâu?** 
Toàn bộ nhóm (đặc biệt là Worker Owner và Eval Owner) bị block hoàn toàn nếu file `graph.py` của tôi không chạy được, vì không có graph thì các worker không thể giao tiếp với nhau để ra được output cuối cùng.

**Phần tôi phụ thuộc vào thành viên khác:** 
Tôi phụ thuộc vào Worker Owner trong việc thống nhất các schema trong `worker_contracts.yaml` để biết chính xác cần đẩy dữ liệu gì vào `state` cho họ, và họ sẽ trả về key gì (ví dụ `policy_result` hay `retrieved_chunks`).

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Nếu có thêm 2 giờ, tôi sẽ cải tiến `route_decision` thành một **Semantic Router** nhẹ (dùng mô hình embedding nhỏ hoặc LLM prompt siêu nhanh) thay vì chỉ check keyword thô cứng.
Lý do: Trong log của `grading_run.json` hoặc test traces, sẽ có trường hợp người dùng hỏi *"quy định trả lại tiền"* thay vì *"hoàn tiền"*. Do luật keyword cứng của tôi, câu hỏi này bị đẩy vào nhánh fallback `retrieval_worker` thay vì `policy_tool_worker`, làm giảm hiệu quả xử lý các ngoại lệ như Flash Sale. Cải tiến thành Semantic Router sẽ giải quyết triệt để vấn đề này.