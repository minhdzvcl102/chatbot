import asyncio
import json
import os
import re
import time
import sys
import threading
import logging
from dotenv import load_dotenv
from fastmcp.client import Client
from fastmcp.client.transports import PythonStdioTransport
import boto3
from botocore.exceptions import ClientError
import helper_functions
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
def enqueue_message_callback(conversation_id, user_message, username, user_id, response_future: Future):
    """
    Callback for SocketServer to put messages into the async queue.
    Now includes user_id for permission control.
    """
    logger.info(f"Enqueuing message for conversation {conversation_id}, user_id: {user_id}")
    try:
        if main_event_loop is None or main_event_loop.is_closed():
            raise RuntimeError("Main event loop is not set or is closed.")
        asyncio.run_coroutine_threadsafe(
            message_queue.put((conversation_id, user_message, username, user_id, response_future)), 
            main_event_loop
        )
    except Exception as e:
        logger.error(f"Failed to enqueue message for user_id {user_id}: {e}")
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
    base_prompt = """You are a data analysis chatbot specializing in business intelligence and data interpretation.
    
    CRITICAL RULE: You MUST use the available tools to answer user questions about data, databases, or analysis. DO NOT answer with abstract general knowledge unless no relevant tool results are found.

    
    MANDATORY WORKFLOW FOR ALL QUESTIONS:
    1. FIRST, call the appropriate tool to get real data
    2. WAIT for the tool results
    3. ONLY then provide your answer based on the tool results
    4. If tool returns no results, explicitly state "No relevant information found in the uploaded documents"

    TOOL USAGE INSTRUCTIONS:
    - When you need to use a tool, call it using the proper function calling format
    - Always use tools to get actual data before providing analysis
    - Wait for tool results before providing your final answer
    - NEVER provide answers without first calling a tool

    TOOL SELECTION PRINCIPLES:
    1. For database-related questions (like "liệt kê db", "list databases"):
       - Use `sql+db://sql/list_databases/{user_id}` to list available databases
       - Use `sql+db://sql/list_tables/{db_name}` to list tables in a database
       - Use `sql+db://sql/schema/{db_name}` to get database schema
       - Use `sql_query_db` for SQL queries 
       
    2. For general questions or document-related questions: 
       - ALWAYS use `rag_query` to search knowledge base FIRST
       - Only answer based on the results from rag_query
       
    3. For PDF summarization requests:
       - Use `summarize_pdf` when user asks to summarize a specific PDF file
       - Vietnamese keywords: "tóm tắt PDF", "tóm tắt file PDF", "tóm tắt tài liệu", "summary PDF"
       - English keywords: "summarize PDF", "PDF summary", "document summary"
       - Provide the complete file path to the tool
       
    4. For RAG collection information:
       - Use `get_collection_info` when user asks about uploaded documents status
       - Vietnamese: "thông tin tài liệu", "số lượng file", "trạng thái collection"
       - English: "collection info", "document status", "how many documents"
       
    5. For visualization: Use `chart_create_chart` when explicitly requested

    RESPONSE FORMAT:
    - If rag_query returns relevant documents: Base your answer on those documents
    - If rag_query returns no documents: Say "I don't have information about this in the uploaded documents"
    - If summarize_pdf succeeds: Present the summary in a well-formatted way
    - Always cite which documents your answer comes from

    When working with Vietnamese:
    - "liệt kê db" = "list databases" → use sql+db://sql/list_databases/{user_id}
    - "hiển thị bảng" = "show tables" → use sql+db://sql/list_tables/{db_name}
    - "cấu trúc db" = "database schema" → use sql+db://sql/schema/{db_name}
    - "vẽ biểu đồ" = "chart_create_chart"
    - "tóm tắt PDF" = "summarize PDF" → use summarize_pdf with file path
    - "tóm tắt tài liệu" = "document summary" → use summarize_pdf with file path
    - "thông tin collection" = "collection info" → use get_collection_info
    - "số lượng tài liệu" = "document count" → use get_collection_info
    - "Tóm tắt" (general) = "summarize" → use rag_query with "summarize" keyword
    - For any other question → use rag_query first

    - For requests like "hiển thị bảng", "liệt kê dưới dạng bảng":
   - If data comes from sql_query_db, format the results as a markdown table with headers and data rows , and align columns equally.
   - Example: 
         | Header1     | Header2     | Header3     |
         |-------------|-------------|-------------|
         | Data1       | Long Data2  | Data3       |
         | Short Data  | Data2       | Longer Data |

     CRITICAL DATABASE QUERY RULES:
    1. For Vietnamese database queries like "lấy cho tôi các mã giao dịch", "hiển thị đơn hàng":
       - STEP 1: ALWAYS get available databases first using list_databases
       - STEP 2: If multiple databases, ask user to specify OR use the first one
       - STEP 3: ALWAYS prefix your SQL query with "USE `database_name`;"
       - STEP 4: Then execute your actual SELECT query
       
    2. NEVER run bare SELECT statements without USE database first
    3. Example correct workflow:
       - User: "lấy cho tôi các đơn hàng tháng 8"
       - AI: First call list_databases
       - AI: Then sql_query_db with "USE `ecommerce_db`; SELECT * FROM orders WHERE MONTH(created_at) = 8;"
       
    4. If SQL fails with "Table doesn't exist", always retry with USE database_name first

    PDF SUMMARIZATION WORKFLOW:
    1. For requests like "tóm tắt file ABC.pdf":
       - Call summarize_pdf with the exact file path
       - Present the summary in a readable format with clear sections
       - Include metadata (pages, word count, etc.)
       
    2. For general summarization requests without specific file:
       - Use rag_query to find relevant content first
       - If user wants to summarize all uploaded content, use get_collection_info to show available documents
       - Then suggest they specify which document to summarize
       
    3. PDF Summary Presentation Format:
       - Always format the summary with clear headers
       - Show file metadata (pages, size, etc.)
       - Break content into readable sections
       - Provide context about the document type/topic

    TOOL SELECTION PRIORITY:
    1. For Vietnamese queries like "lấy cho tôi", "hiển thị", "tìm" + database terms:
       → ALWAYS use sql_query_db FIRST (but with USE database prefix!)
    2. For "tóm tắt PDF [filename]" or "summarize PDF [filename]":
       → Use rag_summarize_pdf with the specified file path
    3. For "tóm tắt" without specific file or general document questions:
       → Use rag_query to search relevant content
    4. For collection status questions:
       → Use get_collection_info
    5. Only use rag_query if SQL fails or for document-specific questions
    
    IMPORTANT: Always response by Vietnamese
    REMEMBER: Always call rag_query for document-related questions before answering!"""

    if context_type == "db" and context_name:
        base_prompt += f"\n\nCurrent database context: {context_name}. Prioritize SQL tools for database-related queries. Always USE {context_name} before running queries."
    else:
        base_prompt += "\n\nNo specific database context. For database questions, start with list_databases tool, then USE the appropriate database before querying. For other questions, use rag_query."
    
    return {"role": "system", "content": base_prompt}

