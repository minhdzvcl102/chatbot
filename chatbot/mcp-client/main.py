import asyncio
import json
import os
import re
import time
import sys
from dotenv import load_dotenv
from fastmcp.client import Client
from fastmcp.client.transports import PythonStdioTransport
from openai import AsyncOpenAI
import helper_functions
import logging
from socket_server import SocketServer

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


def should_reset_context(conversation_id, user_message):
    """Determine if we should reset the conversation context"""
    previous_context = conversation_context.get(conversation_id, {})
    previous_type = previous_context.get("type")
    previous_name = previous_context.get("name")

    # Let LLM decide context in system prompt; reset if no prior context
    if not previous_type:
        logger.info(f"New context established: rag:general")
        conversation_context[conversation_id] = {"type": "rag", "name": "general"}
        return False, "rag", "general"
    return False, previous_type, previous_name


def get_dynamic_sys_prompt(context_type=None, context_name=None):
    """Generate system prompt to guide LLM in intelligently selecting tools"""
    base_prompt = """You are a data analytics chatbot specialized in business intelligence and data interpretation.

    IMPORTANT: You MUST use tools to answer user questions about data, databases, or analytics. Do NOT answer from general knowledge unless no relevant tool results are found. Your goal is to intelligently select the appropriate tool based on the question's intent and context, prioritizing rag_query for general or ambiguous questions.

    Your expertise includes:
    - Data interpretation and business insights
    - Statistical analysis and trend identification
    - Performance metrics and KPI analysis
    - Data visualization recommendations
    - Business intelligence and reporting
    - SQL query execution and database analysis
    - Document and knowledge base querying

    TOOL SELECTION GUIDELINES:
    1. By default, use rag_query for general, ambiguous, or knowledge-based questions (e.g., 'explain', 'define', 'what is', 'giải thích', 'là gì', 'phân tích doanh thu') to search for relevant information in documents.
    2. Only use sql_query_db, list_databases, list_tables, or get_schema when:
       - The question explicitly mentions database-related terms (e.g., 'database', 'table', 'sql', 'cơ sở dữ liệu', 'bảng') or names that appear to be database identifiers (e.g., 'php3_wd19314').
       - The user explicitly requests to use SQL (e.g., 'dùng SQL', 'use SQL').
       - rag_query returns no relevant results, and the question implies structured data (e.g., 'list products', 'sales data').
    3. For chart/visualization requests:
       - If the question implies document-based data (e.g., 'summary from report'), use rag_query.
       - If the question implies structured data (e.g., 'sales data from table'), use sql_query_db.
       - Explain visualization options after retrieving data.
    4. Use conversation history to infer context if the current question is ambiguous. For example:
       - If previous questions were about documents, prioritize rag_query.
       - If previous questions mentioned a specific database (e.g., 'php3_wd19314'), consider sql_query_db.
    5. If rag_query returns no relevant results, try sql_query_db as a fallback for data-related questions.
    6. Always provide the business meaning of findings in your response.
    7. If no relevant data is found, inform the user and suggest rephrasing the question or checking other sources.

    Examples:
    - Question: "Phân tích doanh thu hòa phát các năm" → Use rag_query to find information in documents, as it is a general analysis request.
    - Question: "Liệt kê 20 sản phẩm trong php3_wd19314" → Use sql_query_db with database 'php3_wd19314', as it mentions a likely database name and implies structured data.
    - Question: "Dùng SQL để lấy doanh thu từ bảng sales" → Use sql_query_db, as the user explicitly requests SQL.
    - Question: "Doanh thu là gì?" → Use rag_query to find definitions in documents.

    Available tools:
    - sql_query_db: Execute SQL queries on databases
    - list_databases: List available databases
    - list_tables: List tables in a specific database
    - get_schema: Get schema of a specific database
    - rag_query: Query document knowledge base
    - rag_get_collection_info: Get information about document collections
    + 
    + TOOL CALL NAMES (for LLM):
    + - sql_query_db
    + - sql+db://sql/list_databases
    + - sql+db://sql/list_tables/{db_name}
    + - sql+db://sql/schema/{db_name}
    + - rag_query
    + - rag_get_collection_info
    
    Valid tool call names (exact match only):
    - sql_query_db
    - sql+db://sql/list_databases
    - sql+db://sql/list_tables/{db_name}
    - sql+db://sql/schema/{db_name}
    - rag_query
    - rag_get_collection_info

    WORKFLOW:
    1. Analyze the question and conversation history to infer the user's intent.
    2. Select the appropriate tool based on the intent:
       - Use rag_query by default for general, ambiguous, or document-related questions.
       - Use SQL tools (sql_query_db, list_databases, list_tables, get_schema) only for explicit database-related questions or when explicitly requested (e.g., 'dùng SQL').
       - If rag_query returns no results, try sql_query_db for data-related questions.
    3. Execute the selected tool and verify the results.
    4. Provide a clear answer with business context, citing the source (database or document).
    5. If no data is found, inform the user and suggest alternative approaches.

    When working with SQL databases:
    - Always use fully qualified table names with database prefix (e.g., `database_name.table_name`).
    - If you get 'No database selected' error, use list_databases or list_tables to explore available data.
    - Start with list_databases or list_tables if unsure about available data.

    When working with documents:
    - Use rag_query to search for relevant information in the document knowledge base.
    - If rag_query returns no results, consider using sql_query_db as a fallback for data-related questions.
    - Use rag_get_collection_info to understand available document collections if needed."""

    if context_type == "db" and context_name:
        base_prompt += f"\n\nCurrent database context: {context_name}. Use format: `{context_name}.table_name` in SQL queries. Prioritize sql_query_db for this question unless it clearly indicates a document-based query."
    else:
        base_prompt += "\n\nNo specific database context provided. Use rag_query by default for this question, unless it explicitly mentions database-related terms or requests to use SQL."

    return {"role": "system", "content": base_prompt}


