# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Dương Quang Đông  
**Vai trò trong nhóm:** MCP Owner  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

Tôi phụ trách toàn bộ phần MCP trong Sprint 3, tập trung vào file [mcp_server.py](../mcp_server.py). Tôi đã hoàn thiện bốn tool trong `TOOL_REGISTRY`: `search_kb`, `get_ticket_info`, `check_access_permission` và `create_ticket`, cùng với hai hàm giao tiếp chuẩn là `list_tools()` và `dispatch_tool()`. Trong đó, hai tool bắt buộc của đề bài là `search_kb(query, top_k)` và `get_ticket_info(ticket_id)` là phần chính để worker khác có thể gọi capability ngoài thay vì hard-code logic. Đoạn code dưới đây là phần tôi trích trực tiếp từ file để thể hiện rõ lớp discovery và dispatch:

```python
TOOL_REGISTRY = {
    "search_kb": search_kb,
    "get_ticket_info": get_ticket_info,
    "check_access_permission": check_access_permission,
    "create_ticket": create_ticket,
}

def list_tools() -> list:
    return list(TOOL_SCHEMAS.values())

def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    if tool_name not in TOOL_REGISTRY:
        return {
            "error": f"Tool '{tool_name}' không tồn tại. Available: {list(TOOL_REGISTRY.keys())}"
        }
    tool_fn = TOOL_REGISTRY[tool_name]
    return tool_fn(**tool_input)
```

Công việc của tôi không đứng riêng lẻ. Nó nối trực tiếp với [workers/policy_tool.py](../workers/policy_tool.py) qua `_call_mcp_tool()` và `_record_mcp_call()`: policy worker sẽ gọi `dispatch_tool()` khi cần tra cứu KB hoặc ticket, rồi ghi lại kết quả vào `mcp_tools_used`, `mcp_tool_called`, và `mcp_result`. Điều này khớp đúng với mô tả trong [mcp_server.py](../mcp_server.py), nơi phần header nói rõ agent phải gọi `dispatch_tool()` thay vì hard-code từng API, và phần schema đã công khai sẵn hai tool chính là `search_kb(query, top_k)` và `get_ticket_info(ticket_id)`.

Tôi cũng phối hợp với supervisor ở [graph.py](../graph.py) để `route_reason` nói rõ khi nào hệ thống chọn MCP. Trace [run_20260414_175340.json](../artifacts/traces/run_20260414_175340.json) cho thấy một query khẩn cấp đã gọi cả `search_kb` và `get_ticket_info`, nên phần MCP của tôi đã thực sự đi vào pipeline chứ không chỉ dừng ở mock hàm. Ở run này, lịch sử xử lý ghi rất rõ `called MCP search_kb` rồi `called MCP get_ticket_info`, nên khi đọc trace tôi có thể chứng minh được MCP không phải phần “trưng bày”.

Ngoài bản mock, tôi còn viết thêm bản HTTP thử nghiệm ở [day09/extras/mcp_http_server.py](../../../extras/mcp_http_server.py). File này dùng `FastMCP`, khai báo `tool_search_kb()` và `tool_get_ticket_info()`, rồi ghép với `FastAPI`/SSE để tiến gần hơn hướng Advanced. Trong code, tôi đã tách tool rất rõ: `tool_search_kb()` chỉ wrap `search_kb(query, top_k)` và `tool_get_ticket_info()` chỉ wrap `get_ticket_info(ticket_id)`. Tôi không chọn nó để nộp vì đây mới là bản thử nghiệm local, chưa thật sự ổn định bằng mock in-process và chưa đem lại lợi ích rõ ràng hơn cho bài lab. Phần dưới là đoạn code trích trực tiếp từ file HTTP thử nghiệm:

```python
mcp = FastMCP("ticket-mcp-server")
from mcp_server import search_kb, get_ticket_info

@mcp.tool()
def tool_search_kb(query: str, top_k: int = 3) -> str:
    return str(search_kb(query, top_k))

@mcp.tool()
def tool_get_ticket_info(ticket_id: str) -> str:
    return str(get_ticket_info(ticket_id))

app = FastAPI()
from mcp.server.sse import SseServerTransport
sse = SseServerTransport("/messages")

@app.get("/sse")
async def handle_sse():
    async with sse.connect_sse() as streams:
        await mcp.run_stdio_async(streams[0], streams[1])
```

## 2. Tôi đã ra một quyết định kỹ thuật gì?

Quyết định chính của tôi là chọn **Standard mock MCP in-process** thay vì cố đẩy ngay sang HTTP MCP server. Lựa chọn thay thế là dựng server FastAPI/SSE rồi cho `policy_tool.py` gọi qua client thật. Tôi đã thử hướng đó, và bản nháp nằm ở [day09/extras/mcp_http_server.py](../../../extras/mcp_http_server.py), nhưng với bối cảnh bài lab và thời gian ngắn, nó tạo thêm quá nhiều rủi ro: phải chạy thêm một tiến trình riêng, xử lý async lifecycle, và dễ phát sinh lỗi tích hợp giữa server/client. Tôi nhìn vào chính file HTTP thử nghiệm của mình thì thấy ngay sự khác nhau: phần trên khai báo `mcp = FastMCP("ticket-mcp-server")`, phần dưới lại phải ghép thêm `FastAPI`, `SseServerTransport("/messages")`, rồi `@app.get("/sse")` mới cố mở đường cho client SSE. So với bản mock in-process, đó là một lớp vận hành nữa mà lab này không bắt buộc phải có.