async def generate_message(bedrock_runtime, model_id, system_prompt, messages, max_tokens, tools=None):
    """
    Generate a message with Anthropic Claude via AWS Bedrock
    """
    try:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": messages
        }
        
        # Add tools if provided
        if tools:
            body["tools"] = tools
            logger.info(f"Added {len(tools)} tools to request")
            
        body_json = json.dumps(body)
        
        response = bedrock_runtime.invoke_model( modelId=model_id,body=body_json)
        response_body = json.loads(response.get('body').read())
        
        # logger.info(f"Bedrock API Raw Response: {json.dumps(response_body, indent=2)}")
        return response_body
        
    except ClientError as err:
        logger.error(f"A client error occurred: {err.response['Error']['Message']}")
        raise

class AISocketServer:
    def __init__(self, host="localhost", port=8888):
        self.host = host
        self.port = port
        self.max_retries = 3
        self.mcp_client = None
        self.socket_server_instance = None
        self.bedrock_runtime = boto3.client(
            service_name='bedrock-runtime',
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        )

    async def mcpCall(self, tool_call: dict, client: Client, user_id: str = None):
        """Execute MCP tool call with user context."""
        try:
            tool_name = tool_call["name"]
            tool_args = tool_call["input"]
            logger.info(f"Executing tool: {tool_name} with args: {tool_args} for user_id: {user_id}")
            
            if tool_call["type"] == "tool":
                if tool_args and len(tool_args) > 0:
                    result = await client.call_tool(tool_name, tool_args)
                else:
                    result = await client.call_tool(tool_name)
            elif tool_call["type"] == "resource":
                result = await client.read_resource(tool_name)
            elif tool_call["type"] == "resource_template":
                # logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!! resource_template')
                a_uri = re.split(r"{|}", tool_name)
                i = 0
                for key, a_value in tool_args.items():
                    if i * 2 + 1 < len(a_uri):
                        a_uri[i * 2 + 1] = str(a_value)
                        i += 1
                uri = "".join(a_uri)
                logger.info(f"Constructed URI for resource template: {uri}")
                if (uri == "sql+db://sql/list_databases"):
                    uri = f"sql+db://sql/list_databases/{user_id}"
                result = await client.read_resource(uri)
            else:
                raise ValueError(f"Unknown tool type: {tool_call['type']}")
            
            logger.info(f"Tool {tool_name} executed successfully for user_id: {user_id}")
            # logger.info(result)
            
            # Handle result formatting (existing logic)
            if hasattr(result, 'content') and result.content:
                if isinstance(result.content, list) and len(result.content) > 0:
                    first_content = result.content[0]
                    if hasattr(first_content, 'text'):
                        result_text = first_content.text
                    else:
                        result_text = str(first_content)
                else:
                    result_text = str(result.content)
            elif hasattr(result, 'text'):
                result_text = result.text
            else:
                result_text = str(result)
            
            class ResultWrapper:
                def __init__(self, text):
                    self.text = text
            
            return [ResultWrapper(result_text)]
            
        except Exception as e:
            logger.error(f"Error in mcpCall for tool {tool_call.get('name', 'unknown')} (user_id: {user_id}): {str(e)}")
            class ErrorResult:
                def __init__(self, error_msg):
                    self.text = json.dumps({"error": error_msg})
            return [ErrorResult(str(e))]

