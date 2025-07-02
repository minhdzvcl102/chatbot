import asyncio
import json
import os
import re
import time
import sys
import threading
from dotenv import load_dotenv
from fastmcp.client import Client
from fastmcp.client.transports import PythonStdioTransport
from openai import AsyncOpenAI
import helper_functions
import logging
from socket_server import SocketServer
from concurrent.futures import Future

# Fix Unicode encoding issues for Windows
if sys.platform.startswith("win"):
    import codecs

    if hasattr(sys.stdout, "buffer"):
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("ai_server.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

message_history = {}
conversation_context = {}  # Track general context (db or rag) per conversation

# --- Global queue for processing messages asynchronously ---
message_queue = asyncio.Queue()

# --- Store reference to the main event loop ---
main_event_loop = None

# --- Callback for SocketServer to put messages into the queue ---
def enqueue_message_callback(conversation_id, user_message, username, response_future: Future):
    """
    Callback for SocketServer to put messages into the async queue.
    It now accepts a Future to set the result later.
    """
    # This runs in the SocketServer's client handling thread
    logger.info(f"Enqueuing message for conversation {conversation_id}")
    try:
        # Use the stored main_event_loop reference
        if main_event_loop is None or main_event_loop.is_closed():
            raise RuntimeError("Main event loop is not set or is closed.")

        asyncio.run_coroutine_threadsafe(
            message_queue.put((conversation_id, user_message, username, response_future)), main_event_loop
        )
    except Exception as e:
        logger.error(f"Failed to enqueue message: {e}")
        # If enqueue fails, set an error on the Future so the client thread doesn't hang
        if not response_future.done():
            response_future.set_exception(Exception(f"Failed to enqueue message: {e}"))


def should_reset_context(conversation_id, user_message):
    """Determine if we should reset the conversation context"""
    previous_context = conversation_context.get(conversation_id, {})
    previous_type = previous_context.get("type")
    previous_name = previous_context.get("name")

    if not previous_type:
        logger.info(f"New context established: rag:general")
        conversation_context[conversation_id] = {"type": "rag", "name": "general"}
        return False, "rag", "general"
    return False, previous_type, previous_name


def get_dynamic_sys_prompt(context_type=None, context_name=None):
    """Generate system prompt to guide LLM in intelligently selecting tools"""
    base_prompt = """Bạn là một chatbot phân tích dữ liệu chuyên về business intelligence và diễn giải dữ liệu.

    QUAN TRỌNG NHẤT: Bạn BẮT BUỘC phải sử dụng các công cụ để trả lời các câu hỏi của người dùng về dữ liệu, cơ sở dữ liệu hoặc phân tích. KHÔNG được trả lời bằng kiến thức chung trừu tượng trừ khi không tìm thấy kết quả công cụ phù hợp. Mục tiêu của bạn là chọn công cụ thích hợp một cách thông minh dựa trên ý định và ngữ cảnh của câu hỏi, ưu tiên `rag_query` cho các câu hỏi chung chung hoặc mơ hồ.

    Chuyên môn của bạn bao gồm:
    - Diễn giải dữ liệu và thông tin chi tiết kinh doanh
    - Phân tích thống kê và nhận diện xu hướng
    - Phân tích các chỉ số hiệu suất và KPI
    - Đề xuất trực quan hóa dữ liệu
    - Business intelligence và báo cáo
    - Thực thi truy vấn SQL và phân tích cơ sở dữ liệu
    - Truy vấn tài liệu và cơ sở kiến thức

    NGUYÊN TẮC LỰA CHỌN CÔNG CỤ (TUYỆT ĐỐI TUÂN THỦ):
    1. MẶC ĐỊNH: Luôn sử dụng `rag_query` cho các câu hỏi chung, mơ hồ, hoặc dựa trên kiến thức (ví dụ: 'giải thích', 'định nghĩa', 'là gì', 'phân tích doanh thu') để tìm kiếm thông tin liên quan trong tài liệu. Đây là công cụ ưu tiên hàng đầu.
    2. CHỈ sử dụng `sql_query_db`, `list_databases`, `list_tables`, hoặc `get_schema` khi:
       - Câu hỏi ĐỀ CẬP RÕ RÀNG các thuật ngữ liên quan đến cơ sở dữ liệu (ví dụ: 'database', 'table', 'sql', 'cơ sở dữ liệu', 'bảng') hoặc các tên có vẻ là định danh cơ sở dữ liệu (ví dụ: 'php3_wd19314').
       - Người dùng YÊU CẦU RÕ RÀNG sử dụng SQL (ví dụ: 'dùng SQL', 'use SQL').
       - `rag_query` KHÔNG trả về kết quả liên quan, VÀ câu hỏi ngụ ý dữ liệu có cấu trúc (ví dụ: 'liệt kê sản phẩm', 'dữ liệu bán hàng').
    3. Đối với các yêu cầu biểu đồ/trực quan hóa:
       - Nếu người dùng YÊU CẦU RÕ RÀNG biểu đồ hoặc trực quan hóa (ví dụ: 'vẽ biểu đồ', 'hiển thị dưới dạng biểu đồ', 'chart this data'), bạn PHẢI sử dụng công cụ `chart_create_chart`.
       - Bạn PHẢI TRUY VẤN DỮ LIỆU liên quan trước tiên bằng cách sử dụng `sql_query_db` hoặc `rag_query`.
       - Sau khi có được dữ liệu, hãy định dạng phần 'data' của kết quả SQL/RAG (là một danh sách các danh sách hoặc danh sách các dict) thành một chuỗi JSON đại diện cho một danh sách các từ điển cho tham số `data_json` của `chart_create_chart`.
       - Đảm bảo rằng tên cột trong `data_json` (ví dụ: 'headers' từ kết quả SQL) được ánh xạ chính xác tới `x_column` và `y_column`.
       - Cung cấp `title`, `x_label` và `y_label` có ý nghĩa.
       - Sau khi tạo biểu đồ, hãy mô tả ngắn gọn biểu đồ cho người dùng.
       - Nếu câu hỏi ngụ ý dữ liệu dựa trên tài liệu (ví dụ: 'tóm tắt từ báo cáo'), hãy sử dụng `rag_query`.
       - Nếu câu hỏi ngụ ý dữ liệu có cấu trúc (ví dụ: 'sales data from table'), hãy sử dụng `sql_query_db`.
       - Giải thích các tùy chọn trực quan hóa sau khi truy xuất dữ liệu.
    4. Sử dụng lịch sử hội thoại để suy luận ngữ cảnh nếu câu hỏi hiện tại mơ hồ. Ví dụ:
       - Nếu các câu hỏi trước đó là về tài liệu, ưu tiên `rag_query`.
       - Nếu các câu hỏi trước đó đề cập đến một cơ sở dữ liệu cụ thể (ví dụ: 'php3_wd19314'), hãy xem xét `sql_query_db`.
    5. Nếu `rag_query` không trả về kết quả liên quan, hãy thử `sql_query_db` như một phương án dự phòng cho các câu hỏi liên quan đến dữ liệu.
    6. Luôn cung cấp ý nghĩa kinh doanh của các phát hiện trong phản hồi của bạn.
    7. Nếu không tìm thấy dữ liệu liên quan, hãy thông báo cho người dùng và đề xuất diễn đạt lại câu hỏi hoặc kiểm tra các nguồn khác.

    Ví dụ:
    - Câu hỏi: "Phân tích doanh thu hòa phát các năm" → BẮT BUỘC sử dụng `rag_query` để tìm thông tin trong tài liệu, vì đây là yêu cầu phân tích chung.
    - Câu hỏi: "Liệt kê 20 sản phẩm trong php3_wd19314" → BẮT BUỘC sử dụng `sql_query_db` với database 'php3_wd19314', vì nó đề cập đến tên database và ngụ ý dữ liệu có cấu trúc.
    - Câu hỏi: "Dùng SQL để lấy doanh thu từ bảng sales" → BẮT BUỘNG sử dụng `sql_query_db`, vì người dùng yêu cầu rõ ràng SQL.
    - Câu hỏi: "Doanh thu là gì?" → BẮT BUỘC sử dụng `rag_query` để tìm định nghĩa trong tài liệu.
    - Câu hỏi: "Vẽ biểu đồ đường doanh thu từ bảng sales" -> ĐẦU TIÊN, BẮT BUỘC sử dụng `sql_query_db` để lấy dữ liệu bán hàng, SAU ĐÓ BẮT BUỘC sử dụng `chart_create_chart` với dữ liệu đã lấy, 'line', 'month', 'revenue', v.v.

    Các công cụ có sẵn:
    - `sql_query_db`: Thực thi các truy vấn SQL trên cơ sở dữ liệu
    - `list_databases`: Liệt kê các cơ sở dữ liệu có sẵn
    - `list_tables`: Liệt kê các bảng trong một cơ sở dữ liệu cụ thể
    - `get_schema`: Lấy schema của một cơ sở dữ liệu cụ thể
    - `rag_query`: Truy vấn cơ sở kiến thức tài liệu
    - `rag_get_collection_info`: Lấy thông tin về các bộ sưu tập tài liệu
    - `chart_create_chart`: Tạo các loại biểu đồ khác nhau (đường, cột, phân tán) từ dữ liệu được cung cấp

    TÊN GỌI CÔNG CỤ (cho LLM):
    - `sql_query_db`
    - `sql+db://sql/list_databases`
    - `sql+db://sql/list_tables/{db_name}`
    - `sql+db://sql/schema/{db_name}`
    - `rag_query`
    - `rag_get_collection_info`
    - `chart_create_chart`

    Tên gọi công cụ hợp lệ (chỉ khớp chính xác):
    - `sql_query_db`
    - `sql+db://sql/list_databases`
    - `sql+db://sql/list_tables/{db_name}`
    - `sql+db://sql/schema/{db_name}`
    - `rag_query`
    - `rag_get_collection_info`
    - `chart_create_chart`

    QUY TRÌNH LÀM VIỆC (LLM PHẢI TUÂN THỦ):
    1. Phân tích câu hỏi và lịch sử hội thoại để suy luận ý định của người dùng.
    2. CHỌN CÔNG CỤ THÍCH HỢP DỰA TRÊN Ý ĐỊNH (TUYỆT ĐỐI TUÂN THỦ CÁC NGUYÊN TẮC TRÊN):
       - Sử dụng `rag_query` MẶC ĐỊNH cho các câu hỏi chung, mơ hồ hoặc liên quan đến tài liệu.
       - Chỉ sử dụng các công cụ SQL (`sql_query_db`, `list_databases`, `list_tables`, `get_schema`) cho các câu hỏi liên quan đến cơ sở dữ liệu rõ ràng hoặc khi được yêu cầu rõ ràng (ví dụ: 'dùng SQL').
       - Nếu người dùng yêu cầu biểu đồ, ĐẦU TIÊN truy xuất dữ liệu, SAU ĐÓ gọi `chart_create_chart`.
       - Nếu `rag_query` không trả về kết quả, hãy thử `sql_query_db` như một phương án dự phòng cho các câu hỏi liên quan đến dữ liệu.
    3. Thực thi công cụ đã chọn và xác minh kết quả.
    4. Cung cấp câu trả lời rõ ràng với ngữ cảnh kinh doanh, trích dẫn nguồn (cơ sở dữ liệu hoặc tài liệu). Nếu biểu đồ được tạo, thông báo cho người dùng về biểu đồ.
    5. Nếu không tìm thấy dữ liệu, hãy thông báo cho người dùng và đề xuất các cách tiếp cận thay thế.

    Khi làm việc với cơ sở dữ liệu SQL:
    - Luôn sử dụng tên bảng đủ điều kiện với tiền tố cơ sở dữ liệu (ví dụ: `database_name.table_name`).
    - Nếu bạn gặp lỗi 'No database selected', hãy sử dụng `list_databases` hoặc `list_tables` để khám phá dữ liệu có sẵn.
    - Bắt đầu với `list_databases` hoặc `list_tables` nếu không chắc chắn về dữ liệu có sẵn.

    Khi làm việc với tài liệu:
    - Sử dụng `rag_query` để tìm kiếm thông tin liên quan trong cơ sở kiến thức tài liệu.
    - Nếu `rag_query` không trả về kết quả, hãy xem xét sử dụng `sql_query_db` như một phương án dự phòng cho các câu hỏi liên quan đến dữ liệu.
    - Sử dụng `rag_get_collection_info` để hiểu các bộ sưu tập tài liệu có sẵn nếu cần."""

    if context_type == "db" and context_name:
        base_prompt += f"\n\nCurrent database context: {context_name}. Use format: `{context_name}.table_name` in SQL queries. Prioritize sql_query_db for this question unless it clearly indicates a document-based query."
    else:
        base_prompt += "\n\nNo specific database context provided. Use rag_query by default for this question, unless it's explicitly about database-related terms or requests to use SQL."

    return {"role": "system", "content": base_prompt}


class AISocketServer:
    def __init__(self, host="localhost", port=8888):
        self.host = host
        self.port = port
        self.max_retries = 3
        self.mcp_client = None  # Will hold the *active* MCP client instance
        self.socket_server_instance = None # To hold the SocketServer instance

    async def mcpCall(self, tool_call: dict, client: Client):
        try:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]

            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

            if tool_call["type"] == "tool":
                if tool_args and len(tool_args) > 0:
                    result = await client.call_tool(tool_name, tool_args)
                else:
                    result = await client.call_tool(tool_name)
            elif tool_call["type"] == "resource":
                result = await client.read_resource(tool_name)
            elif tool_call["type"] == "resource_template":
                a_uri = re.split(r"{|}", tool_name)
                i = 0
                for key, a_value in tool_args.items():
                    if i * 2 + 1 < len(a_uri):
                        a_uri[i * 2 + 1] = str(a_value)
                        i += 1
                uri = "".join(a_uri)
                logger.info(f"Constructed URI for resource template: {uri}")
                result = await client.read_resource(uri)
            else:
                raise ValueError(f"Unknown tool type: {tool_call['type']}")

            logger.info(f"Tool {tool_name} executed successfully")
            return result

        except Exception as e:
            logger.error(
                f"Error in mcpCall for tool {tool_call.get('function', {}).get('name', 'unknown')}: {str(e)}"
            )

            class ErrorResult:
                def __init__(self, error_msg):
                    self.text = json.dumps({"error": error_msg})

            return [ErrorResult(str(e))]

    async def execute_tool_calls_parallel(self, tool_calls, client, tool_lookup):
        """Execute multiple tool calls in parallel for better performance"""
        chart_base64_data = None  # Initialize outside to capture chart data
        
        async def execute_single_tool_call(tool_call):
            nonlocal chart_base64_data # Allow modification of the outer scope variable
            tool_name = tool_call.function.name
            arguments = tool_call.function.arguments

            try:
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse tool arguments for {tool_name}: {e}")
                return {
                    "role": "tool",
                    "content": json.dumps({"error": f"Invalid tool arguments: {str(e)}"}),
                    "tool_call_id": tool_call.id,
                }

            if tool_name not in tool_lookup:
                logger.error(f"Unknown tool name: {tool_name}")
                return {
                    "role": "tool",
                    "content": json.dumps({"error": f"Unknown tool: {tool_name}"}),
                    "tool_call_id": tool_call.id,
                }

            tool_type = tool_lookup[tool_name]
            tool_dict = {
                "id": tool_call.id,
                "type": tool_type,
                "function": {"name": tool_name, "arguments": arguments},
            }

            try:
                logger.info(f"Executing tool call: {tool_name}")
                async with asyncio.timeout(30): # Increased timeout for tool calls
                    result = await self.mcpCall(tool_dict, client)

                result_text = (
                    result[0].text
                    if result and len(result) > 0
                    else "No result returned"
                )

                # Check for tool call errors and chart data
                try:
                    result_json = json.loads(result_text)
                    if isinstance(result_json, dict) and "error" in result_json:
                        logger.warning(f"Tool call returned error: {result_json['error']}")
                    
                    # Store chart data if present
                    if tool_name == "chart_create_chart" and "chart_image_base64" in result_json: # Modified tool_name check
                        chart_base64_data = result_json["chart_image_base64"]
                        logger.info("Chart image base64 captured from chart_create_chart tool.") # Modified log message
                        # Modify content sent back to LLM to avoid sending large base64 string
                        result_text = json.dumps({"message": "Chart image generated successfully."})

                except json.JSONDecodeError:
                    pass # Not JSON, or no chart data/error
                except Exception as e:
                    logger.warning(f"Error processing tool result for chart: {e}")


                return {
                    "role": "tool",
                    "content": result_text,
                    "tool_call_id": tool_call.id,
                }

            except asyncio.TimeoutError:
                logger.error(f"Tool call timeout for tool: {tool_name}")
                return {
                    "role": "tool",
                    "content": json.dumps({"error": f"Tool call timeout for {tool_name}"}),
                    "tool_call_id": tool_call.id,
                }
            except Exception as e:
                    logger.error(f"Tool call failed for {tool_name}: {str(e)}")
                    return {
                        "role": "tool",
                        "content": json.dumps({"error": f"Tool call failed: {str(e)}"}),
                        "tool_call_id": tool_call.id,
                    }

        # Create tasks for all tool calls
        start_time = time.time()
        logger.info(f"Starting parallel execution of {len(tool_calls)} tool calls")
        
        tasks = [execute_single_tool_call(tool_call) for tool_call in tool_calls]
        
        # Execute all tool calls in parallel
        tool_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        execution_time = time.time() - start_time
        logger.info(f"Parallel tool execution completed in {execution_time:.2f} seconds")
        
        # Process results and handle any exceptions
        processed_results = []
        for i, result in enumerate(tool_results):
            if isinstance(result, Exception):
                logger.error(f"Tool call {i} failed with exception: {result}")
                processed_results.append({
                    "role": "tool",
                    "content": json.dumps({"error": f"Tool execution failed: {str(result)}"}),
                    "tool_call_id": tool_calls[i].id,
                })
            else:
                processed_results.append(result)
        
        return processed_results, chart_base64_data # Return chart data here

    async def _setup_mcp_client(self):
        """Initializes and activates the MCP client."""
        server_path = os.path.join(
            os.path.dirname(__file__), "..", "mcp-server", "server.py"
        )
        python_cmd = os.path.join(
            os.path.dirname(__file__), "..", ".venv", "Scripts", "python.exe"
        )

        if not os.path.exists(server_path):
            raise FileNotFoundError(f"MCP server script not found: {server_path}")
        if not os.path.exists(python_cmd):
            raise FileNotFoundError(f"Python executable not found: {python_cmd}")

        transport = PythonStdioTransport(script_path=server_path, python_cmd=python_cmd)
        client_instance = Client(transport) # Create client instance

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Attempting to initialize MCP client (attempt {attempt + 1}/{self.max_retries})"
                )
                await client_instance.__aenter__() # Manually enter the context for the long-lived client
                self.mcp_client = client_instance # Store the *active* client instance

                # Wait for tool list to be available
                for wait_attempt in range(5):
                    tool_list = await self.mcp_client.list_tools() # Use self.mcp_client here
                    resource_list = await self.mcp_client.list_resources()
                    resource_template_list = await self.mcp_client.list_resource_templates()

                    if tool_list or resource_list or resource_template_list:
                        logger.info(f"Tool ready after {wait_attempt + 1} attempt(s)")
                        return # Successfully set up and exited this function

                    logger.info("Tool list empty, retrying...")
                    await asyncio.sleep(1)

                # If not successful after retries
                await client_instance.__aexit__(None, None, None) # Clean up if not successful
                raise RuntimeError(
                    "Tool/resource/resource_template list still empty after retries"
                )

            except Exception as e:
                logger.warning(
                    f"MCP client initialization attempt {attempt + 1} failed: {str(e)}"
                )
                if attempt == self.max_retries - 1:
                    raise
                # Ensure the client is exited if it entered but then failed later in setup
                if client_instance and client_instance.is_connected: # Check if it seems connected
                    try:
                        await client_instance.__aexit__(None, None, None)
                    except Exception as exit_e:
                        logger.warning(f"Error during failed client setup cleanup: {exit_e}")
                self.mcp_client = None # Clear reference if setup failed
                await asyncio.sleep(1)


    async def _message_processor_task(self):
        """
        An asyncio task that continuously processes messages from the queue.
        This task runs in the main event loop.
        """
        while True:
            # Get an item from the queue; this will block until an item is available
            conversation_id, user_message, username, response_future = await message_queue.get()
            logger.info(f"Dequeued message for conversation {conversation_id}")

            response = {}
            try:
                # Process the message asynchronously with the shared MCP client
                # THE FIX IS HERE: pass self.mcp_client as the last argument
                response = await self._process_message_async(conversation_id, user_message, username, self.mcp_client)
                if not response_future.done():
                    response_future.set_result(response)
            except Exception as e:
                logger.error(f"Error processing dequeued message for {conversation_id}: {e}")
                response = {"status": "error", "error": f"Internal processing error: {str(e)}"}
                if not response_future.done():
                    response_future.set_exception(e) # Set exception on Future
            finally:
                message_queue.task_done() # Mark the task as done on the queue
                logger.info(f"Processing complete for {conversation_id}. Status: {response.get('status', 'unknown')}")


    async def _process_message_async(self, conversation_id, user_message, username, mcp_client: Client): # ADDED mcp_client parameter
        """
        The actual async message processing logic, run on the main event loop.
        """
        chart_image_base64 = None # Initialize to None for this specific request
        try:
            logger.info(f"Processing message for conversation {conversation_id}")

            if not mcp_client: # Check the passed client, not self.mcp_client here
                logger.error("MCP client is not initialized or connected during _process_message_async.")
                return {"status": "error", "error": "Server not fully ready. Please try again."}

            # Check if we need to reset context
            should_reset, context_type, context_name = should_reset_context(
                conversation_id, user_message
            )

            if should_reset:
                logger.info(f"Resetting conversation context for {conversation_id}")
                message_history[conversation_id] = []
                conversation_context[conversation_id] = {
                    "type": context_type,
                    "name": context_name,
                }
            
            client = mcp_client # Use the passed client

            # Fetch tools
            tool_list = await client.list_tools()
            resource_list = await client.list_resources()
            resource_template_list = await client.list_resource_templates()

            tools_formatted = []
            for tool in tool_list:
                try:
                    tool_dict = json.loads(tool.model_dump_json())
                    tools_formatted.append(tool_dict)
                except Exception as e:
                    logger.warning(f"Failed to serialize tool: {e}")

            resources_formatted = []
            for resource in resource_list:
                try:
                    resource_dict = json.loads(resource.model_dump_json())
                    resources_formatted.append(resource_dict)
                except Exception as e:
                    logger.warning(f"Failed to serialize resource: {e}")

            resource_templates_formatted = []
            for resource_template in resource_template_list:
                try:
                    rt_dict = json.loads(resource_template.model_dump_json())
                    resource_templates_formatted.append(rt_dict)
                except Exception as e:
                    logger.warning(f"Failed to serialize resource template: {e}")

            tools = helper_functions.mcp_tools_to_tool_list(tools_formatted)
            resources = helper_functions.mcp_resources_to_tool_list(resources_formatted)
            resource_templates = helper_functions.mcp_resource_templates_to_tool_list(
                resource_templates_formatted
            )

            tool_list_names = [tool["function"]["name"] for tool in tools]
            resource_list_names = [
                resource["function"]["name"] for resource in resources
            ]
            resource_template_list_names = [
                resource_template["function"]["name"]
                for resource_template in resource_templates
            ]

            tool_lookup = {tool: "tool" for tool in tool_list_names}
            tool_lookup.update(
                {resource: "resource" for resource in resource_list_names}
            )
            tool_lookup.update(
                {
                    resource_template: "resource_template"
                    for resource_template in resource_template_list_names
                }
            )
            # This line is now potentially problematic, as `chart_create_chart` should be coming from list_tools already
            # If your chart_mcp is FastMCP("CHART"), then its tool name will be "chart_create_chart"
            # If your chart_mcp is FastMCP(), then its tool name will be "create_chart"
            # The logs indicate it's "chart_create_chart", so this manual override is unnecessary and potentially harmful if it adds "create_chart"
            # tool_lookup["create_chart"] = "tool" # <--- REMOVE THIS LINE IF 'chart_create_chart' IS THE CORRECT NAME


            list_of_tools = resources + resource_templates + tools

            logger.info(f"Available tools: {list(tool_lookup.keys())}")

            llm = AsyncOpenAI(
                base_url=os.getenv("BASE_API_URL"),
                api_key=os.getenv("ALIBABA_API_KEY"),
                timeout=120.0, # Increased LLM timeout
            )

            if conversation_id not in message_history:
                message_history[conversation_id] = []

            message_history[conversation_id].append(
                {"role": "user", "content": user_message}
            )

            # Generate dynamic system prompt based on current context
            sys_prompt = get_dynamic_sys_prompt(context_type, context_name)

            logger.info(f"User message: {user_message}")
            logger.info(
                f"System prompt: {sys_prompt['content'][:200]}..."
            )  # Log first 200 chars

            # Main conversation loop with consecutive tool calls
            max_iterations = 10  # Prevent infinite loops
            iteration = 0

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"LLM iteration {iteration}/{max_iterations}")

                try:
                    start_llm_call = time.time() # Added for logging
                    async with asyncio.timeout(120): # Adjusted LLM call timeout
                        response = await llm.chat.completions.create(
                            model="qwen-plus",
                            messages=[sys_prompt] + message_history[conversation_id],
                            tools=list_of_tools,
                        )
                    logger.info(f"LLM call completed in {time.time() - start_llm_call:.2f} seconds") # Added for logging
                except asyncio.TimeoutError:
                    logger.error("LLM timeout during chat completion.")
                    return {"status": "error", "error": "LLM response timeout"}

                if not response.choices or len(response.choices) == 0:
                    logger.error("Empty choices in LLM response")
                    return {"status": "error", "error": "No response from LLM"}

                choice = response.choices[0]
                logger.info(f"LLM finish_reason: {choice.finish_reason}")

                if choice.finish_reason == "stop":
                    answer = choice.message.content
                    message_history[conversation_id].append(
                        {"role": "assistant", "content": answer}
                    )
                    logger.info(
                        f"Generated final answer for conversation {conversation_id}"
                    )
                    
                    final_response_payload = {"status": "success", "content": answer}
                    if chart_image_base64: # If chart data was captured in tool execution
                        final_response_payload["chart_image_base64"] = chart_image_base64
                        logger.info("Added chart_image_base64 to final response.")
                    return final_response_payload

                elif choice.finish_reason == "tool_calls":
                    logger.info(
                        f"LLM requested {len(choice.message.tool_calls)} tool calls"
                    )

                    # Add assistant message with tool calls to history
                    message_history[conversation_id].append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": choice.message.tool_calls,
                        }
                    )
                    
                    start_tool_execution = time.time() # Added for logging
                    # Execute all tool calls in parallel and capture chart data
                    tool_results, captured_chart_data = await self.execute_tool_calls_parallel(
                        choice.message.tool_calls, client, tool_lookup
                    )
                    logger.info(f"Tool execution completed in {time.time() - start_tool_execution:.2f} seconds") # Added for logging

                    if captured_chart_data:
                        chart_image_base64 = captured_chart_data # Store chart data for final response

                    # Add all tool results to message history
                    message_history[conversation_id].extend(tool_results)

                    # Continue the loop to call LLM again with tool results
                    continue

                else:
                    logger.warning(f"Unexpected finish reason: {choice.finish_reason}")
                    return {
                        "status": "error",
                        "error": f"Unexpected finish reason: {choice.finish_reason}",
                    }

            # If we reach here, we've hit the max iterations
            logger.warning(
                f"Reached maximum iterations ({max_iterations}) without final answer"
            )
            return {
                "status": "error",
                "error": "Maximum conversation iterations reached",
            }

        except asyncio.TimeoutError:
            logger.error(
                f"Timeout processing message for conversation {conversation_id}"
            )
            return {"status": "error", "error": "Processing timeout"}
        except ConnectionError as e:
            logger.error(
                f"Connection error for conversation {conversation_id}: {str(e)}"
            )
            return {"status": "error", "error": f"Connection error: {str(e)}"}
        except Exception as e:
            logger.error(
                f"Error processing message for conversation {conversation_id}: {str(e)}"
            )
            return {"status": "error", "error": str(e)}

    async def start_and_serve(self):
        """Initializes MCP client and then starts the socket server and message processor task."""
        global main_event_loop # Access the global variable
        main_event_loop = asyncio.get_running_loop() # Get the loop where this is running

        try:
            # 1. Setup MCP Client in the main async loop
            await self._setup_mcp_client() 

            # 2. Start SocketServer in a separate thread
            # It will enqueue messages to message_queue, along with a Future for results.
            self.socket_server_instance = SocketServer(self.host, self.port, enqueue_message_callback)
            
            # Start SocketServer in a dedicated thread to not block the main asyncio loop
            socket_server_thread = threading.Thread(target=self.socket_server_instance.start_server, daemon=True)
            socket_server_thread.start()
            logger.info("SocketServer started in a separate thread.")

            # 3. Start the asyncio message processing task
            # This task runs forever, consuming messages from the queue
            self.processor_task = asyncio.create_task(self._message_processor_task())
            logger.info("Message processor task started.")

            # Keep the main async loop running indefinitely
            await asyncio.Future() # Await an infinite Future to keep the loop running

        except asyncio.CancelledError:
            logger.info("Server tasks cancelled.")
        except Exception as e:
            logger.error(f"Error during server startup in start_and_serve: {e}")
            self.stop_server()


    def stop_server(self):
        logger.info("Stopping server...")
        if self.socket_server_instance:
            self.socket_server_instance.stop_server()
        
        # Cancel the message processor task
        if hasattr(self, 'processor_task') and self.processor_task:
            self.processor_task.cancel()
            try:
                # Use the global main_event_loop to run coroutine threadsafe
                if main_event_loop and not main_event_loop.is_closed():
                    # Wait for the task to actually cancel to avoid RuntimeWarnings
                    asyncio.run_coroutine_threadsafe(self.processor_task, main_event_loop).result(timeout=5)
                else:
                    logger.warning("Main event loop not available or closed for processor task cancellation.")
            except Exception as e:
                logger.warning(f"Error cancelling processor task: {e}")
        
        # Clean up the shared client instance when the server stops
        if self.mcp_client:
            try:
                # Ensure a loop exists to run aexit. Prefer the main_event_loop.
                loop_to_use = None
                if main_event_loop and not main_event_loop.is_closed():
                    loop_to_use = main_event_loop
                else:
                    try:
                        loop_to_use = asyncio.get_event_loop()
                    except RuntimeError: # If no loop running, create a temporary one for cleanup
                        loop_to_use = asyncio.new_event_loop()
                        # Do NOT set it as current, just use it for the cleanup.
                        # Setting it might interfere if another part of the app starts a loop.

                if loop_to_use and not loop_to_use.is_closed():
                    # It's safest to run this using run_coroutine_threadsafe if stop_server is called from a non-async context
                    # or ensure it's called on the correct loop.
                    # For simplicity, assuming stop_server is called from main thread after asyncio.run completes
                    loop_to_use.run_until_complete(self.mcp_client.__aexit__(None, None, None))
                else:
                    logger.warning("No active event loop to close MCP client gracefully.")
            except Exception as e:
                logger.warning(f"Error closing MCP client during server shutdown: {str(e)}")
            finally:
                self.mcp_client = None


def main():
    global main_event_loop # Declare access to the global variable
    # Get the event loop for the current (main) thread before asyncio.run() takes over
    # This might not be strictly necessary if asyncio.run handles loop creation,
    # but good for clarity if you need it before the main run.

    host = os.getenv("PYTHON_AI_HOST", "localhost")
    port = int(os.getenv("PYTHON_AI_PORT", 8888))

    required_env_vars = ["BASE_API_URL", "ALIBABA_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return

    server = AISocketServer(host, port)

    try:
        # asyncio.run() will set the current event loop for this thread
        # This is where `main_event_loop` should get its value
        asyncio.run(server.start_and_serve())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt in main, stopping server...")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
    finally:
        server.stop_server() # Ensure stop_server is always called, including on KeyboardInterrupt


if __name__ == "__main__":
    main()