Với mock in-process, tôi giữ được một nguồn sự thật duy nhất, trace ngắn và dễ đọc, và worker vẫn thể hiện đúng tinh thần MCP: không truy cập dữ liệu trực tiếp mà đi qua `dispatch_tool()`. Cách làm này cũng khớp với phần comment trong [mcp_server.py](../mcp_server.py), nơi tool discovery và execution được phân tách thành `list_tools()` và `dispatch_tool()` thay vì buộc policy worker biết chi tiết implementation của từng nguồn dữ liệu.

Trade-off tôi chấp nhận là không lấy bonus của bản HTTP, nhưng đổi lại pipeline chạy ổn định và dễ chấm hơn. Điều này phản ánh rõ ở trace [run_20260414_175340.json](../artifacts/traces/run_20260414_175340.json): policy worker vừa gọi `search_kb` để lấy context, vừa gọi `get_ticket_info` để bổ sung thông tin incident P1, trong khi `route_reason` đã ghi rõ đây là trường hợp “choose MCP=yes”. Với tôi, đó là đủ để đạt đúng mục tiêu Sprint 3 mà không tạo thêm một lớp hỏng hóc mới.

## 3. Tôi đã sửa một lỗi gì?

Lỗi tôi sửa là bug logging của trace MCP: ban đầu hệ thống chỉ lưu tốt `mcp_tools_used`, còn hai alias mà README yêu cầu là `mcp_tool_called` và `mcp_result` chưa được chuẩn hóa đầy đủ. Symptom là khi đọc trace, người xem phải tự suy luận từ raw object chứ không thể nhìn ngay thấy tool nào đã được gọi và output của nó là gì. Trace [run_20260414_175340.json](../artifacts/traces/run_20260414_175340.json) là bằng chứng tốt nhất vì nó lưu cả hai lần gọi MCP trong cùng một run: `search_kb` để tìm context và `get_ticket_info` để bóc thêm chi tiết ticket P1.

Root cause nằm trong tầng worker logic, cụ thể là phần ghi log sau mỗi lần gọi tool. Tôi sửa bằng cách chuẩn hóa `_record_mcp_call()` trong [workers/policy_tool.py](../workers/policy_tool.py): mỗi lần gọi MCP sẽ append đồng thời vào ba field, giữ schema cũ nhưng bổ sung alias trace mới để downstream evaluator và người chấm đọc được ngay. Sau sửa, trace [run_20260414_175340.json](../artifacts/traces/run_20260414_175340.json) đã có đủ dấu vết của hai tool call thực tế, còn các trace cũ như [run_20260414_173026.json](../artifacts/traces/run_20260414_173026.json) cho thấy vì sao alias này cần thiết: nếu chỉ giữ raw output thì trace rất khó kiểm tra nhanh.

## 4. Tôi tự đánh giá đóng góp của mình

Tôi làm tốt nhất ở chỗ giữ phần MCP đơn giản nhưng đủ dùng: tool discovery rõ ràng, dispatch gọn, và log đủ để debug. Tôi cũng làm tốt phần gắn MCP vào policy worker mà không phá contract hiện có của nhóm. Điểm tôi làm chưa tốt là đã mất thời gian thử bản HTTP server riêng trước khi chốt Standard, nên nhịp làm việc ban đầu hơi phân tán. Nhìn lại, [mcp_http_server.py](../../../extras/mcp_http_server.py) là một bản nháp tốt để chứng minh tôi có thử hướng Advanced, nhưng nếu dùng nó làm bản nộp chính thì độ phức tạp vận hành sẽ cao hơn giá trị thực tế của lab.

Nhóm phụ thuộc vào tôi ở chỗ mọi câu hỏi cần tra KB hoặc ticket đều phải đi qua MCP của tôi; nếu `mcp_server.py` hoặc logging schema lỗi, policy worker và trace owner sẽ bị kẹt. Ngược lại, tôi phụ thuộc vào Supervisor Owner để route đúng sang policy worker, và phụ thuộc vào Worker Owner để worker trả state đúng key, đặc biệt là `needs_tool`, `retrieved_chunks`, và `policy_result`.

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ hoàn thiện nốt bản HTTP MCP server để đạt bonus, nhưng chỉ làm sau khi tách rõ health check và client timeout. Tôi muốn làm việc đó vì trace [run_20260414_175340.json](../artifacts/traces/run_20260414_175340.json) cho thấy phần MCP đã có nhu cầu thật: một câu hỏi khẩn cấp có thể cần đồng thời search KB và tra ticket. Hiện bản thử nghiệm ở [day09/extras/mcp_http_server.py](../../../extras/mcp_http_server.py) đã đi đúng hướng, nhưng nếu còn thời gian tôi sẽ làm nó ổn định hơn trước khi đổi policy worker sang client thật; còn bản mock in-process sẽ giữ làm fallback khi demo hoặc chấm bài.
