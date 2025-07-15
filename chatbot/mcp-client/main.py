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
def enqueue_message_callback(conversation_id, user_message, username, response_future: Future):
    """
    Callback for SocketServer to put messages into the async queue.
    It now accepts a Future to set the result later.
    """
    logger.info(f"Enqueuing message for conversation {conversation_id}")
    try:
        if main_event_loop is None or main_event_loop.is_closed():
            raise RuntimeError("Main event loop is not set or is closed.")
        asyncio.run_coroutine_threadsafe(
            message_queue.put((conversation_id, user_message, username, response_future)), main_event_loop
        )
    except Exception as e:
        logger.error(f"Failed to enqueue message: {e}")
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
       - Use `sql+db://sql/list_databases` to list available databases
       - Use `sql+db://sql/list_tables/{db_name}` to list tables in a database
       - Use `sql+db://sql/schema/{db_name}` to get database schema
       - Use `sql_query_db` for SQL queries
    2. For general questions or document-related questions: 
       - ALWAYS use `rag_query` to search knowledge base FIRST
       - Only answer based on the results from rag_query
    3. For visualization: Use `chart_create_chart` when explicitly requested

    RESPONSE FORMAT:
    - If rag_query returns relevant documents: Base your answer on those documents
    - If rag_query returns no documents: Say "I don't have information about this in the uploaded documents"
    - Always cite which documents your answer comes from

    When working with Vietnamese:
    - "liệt kê db" = "list databases" → use sql+db://sql/list_databases
    - "hiển thị bảng" = "show tables" → use sql+db://sql/list_tables/{db_name}
    - "cấu trúc db" = "database schema" → use sql+db://sql/schema/{db_name}
    - For any other question → use rag_query first

    REMEMBER: Always call rag_query for document-related questions before answering!"""

    if context_type == "db" and context_name:
        base_prompt += f"\n\nCurrent database context: {context_name}. Prioritize SQL tools for database-related queries."
    else:
        base_prompt += "\n\nNo specific database context. For database questions, start with list_databases tool. For other questions, use rag_query."
    
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
        
        response = bedrock_runtime.invoke_model(body=body_json, modelId=model_id)
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

    async def mcpCall(self, tool_call: dict, client: Client):
        try:
            tool_name = tool_call["name"]
            tool_args = tool_call["input"]
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
            
            # Fixed: Handle CallToolResult properly
            if hasattr(result, 'content') and result.content:
                # For tools that return content list
                if isinstance(result.content, list) and len(result.content) > 0:
                    # Get the first content item
                    first_content = result.content[0]
                    if hasattr(first_content, 'text'):
                        result_text = first_content.text
                    else:
                        result_text = str(first_content)
                else:
                    result_text = str(result.content)
            elif hasattr(result, 'text'):
                # For results that have direct text attribute
                result_text = result.text
            else:
                # Fallback: convert to string
                result_text = str(result)
            
            # Return in the expected format (as a list with text attribute)
            class ResultWrapper:
                def __init__(self, text):
                    self.text = text
            
            return [ResultWrapper(result_text)]
            
        except Exception as e:
            logger.error(f"Error in mcpCall for tool {tool_call.get('name', 'unknown')}: {str(e)}")
            class ErrorResult:
                def __init__(self, error_msg):
                    self.text = json.dumps({"error": error_msg})
            return [ErrorResult(str(e))]

    async def execute_tool_calls_parallel(self, tool_calls, client, tool_lookup, original_name_lookup):
        """Execute multiple tool calls in parallel for better performance - FIXED for chart handling"""
        chart_base64_data = None
        
        async def execute_single_tool_call(tool_call):
            nonlocal chart_base64_data
            # FIXED: Bedrock format uses different structure
            tool_name = tool_call["name"]  # This is the sanitized name
            arguments = tool_call.get("input", {})
            
            logger.info(f"Processing tool call: {tool_name} with args: {arguments}")
            
            if tool_name not in tool_lookup:
                logger.error(f"Unknown tool name: {tool_name}")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_call.get("id", "unknown"),
                    "content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {tool_name}"})}]
                }
            
            tool_type = tool_lookup[tool_name]
            # Get the original tool name for MCP call
            original_name = original_name_lookup.get(tool_name, tool_name)
            
            tool_dict = {
                "id": tool_call.get("id", "unknown"),
                "type": tool_type,
                "name": original_name,  # Use original name for MCP
                "input": arguments,
            }
            
            try:
                logger.info(f"Executing tool call: {tool_name}")
                async with asyncio.timeout(30):
                    result = await self.mcpCall(tool_dict, client)
                result_text = (
                    result[0].text
                    if result and len(result) > 0
                    else "No result returned"
                )
                
                try:
                    result_json = json.loads(result_text)
                    if isinstance(result_json, dict) and "error" in result_json:
                        logger.warning(f"Tool call returned error: {result_json['error']}")
                    
                    # FIXED: Check for chart_create_chart tool and capture base64 data
                    if tool_name == "chart_create_chart" and isinstance(result_json, dict):
                        if "chart_image_base64" in result_json:
                            chart_base64_data = result_json["chart_image_base64"]
                            logger.info("Chart image base64 captured from chart_create_chart tool.")
                            # Return success message instead of the full result
                            result_text = json.dumps({
                                "message": "Chart image generated successfully.",
                                "chart_path": result_json.get("chart_image_path", "")
                            })
                        else:
                            logger.warning("chart_create_chart tool did not return chart_image_base64")
                    
                except json.JSONDecodeError:
                    # If result is not JSON, keep as is
                    logger.debug(f"Tool result is not JSON format: {result_text[:100]}...")
                except Exception as e:
                    logger.warning(f"Error processing tool result for chart: {e}")
                
                # FIXED: Return Bedrock format for tool results
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_call.get("id", "unknown"),
                    "content": [{"type": "text", "text": result_text}]
                }
            except asyncio.TimeoutError:
                logger.error(f"Tool call timeout for tool: {tool_name}")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_call.get("id", "unknown"),
                    "content": [{"type": "text", "text": json.dumps({"error": f"Tool call timeout for {tool_name}"})}]
                }
            except Exception as e:
                logger.error(f"Tool call failed for {tool_name}: {str(e)}")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_call.get("id", "unknown"),
                    "content": [{"type": "text", "text": json.dumps({"error": f"Tool call failed: {str(e)}"})}]
                }
        
        start_time = time.time()
        logger.info(f"Starting parallel execution of {len(tool_calls)} tool calls")
        tasks = [execute_single_tool_call(tool_call) for tool_call in tool_calls]
        tool_results = await asyncio.gather(*tasks, return_exceptions=True)
        execution_time = time.time() - start_time
        logger.info(f"Parallel tool execution completed in {execution_time:.2f} seconds")
        
        processed_results = []
        for i, result in enumerate(tool_results):
            if isinstance(result, Exception):
                logger.error(f"Tool call {i} failed with exception: {result}")
                processed_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_calls[i].get("id", "unknown"),
                    "content": [{"type": "text", "text": json.dumps({"error": f"Tool execution failed: {str(result)}"})}]
                })
            else:
                processed_results.append(result)
        
        return processed_results, chart_base64_data

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
        client_instance = Client(transport)
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Attempting to initialize MCP client (attempt {attempt + 1}/{self.max_retries})"
                )
                await client_instance.__aenter__()
                self.mcp_client = client_instance
                for wait_attempt in range(5):
                    tool_list = await self.mcp_client.list_tools()
                    resource_list = await self.mcp_client.list_resources()
                    resource_template_list = await self.mcp_client.list_resource_templates()
                    if tool_list or resource_list or resource_template_list:
                        logger.info(f"Tool ready after {wait_attempt + 1} attempt(s)")
                        return
                    logger.info("Tool list empty, retrying...")
                    await asyncio.sleep(1)
                await client_instance.__aexit__(None, None, None)
                raise RuntimeError(
                    "Tool/resource/resource_template list still empty after retries"
                )
            except Exception as e:
                logger.warning(
                    f"MCP client initialization attempt {attempt + 1} failed: {str(e)}"
                )
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
        This task runs in the main event loop.
        """
        while True:
            conversation_id, user_message, username, response_future = await message_queue.get()
            logger.info(f"Dequeued message for conversation {conversation_id}")
            response = {}
            try:
                response = await self._process_message_async(conversation_id, user_message, username, self.mcp_client)
                if not response_future.done():
                    response_future.set_result(response)
            except Exception as e:
                logger.error(f"Error processing dequeued message for {conversation_id}: {e}")
                response = {"status": "error", "error": f"Internal processing error: {str(e)}"}
                if not response_future.done():
                    response_future.set_exception(e)
            finally:
                message_queue.task_done()
                logger.info(f"Processing complete for {conversation_id}. Status: {response.get('status', 'unknown')}")

    async def _process_message_async(self, conversation_id, user_message, username, mcp_client: Client):
        """
        The actual async message processing logic, run on the main event loop.
        FIXED: Proper handling of Bedrock message format and tool calls
        """
        chart_image_base64 = None
        try:
            logger.info(f"Processing message for conversation {conversation_id}")
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
            
            model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
            max_tokens = 1000
            
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
                    logger.info(f"LLM call completed in {time.time() - start_llm_call:.2f} seconds")
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
                
                for item in content:
                    if item.get("type") == "text":
                        answer += item.get("text", "")
                    elif item.get("type") == "tool_use":
                        has_tool_calls = True
                        tool_calls.append(item)
                
                if has_tool_calls:
                    logger.info(f"LLM requested {len(tool_calls)} tool calls")
                    # FIXED: Add assistant message in proper Bedrock format
                    message_history[conversation_id].append(
                        {
                            "role": "assistant",
                            "content": content,
                        }
                    )
                    
                    start_tool_execution = time.time()
                    tool_results, captured_chart_data = await self.execute_tool_calls_parallel(
                        tool_calls, client, tool_lookup, original_name_lookup
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