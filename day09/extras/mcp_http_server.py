from fastapi import FastAPI
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.fastapi.sse import SseServerTransport # Nếu vẫn lỗi dòng này, hãy dùng mcp.server.sse

# Khởi tạo MCP Server bằng FastMCP (Rất ổn định)
mcp = FastMCP("ticket-mcp-server")

# Import logic từ file cũ
from mcp_server import search_kb, get_ticket_info

@mcp.tool()
def tool_search_kb(query: str, top_k: int = 3) -> str:
    """Tìm kiếm quy trình, chính sách từ Knowledge Base."""
    return str(search_kb(query, top_k))

@mcp.tool()
def tool_get_ticket_info(ticket_id: str) -> str:
    """Tra cứu thông tin chi tiết một ticket."""
    return str(get_ticket_info(ticket_id))

# Tích hợp vào FastAPI
app = FastAPI()

# Dùng helper tích hợp sẵn của FastMCP (nếu bản bạn có hỗ trợ)
# Nếu không, ta dùng cách thủ công ổn định sau:
from mcp.server.sse import SseServerTransport
sse = SseServerTransport("/messages")

@app.get("/sse")
async def handle_sse():
    async with sse.connect_sse() as streams:
        # Chạy server loop cho connection này
        await mcp.run_stdio_async(streams[0], streams[1]) # Hoặc dùng session trực tiếp

# --- CÁCH ĐƠN GIẢN NHẤT CHO BẢN NEW ---
# Nếu bạn không nhất thiết phải dùng FastAPI, chỉ cần chạy luôn server này:
if __name__ == "__main__":
    # Lệnh này sẽ tự động tạo một server MCP (mặc định là stdio)
    # Để chạy HTTP SSE bản mới nhất, thư viện mcp cung cấp lệnh CLI
    # Nhưng để code chạy ngay bây giờ, hãy dùng logic fix cho Server.run:
    pass