class AISocketServer:
    def __init__(self, host="localhost", port=8888):
        self.host = host
        self.port = port
        self.max_retries = 3
        self.server = SocketServer(host, port, self.process_message)

    async def mcpCall(self, tool_call: dict, client):
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
        async def execute_single_tool_call(tool_call):
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
                async with asyncio.timeout(15):
                    result = await self.mcpCall(tool_dict, client)

                result_text = (
                    result[0].text
                    if result and len(result) > 0
                    else "No result returned"
                )

                # Check for tool call errors but don't stop execution
                try:
                    result_json = json.loads(result_text)
                    if isinstance(result_json, dict) and "error" in result_json:
                        logger.warning(f"Tool call returned error: {result_json['error']}")
                except json.JSONDecodeError:
                    pass

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
        
        return processed_results

    async def initialize_mcp_client(self):
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

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Attempting to initialize MCP client (attempt {attempt + 1}/{self.max_retries})"
                )

                transport = PythonStdioTransport(
                    script_path=server_path, python_cmd=python_cmd
                )
                client = Client(transport)

                await client.__aenter__()  # ✅ Sử dụng nếu KHÔNG dùng `async with`
                self._client_cleanup = (
                    client.__aexit__
                )  # Ghi nhớ hàm exit để sau gọi khi cần
                self.client = client

                # Đợi cho đến khi tool list có dữ liệu
                for wait_attempt in range(5):  # thử 5 lần, mỗi lần cách nhau 1 giây
                    tool_list = await client.list_tools()
                    resource_list = await client.list_resources()
                    resource_template_list = await client.list_resource_templates()

                    if tool_list or resource_list or resource_template_list:
                        logger.info(f"Tool ready after {wait_attempt + 1} attempt(s)")
                        return client

                    logger.info("Tool list empty, retrying...")
                    await asyncio.sleep(1)

                # Nếu không thành công
                await client.__aexit__(None, None, None)  # cleanup
                raise RuntimeError(
                    "Tool/resource/resource_template list still empty after retries"
                )

            except Exception as e:
                logger.warning(
                    f"MCP client initialization attempt {attempt + 1} failed: {str(e)}"
                )
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1)

    async def process_message(self, conversation_id, user_message, username):
        client = None
        try:
            logger.info(f"Processing message for conversation {conversation_id}")

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

            client = await self.initialize_mcp_client()

            async with asyncio.timeout(120):
                tool_list = await client.list_tools()
                resource_list = await client.list_resources()
                resource_template_list = await client.list_resource_templates()

            tools = []
            for tool in tool_list:
                try:
                    tool_dict = json.loads(tool.model_dump_json())
                    tools.append(tool_dict)
                except Exception as e:
                    logger.warning(f"Failed to serialize tool: {e}")

            resources = []
            for resource in resource_list:
                try:
                    resource_dict = json.loads(resource.model_dump_json())
                    resources.append(resource_dict)
                except Exception as e:
                    logger.warning(f"Failed to serialize resource: {e}")

            resource_templates = []
            for resource_template in resource_template_list:
                try:
                    rt_dict = json.loads(resource_template.model_dump_json())
                    resource_templates.append(rt_dict)
                except Exception as e:
                    logger.warning(f"Failed to serialize resource template: {e}")

            tools = helper_functions.mcp_tools_to_tool_list(tools)
            resources = helper_functions.mcp_resources_to_tool_list(resources)
            resource_templates = helper_functions.mcp_resource_templates_to_tool_list(
                resource_templates
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

            list_of_tools = resources + resource_templates + tools

            logger.info(f"Available tools: {list(tool_lookup.keys())}")

            llm = AsyncOpenAI(
                base_url=os.getenv("BASE_API_URL"),
                api_key=os.getenv("ALIBABA_API_KEY"),
                timeout=90.0,
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
                    async with asyncio.timeout(90):
                        response = await llm.chat.completions.create(
                            model="qwen-plus",
                            messages=[sys_prompt] + message_history[conversation_id],
                            tools=list_of_tools,
                        )
                except asyncio.TimeoutError:
                    logger.error("LLM timeout")
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
                    return {"status": "success", "content": answer}

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

                    # Execute all tool calls in parallel
                    tool_results = await self.execute_tool_calls_parallel(
                        choice.message.tool_calls, client, tool_lookup
                    )
                    
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
        finally:
            if client:
                try:
                    loop = asyncio.get_event_loop()
                    if not loop.is_closed():
                        await client.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing MCP client: {str(e)}")

    def start_server(self):
        self.server.start_server()

    def stop_server(self):
        self.server.stop_server()


def main():
    host = os.getenv("PYTHON_AI_HOST", "localhost")
    port = int(os.getenv("PYTHON_AI_PORT", 8888))

    required_env_vars = ["BASE_API_URL", "ALIBABA_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return

    server = AISocketServer(host, port)

    try:
        server.start_server()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, stopping server...")
        server.stop_server()
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        server.stop_server()


if __name__ == "__main__":
    main()