# Sprint 03 - MCP Owner Guide

## Ket luan nhanh

Neu chi xet rieng file `day09/lab/mcp_server.py` thi phan TODO toi thieu cua MCP server da co:

- `search_kb(query, top_k)` da duoc implement bang `tool_search_kb()`
- `get_ticket_info(ticket_id)` da duoc implement bang `tool_get_ticket_info()`
- `dispatch_tool()` va `list_tools()` da co, nen mock MCP server da dung du cho muc `Standard`

Noi cach khac: vai tro `MCP Owner` o muc "co it nhat 2 tools trong mcp_server.py" ve co ban da xong.

## Nhung gi Sprint 03 van can de du Definition of Done

README khong chi yeu cau implement tool trong `mcp_server.py`, ma con yeu cau ca pipeline tich hop MCP:

1. `workers/policy_tool.py` phai goi MCP client thay vi truy cap ChromaDB truc tiep
2. Trace phai ghi duoc thong tin tool call, toi thieu la `mcp_tool_called` va ket qua tool
3. Supervisor nen ghi ro ly do "chon MCP hay khong chon MCP" trong `route_reason`

## Trang thai hien tai

### 1. `mcp_server.py`

Da dat yeu cau co ban:

- `search_kb` da goi `workers.retrieval.retrieve_dense(...)`, co fallback mock neu ChromaDB loi
- `get_ticket_info` da doc tu `MOCK_TICKETS`
- Ngoai ra con co them `check_access_permission` va `create_ticket`

=> Neu giang vien check rieng file server thi phan nay on.

### 2. `workers/policy_tool.py`

Da co tich hop MCP o muc co ban:

- `_call_mcp_tool(...)` import `dispatch_tool` tu `mcp_server.py`
- Khi `needs_tool=True` va chua co chunks, worker se goi `search_kb`
- Khi task lien quan `ticket`, `p1`, `jira`, worker se goi `get_ticket_info`
- Ket qua duoc dua vao `state["mcp_tools_used"]`

=> Phan nay gan nhu da dap ung yeu cau "policy worker goi MCP client".

### 3. Trace / field ten

Day la diem can chu y nhat:

- README viet la can ghi `mcp_tool_called` va `mcp_result`
- Code hien tai dang luu vao `state["mcp_tools_used"]`

Dieu nay nghia la ve mat du lieu thi da co log MCP call, nhung ten field chua khop 100% voi README. Neu muon an toan khi demo/cham bai, nen them alias:

- `mcp_tool_called`: ten tool vua goi
- `mcp_result`: output cua tool hoac object log day du

Co the van giu `mcp_tools_used` de khong pha code cu, nhung nen bo sung 2 field tren.

## De xuat implementation toi thieu de chot Sprint 03

Neu muon chot Sprint 03 dep va it rui ro, nen lam them 3 viec nho:

1. Trong `workers/policy_tool.py`, moi lan goi MCP:
   - append vao `mcp_tools_used`
   - dong thoi ghi them `mcp_tool_called`
   - ghi them `mcp_result`

2. Trong `graph.py`:
   - khi supervisor set `needs_tool=True`, sua `route_reason` de noi ro vi sao can MCP
   - vi du: `task contains policy/access keyword -> policy_tool_worker + use MCP`

3. Khi luu trace:
   - dam bao file trace co cac truong lien quan MCP de doi Trace Owner dung lai duoc ngay

## Cau tra loi ngan cho vai tro MCP Owner

Ban co the noi ngan gon nhu sau:

`mcp_server.py` da hoan thanh phan yeu cau toi thieu cua Sprint 03 cho MCP Owner, vi da co it nhat 2 tools la `search_kb` va `get_ticket_info`, kem `dispatch_tool()` de mock MCP. Tuy nhien, neu xet toan bo Definition of Done cua Sprint 03 trong README thi van nen bo sung logging/alias trace (`mcp_tool_called`, `mcp_result`) va lam ro hon route_reason ve viec co dung MCP hay khong.`

## Hướng dẫn Advanced: MCP Server qua HTTP (FastAPI + SSE)

Để đạt điểm Bonus (+2) cho mức Advanced, bạn cần chạy MCP Server thực sự thay vì chỉ gọi function mock (Standard). Cách phổ biến nhất (và chuẩn của thư viện MCP) là dùng HTTP Server với Server-Sent Events (SSE) thông qua thư viện `mcp` kết hợp `fastapi` và `uvicorn`.

### 1. Cài đặt thư viện
```bash
pip install "mcp[cli]" fastapi uvicorn
```

### 2. Viết file `mcp_http_server.py`
Tạo một file mới (ví dụ: `mcp_http_server.py`) để khởi tạo MCP Server và Mount vào ứng dụng FastAPI:

```python
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
from mcp.server.fastapi.sse import SseServerTransport
from mcp.server.lowlevel.server import Server
import mcp.types as types

# Import functions từ mcp_server.py bản standard
from mcp_server import tool_search_kb, tool_get_ticket_info

app = FastAPI()
mcp_server = Server("ticket-mcp-server")
sse_transport = SseServerTransport("/messages")

@mcp_server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_kb",
            description="Tìm kiếm quy trình, chính sách từ ChromaDB",
            inputSchema={
                "type": "object", 
                "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}}
            }
        ),
        types.Tool(
            name="get_ticket_info",
            description="Lấy thông tin ticket",
            inputSchema={
                "type": "object", 
                "properties": {"ticket_id": {"type": "string"}}
            }
        )
    ]

@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "search_kb":
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 3)
        result = tool_search_kb(query, top_k)
        return [types.TextContent(type="text", text=str(result))]
        
    elif name == "get_ticket_info":
        ticket_id = arguments.get("ticket_id", "")
        result = tool_get_ticket_info(ticket_id)
        return [types.TextContent(type="text", text=str(result))]
        
    raise ValueError(f"Unknown tool: {name}")

@app.get("/sse")
async def handle_sse():
    async with sse_transport.connect_sse() as init_stream:
        # Binding router của server vào stream
        return await init_stream()

@app.post("/messages")
async def handle_messages(request):
    await sse_transport.handle_post_message(request)

if __name__ == "__main__":
    import asyncio
    
    # Startup script để ghép nối mcp_server với sse_transport
    @app.on_event("startup")
    async def startup():
        asyncio.create_task(mcp_server.run(sse_transport, sse_transport.server_options, sse_transport.server_options))

    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 3. Cập nhật Policy Worker (Client)
Trong `workers/policy_tool.py`, thay vì gọi `dispatch_tool()`, bạn đổi sang gọi qua `mcp.client`.

```python
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
import asyncio

async def async_call_real_mcp(tool_name: str, tool_args: dict):
    url = "http://localhost:8000/sse"
    async with sse_client(url) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=tool_args)
            return result.content[0].text

def _call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    # Do policy_tool.py có thể đang code đồng bộ, 
    # bạn cần dùng asyncio.run() để wrap hàm bất đồng bộ
    try:
        res_text = asyncio.run(async_call_real_mcp(tool_name, arguments))
        return {
            "mcp_tool_called": tool_name,
            "mcp_result": res_text
        }
    except Exception as e:
        return {
            "mcp_tool_called": tool_name,
            "mcp_result": f"Error calling MCP server: {e}"
        }
```

**Lưu ý quan trọng với mức Advanced:**
1. **Khởi chạy độc lập**: Phải mở thư mục lab trên 1 terminal phụ và chạy lệnh `python mcp_http_server.py` để server HTTP sống tách bạch. Sau đó ở giao diện terminal chính mới chạy `python eval_trace.py`.
2. **Theo dõi log**: Khi MCP server chạy dưới mode HTTP FastAPI, console của nó sẽ in log độc lập, hỗ trợ bạn debug tham số input/output một cách trực quan trong lúc các Node/Agent trong LangGraph call sang.