# Trong main.py - Cập nhật execute_tool_calls_parallel

    async def execute_tool_calls_parallel(self, tool_calls, client, tool_lookup, original_name_lookup, user_id: str = None):
        """Execute multiple tool calls in parallel with user_id context."""
        chart_base64_data = None
        if user_id is None:
            logger.warning(f"Received None user_id in execute_tool_calls_parallel")
            user_id = "unknown"
        async def execute_single_tool_call(tool_call):
            nonlocal chart_base64_data
            tool_name = tool_call["name"]
            arguments = tool_call.get("input", {})
            
            logger.info(f"Processing tool call: {tool_name} with args: {arguments} for user_id: {user_id}")
            
            if tool_name not in tool_lookup:
                logger.error(f"Unknown tool name: {tool_name} for user_id: {user_id}")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_call.get("id", "unknown"),
                    "content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {tool_name}"})}]
                }
            
            tool_type = tool_lookup[tool_name]
            original_name = original_name_lookup.get(tool_name, tool_name)
            
            tool_dict = {
                "id": tool_call.get("id", "unknown"),
                "type": tool_type,
                "name": original_name,
                "input": arguments,
            }
            
            try:
                logger.info(f"Executing tool call: {tool_name} for user_id: {user_id}")
                async with asyncio.timeout(30):
                    # Truyền user_id vào mcpCall
                    result = await self.mcpCall(tool_dict, client, user_id)
                
                result_text = (
                    result[0].text
                    if result and len(result) > 0
                    else "No result returned"
                )
                
                try:
                    result_json = json.loads(result_text)
                    if isinstance(result_json, dict) and "error" in result_json:
                        logger.warning(f"Tool call returned error for user_id {user_id}: {result_json['error']}")
                    
                    # Handle chart creation
                    if tool_name == "chart_create_chart" and isinstance(result_json, dict):
                        if "chart_image_base64" in result_json:
                            chart_base64_data = result_json["chart_image_base64"]
                            logger.info(f"Chart image base64 captured from chart_create_chart tool for user_id: {user_id}")
                            result_text = json.dumps({
                                "message": "Chart image generated successfully.",
                                "chart_path": result_json.get("chart_image_path", "")
                            })
                        else:
                            logger.warning(f"chart_create_chart tool did not return chart_image_base64 for user_id: {user_id}")
                    
                except json.JSONDecodeError:
                    logger.debug(f"Tool result is not JSON format for user_id {user_id}: {result_text[:100]}...")
                except Exception as e:
                    logger.warning(f"Error processing tool result for chart (user_id: {user_id}): {e}")
                
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_call.get("id", "unknown"),
                    "content": [{"type": "text", "text": result_text}]
                }
                
            except asyncio.TimeoutError:
                logger.error(f"Tool call timeout for tool: {tool_name} (user_id: {user_id})")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_call.get("id", "unknown"),
                    "content": [{"type": "text", "text": json.dumps({"error": f"Tool call timeout for {tool_name}"})}]
                }
            except Exception as e:
                logger.error(f"Tool call failed for {tool_name} (user_id: {user_id}): {str(e)}")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_call.get("id", "unknown"),
                    "content": [{"type": "text", "text": json.dumps({"error": f"Tool call failed: {str(e)}"})}]
                }
        
        start_time = time.time()
        logger.info(f"Starting parallel execution of {len(tool_calls)} tool calls for user_id: {user_id}")
        tasks = [execute_single_tool_call(tool_call) for tool_call in tool_calls]
        tool_results = await asyncio.gather(*tasks, return_exceptions=True)
        execution_time = time.time() - start_time
        logger.info(f"Parallel tool execution completed in {execution_time:.2f} seconds for user_id: {user_id}")
        
        processed_results = []
        for i, result in enumerate(tool_results):
            if isinstance(result, Exception):
                logger.error(f"Tool call {i} failed with exception for user_id {user_id}: {result}")
                processed_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_calls[i].get("id", "unknown"),
                    "content": [{"type": "text", "text": json.dumps({"error": f"Tool execution failed: {str(result)}"})}]
                })
            else:
                processed_results.append(result)
        
        return processed_results, chart_base64_data

    async def _setup_mcp_client(self, user_id=None):
        """Initializes and activates the MCP client with user_id context."""
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
        
        # Set up environment variables for MCP server
        env_vars = os.environ.copy()
        if user_id != None:
            env_vars["USER_ID"] = str(user_id)
            logger.info(f"Setting USER_ID={user_id} for MCP server")
        
        transport = PythonStdioTransport(
            script_path=server_path, 
            python_cmd=python_cmd,
            env=env_vars  # Pass environment variables
        )
        client_instance = Client(transport)
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempting to initialize MCP client (attempt {attempt + 1}/{self.max_retries}) with user_id: {user_id}")
                await client_instance.__aenter__()
                self.mcp_client = client_instance
                
                # Wait for tools to be ready
                for wait_attempt in range(5):
                    tool_list = await self.mcp_client.list_tools()
                    resource_list = await self.mcp_client.list_resources()
                    resource_template_list = await self.mcp_client.list_resource_templates()
                    if tool_list or resource_list or resource_template_list:
                        logger.info(f"MCP client ready after {wait_attempt + 1} attempt(s) for user_id: {user_id}")
                        return
                    logger.info("Tool list empty, retrying...")
                    await asyncio.sleep(1)
                    
                await client_instance.__aexit__(None, None, None)
                raise RuntimeError("Tool/resource/resource_template list still empty after retries")
                
            except Exception as e:
                logger.warning(f"MCP client initialization attempt {attempt + 1} failed for user_id {user_id}: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
                if client_instance and client_instance.is_connected:
                    try:
                        await client_instance.__aexit__(None, None, None)
                    except Exception as exit_e:
                        logger.warning(f"Error during failed client setup cleanup: {exit_e}")
                self.mcp_client = None
                await asyncio.sleep(1)

    async def _message_processor_task(self):
        """
        An asyncio task that continuously processes messages from the queue.
        Updated to handle user_id.
        """
        while True:
            conversation_id, user_message, username, user_id, response_future = await message_queue.get()
            logger.info(f"Dequeued message for conversation {conversation_id}, user_id: {user_id}")
            response = {}
            try:
                # Truyền user_id vào _process_message_async
                response = await self._process_message_async(
                    conversation_id, user_message, username, user_id, self.mcp_client
                )
                if not response_future.done():
                    response_future.set_result(response)
            except Exception as e:
                logger.error(f"Error processing dequeued message for {conversation_id} (user_id: {user_id}): {e}")
                response = {"status": "error", "error": f"Internal processing error: {str(e)}"}
                if not response_future.done():
                    response_future.set_exception(e)
            finally:
                message_queue.task_done()
                logger.info(f"Processing complete for {conversation_id} (user_id: {user_id}). Status: {response.get('status', 'unknown')}")


    async def _process_message_async(self, conversation_id, user_message, username, user_id, mcp_client: Client):
        """
        The actual async message processing logic with user_id for permission control.
        """
        chart_image_base64 = None
        try:
            logger.info(f"Processing message for conversation {conversation_id}, user_id: {user_id}")
            
            # Set environment variable cho MCP server
            os.environ["USER_ID"] = str(user_id)
            logger.info(f"Set USER_ID environment variable to: {user_id}")
            
            if not mcp_client:
                logger.error("MCP client is not initialized or connected during _process_message_async.")
                return {"status": "error", "error": "Server not fully ready. Please try again."}
            

            
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
            
            client = mcp_client
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
            
            tool_lookup = {}
            original_name_lookup = {}

            # Process tools
            for tool in tools:
                sanitized_name = tool["name"]
                original_name = helper_functions.get_original_tool_name(sanitized_name)
                tool_lookup[sanitized_name] = "tool"
                original_name_lookup[sanitized_name] = original_name

            # Process resources
            for resource in resources:
                sanitized_name = resource["name"]
                original_name = helper_functions.get_original_tool_name(sanitized_name)
                tool_lookup[sanitized_name] = "resource"
                original_name_lookup[sanitized_name] = original_name

            # Process resource templates
            for resource_template in resource_templates:
                sanitized_name = resource_template["name"]
                original_name = helper_functions.get_original_tool_name(sanitized_name)
                tool_lookup[sanitized_name] = "resource_template"
                original_name_lookup[sanitized_name] = original_name

            list_of_tools = resources + resource_templates + tools
            logger.info(f"Available tools: {list(tool_lookup.keys())}")
            
            model_id = "us.anthropic.claude-3-haiku-20240307-v1:0"
            max_tokens = 2000
            
            if conversation_id not in message_history:
                message_history[conversation_id] = []
            
            # FIXED: Ensure proper message format for Bedrock
            message_history[conversation_id].append(
                {"role": "user", "content": user_message}
            )
            
            sys_prompt = get_dynamic_sys_prompt(context_type, context_name)
            logger.info(f"User message: {user_message}")
            logger.info(
                f"System prompt: {sys_prompt['content'][:200]}..."
            )
            
            max_iterations = 10
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"LLM iteration {iteration}/{max_iterations}")
                
                try:
                    start_llm_call = time.time()
                    async with asyncio.timeout(120):
                        response = await generate_message(
                            self.bedrock_runtime,
                            model_id,
                            sys_prompt["content"],
                            message_history[conversation_id],
                            max_tokens,
                            tools=list_of_tools
                        )
                    
                    logger.info(f"LLM call completed in {time.time() - start_llm_call:.2f} seconds " )
                except asyncio.TimeoutError:
                    logger.error("LLM timeout during chat completion.")
                    return {"status": "error", "error": "LLM response timeout"}
                except ClientError as e:
                    logger.error(f"Bedrock client error: {e.response['Error']['Message']}")
                    return {"status": "error", "error": f"Bedrock client error: {e.response['Error']['Message']}"}
                
                if not response.get("content"):
                    logger.error("Empty content in Bedrock response")
                    return {"status": "error", "error": "No response from Bedrock"}
                
                # FIXED: Handle Bedrock response format properly
                content = response.get("content", [])
                if not content:
                    logger.error("No content in response")
                    return {"status": "error", "error": "No content in response"}
                
                # Check if response contains tool calls
                has_tool_calls = False
                tool_calls = []
                answer = ""
                
                # FIXED: Create sanitized content for message history
                sanitized_content = []
                
                for item in content:
                    if item.get("type") == "text":
                        answer += item.get("text", "")
                        sanitized_content.append(item)  # Text items don't need sanitization
                    elif item.get("type") == "tool_use":
                        has_tool_calls = True
                        tool_calls.append(item)
                        
                        # FIXED: Sanitize tool name in the content for message history
                        original_tool_name = item.get("name", "")
                        sanitized_tool_name = helper_functions.sanitize_tool_name(original_tool_name)
                        
                        # Create sanitized version for message history
                        sanitized_tool_item = {
                            "type": "tool_use",
                            "id": item.get("id"),
                            "name": sanitized_tool_name,  # Use sanitized name
                            "input": item.get("input", {})
                        }
                        sanitized_content.append(sanitized_tool_item)
                        
                        # Also update the tool_calls list with sanitized names
                        tool_calls[-1]["name"] = sanitized_tool_name
                
                if has_tool_calls:
                    logger.info(f"LLM requested {len(tool_calls)} tool calls")
                    # FIXED: Add assistant message with sanitized tool names
                    message_history[conversation_id].append(
                        {
                            "role": "assistant",
                            "content": sanitized_content,  # Use sanitized content
                        }
                    )
                    
                    start_tool_execution = time.time()
                    tool_results, captured_chart_data = await self.execute_tool_calls_parallel(
                        tool_calls, client, tool_lookup, original_name_lookup,user_id
                    )
                    logger.info(f"Tool execution completed in {time.time() - start_tool_execution:.2f} seconds")
                    
                    if captured_chart_data:
                        chart_image_base64 = captured_chart_data
                    
                    # FIXED: Add tool results in proper Bedrock format
                    message_history[conversation_id].append({
                        "role": "user",
                        "content": tool_results
                    })
                    continue
                
                elif response.get("stop_reason") == "end_turn":
                    # FIXED: Add final assistant message properly
                    message_history[conversation_id].append(
                        {"role": "assistant", "content": answer}
                    )
                    logger.info(
                        f"Generated final answer for conversation {conversation_id}"
                    )
                    final_response_payload = {"status": "success", "content": answer}
                    if chart_image_base64:
                        final_response_payload["chart_image_base64"] = chart_image_base64
                        logger.info("Added chart_image_base64 to final response.")
                    return final_response_payload
                
                else:
                    logger.warning(f"Unexpected stop reason: {response.get('stop_reason')}")
                    return {
                        "status": "error",
                        "error": f"Unexpected stop reason: {response.get('stop_reason')}",
                    }
            
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
        global main_event_loop
        main_event_loop = asyncio.get_running_loop()
        try:
            await self._setup_mcp_client()
            self.socket_server_instance = SocketServer(self.host, self.port, enqueue_message_callback)
            socket_server_thread = threading.Thread(target=self.socket_server_instance.start_server, daemon=True)
            socket_server_thread.start()
            logger.info("SocketServer started in a separate thread.")
            self.processor_task = asyncio.create_task(self._message_processor_task())
            logger.info("Message processor task started.")
            await asyncio.Future()
        except asyncio.CancelledError:
            logger.info("Server tasks cancelled.")
        except Exception as e:
            logger.error(f"Error during server startup in start_and_serve: {e}")
            self.stop_server()

    def stop_server(self):
        logger.info("Stopping server...")
        if self.socket_server_instance:
            self.socket_server_instance.stop_server()
        if hasattr(self, 'processor_task') and self.processor_task:
            self.processor_task.cancel()
            try:
                if main_event_loop and not main_event_loop.is_closed():
                    asyncio.run_coroutine_threadsafe(self.processor_task, main_event_loop).result(timeout=5)
                else:
                    logger.warning("Main event loop not available or closed for processor task cancellation.")
            except Exception as e:
                logger.warning(f"Error cancelling processor task: {e}")
        if self.mcp_client:
            try:
                loop_to_use = None
                if main_event_loop and not main_event_loop.is_closed():
                    loop_to_use = main_event_loop
                else:
                    try:
                        loop_to_use = asyncio.get_event_loop()
                    except RuntimeError:
                        loop_to_use = asyncio.new_event_loop()
                if loop_to_use and not loop_to_use.is_closed():
                    loop_to_use.run_until_complete(self.mcp_client.__aexit__(None, None, None))
                else:
                    logger.warning("No active event loop to close MCP client gracefully.")
            except Exception as e:
                logger.warning(f"Error closing MCP client during server shutdown: {str(e)}")
            finally:
                self.mcp_client = None

def main():
    global main_event_loop
    host = os.getenv("PYTHON_AI_HOST", "localhost")
    port = int(os.getenv("PYTHON_AI_PORT", 8888))
    required_env_vars = ["AWS_DEFAULT_REGION"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return
    server = AISocketServer(host, port)
    try:
        asyncio.run(server.start_and_serve())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt in main, stopping server...")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
    finally:
        server.stop_server()

if __name__ == "__main__":
    main()