import asyncio
import json
import os
import re
import time
from dotenv import load_dotenv
from fastmcp.client import Client
from fastmcp.client.transports import PythonStdioTransport
from openai import AsyncOpenAI
import helper_functions
import logging
from socket_server import SocketServer

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

message_history = {}
conversation_db_context = {}  # Track database context per conversation

def get_dynamic_sys_prompt(current_db=None):
    """Generate system prompt based on current database context"""
    base_prompt = """You are a helpful assistant. Your job is to assist the user by all means possible.
    Make sure to format your message like utilizing newlines, lists and tables.
    For chart-related requests, use the query_for_chart tool to retrieve chart metadata.
    
    When working with SQL databases:
    - Always use fully qualified table names with database prefix (e.g., `database_name.table_name`)
    - If you get "No database selected" error, retry with proper database prefix"""
    
    if current_db:
        base_prompt += f"\n    - Current database context: {current_db}. Use format: `{current_db}.table_name`"
    
    return {"role": "system", "content": base_prompt}

def extract_database_from_message(message):
    """Extract database name from user message"""
    # Pattern to match database references
    db_patterns = [
        r'database\s+(\w+)',
        r'db\s+(\w+)',
        r'(\w+)\.(\w+)',  # table.column format
        r'trong\s+(\w+)',  # Vietnamese: "trong database_name"
        r'từ\s+(\w+)',     # Vietnamese: "từ database_name"
    ]
    
    message_lower = message.lower()
    for pattern in db_patterns:
        matches = re.findall(pattern, message_lower)
        if matches:
            # Return the first non-empty match
            for match in matches:
                if isinstance(match, tuple):
                    # For patterns like (\w+)\.(\w+), return the first part (database name)
                    db_name = match[0]
                else:
                    db_name = match
                
                # Filter out common words that aren't database names
                if db_name not in ['select', 'from', 'where', 'and', 'or', 'table', 'column']:
                    return db_name
    
    return None

def should_reset_context(conversation_id, user_message):
    """Determine if we should reset the conversation context"""
    # Extract database from current message
    current_db = extract_database_from_message(user_message)
    
    if not current_db:
        return False, None
    
    # Check if this is a different database than before
    previous_db = conversation_db_context.get(conversation_id)
    
    if previous_db and previous_db != current_db:
        logger.info(f"Database context change detected: {previous_db} -> {current_db}")
        return True, current_db
    elif not previous_db:
        logger.info(f"New database context established: {current_db}")
        conversation_db_context[conversation_id] = current_db
        return False, current_db
    
    return False, current_db

class AISocketServer:
    def __init__(self, host='localhost', port=8888):
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
            logger.error(f"Error in mcpCall for tool {tool_call.get('function', {}).get('name', 'unknown')}: {str(e)}")
            class ErrorResult:
                def __init__(self, error_msg):
                    self.text = json.dumps({"error": error_msg})
            
            return [ErrorResult(str(e))]

    async def initialize_mcp_client(self):
        server_path = os.path.join(os.path.dirname(__file__), "..", "mcp-server", "server.py")
        python_cmd = os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "python.exe")
        
        if not os.path.exists(server_path):
            raise FileNotFoundError(f"MCP server script not found: {server_path}")
        if not os.path.exists(python_cmd):
            raise FileNotFoundError(f"Python executable not found: {python_cmd}")
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempting to initialize MCP client (attempt {attempt + 1}/{self.max_retries})")
                client = Client(PythonStdioTransport(script_path=server_path, python_cmd=python_cmd))
                await client.__aenter__()
                logger.info("MCP client initialized successfully")
                return client
            except Exception as e:
                logger.warning(f"MCP client initialization attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1)

    async def process_message(self, conversation_id, user_message, username):
        client = None
        try:
            logger.info(f"Processing message for conversation {conversation_id}")
            
            # Check if we need to reset context due to database change
            should_reset, current_db = should_reset_context(conversation_id, user_message)
            
            if should_reset:
                # Reset message history for this conversation
                logger.info(f"Resetting conversation context for {conversation_id}")
                message_history[conversation_id] = []
                conversation_db_context[conversation_id] = current_db
            elif current_db:
                # Update database context
                conversation_db_context[conversation_id] = current_db
            
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
            resource_templates = helper_functions.mcp_resource_templates_to_tool_list(resource_templates)

            tool_list_names = [tool["function"]["name"] for tool in tools]
            resource_list_names = [resource["function"]["name"] for resource in resources]
            resource_template_list_names = [resource_template["function"]["name"] for resource_template in resource_templates]
            
            tool_lookup = {tool: "tool" for tool in tool_list_names}
            tool_lookup.update({resource: "resource" for resource in resource_list_names})
            tool_lookup.update({resource_template: "resource_template" for resource_template in resource_template_list_names})
            list_of_tools = tools + resources + resource_templates

            logger.info(f"Available tools: {list(tool_lookup.keys())}")

            llm = AsyncOpenAI(
                base_url=os.getenv("BASE_API_URL"),
                api_key=os.getenv("ALIBABA_API_KEY"),
                timeout=90.0
            )

            if conversation_id not in message_history:
                message_history[conversation_id] = []

            message_history[conversation_id].append({"role": "user", "content": user_message})

            chart_keywords = ['vẽ biểu đồ', 'chart', 'graph', 'biểu đồ']
            is_chart_request = any(keyword in user_message.lower() for keyword in chart_keywords)

            if is_chart_request:
                try:
                    async with asyncio.timeout(15):
                        result = await client.call_tool('query_for_chart', {'query': user_message})
                    
                    if result and len(result) > 0:
                        result_text = result[0].text
                        try:
                            result_json = json.loads(result_text)
                            if result_json and result_json[0].get('metadata'):
                                return {
                                    "status": "success",
                                    "content": "Preparing chart data...",
                                    "metadata": result_json[0]['metadata']
                                }
                            else:
                                return {"status": "error", "error": "No chart data found"}
                        except json.JSONDecodeError:
                            return {"status": "error", "error": "Invalid chart data format"}
                    else:
                        return {"status": "error", "error": "No result from query_for_chart"}
                except asyncio.TimeoutError:
                    logger.error("Timeout calling query_for_chart")
                    return {"status": "error", "error": "Chart query timeout"}
                except Exception as e:
                    logger.error(f"Error calling query_for_chart: {str(e)}")
                    return {"status": "error", "error": f"Chart query failed: {str(e)}"}
            else:
                # Generate dynamic system prompt based on current database context
                current_db_context = conversation_db_context.get(conversation_id)
                sys_prompt = get_dynamic_sys_prompt(current_db_context)
                
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
                                tools=list_of_tools
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
                        message_history[conversation_id].append({"role": "assistant", "content": answer})
                        logger.info(f"Generated final answer for conversation {conversation_id}")
                        return {"status": "success", "content": answer}
                    
                    elif choice.finish_reason == "tool_calls":
                        logger.info(f"LLM requested {len(choice.message.tool_calls)} tool calls")
                        
                        # Add assistant message with tool calls to history
                        message_history[conversation_id].append({
                            "role": "assistant", 
                            "content": None, 
                            "tool_calls": choice.message.tool_calls
                        })
                        
                        # Execute all tool calls
                        for tool_call in choice.message.tool_calls:
                            tool_name = tool_call.function.name
                            arguments = tool_call.function.arguments
                            
                            try:
                                if isinstance(arguments, str):
                                    arguments = json.loads(arguments)
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse tool arguments: {e}")
                                return {"status": "error", "error": f"Invalid tool arguments: {str(e)}"}
                            
                            if tool_name not in tool_lookup:
                                logger.error(f"Unknown tool name: {tool_name}")
                                message_history[conversation_id].append({
                                    "role": "tool",
                                    "content": json.dumps({"error": f"Unknown tool: {tool_name}"}),
                                    "tool_call_id": tool_call.id
                                })
                                continue
                            
                            tool_type = tool_lookup[tool_name]
                            tool_dict = {
                                "id": tool_call.id,
                                "type": tool_type,
                                "function": {
                                    "name": tool_name,
                                    "arguments": arguments
                                }
                            }
                            
                            try:
                                logger.info(f"Executing tool call: {tool_name}")
                                async with asyncio.timeout(15):
                                    result = await self.mcpCall(tool_dict, client)
                                
                                result_text = result[0].text if result and len(result) > 0 else "No result returned"
                                
                                # Check for tool call errors but don't stop execution
                                try:
                                    result_json = json.loads(result_text)
                                    if isinstance(result_json, dict) and "error" in result_json:
                                        logger.warning(f"Tool call returned error: {result_json['error']}")
                                        # Let LLM handle the error and potentially retry with different approach
                                except json.JSONDecodeError:
                                    pass
                                
                                message_history[conversation_id].append({
                                    "role": "tool",
                                    "content": result_text,
                                    "tool_call_id": tool_call.id
                                })
                                
                            except asyncio.TimeoutError:
                                logger.error(f"Tool call timeout for tool: {tool_name}")
                                error_result = json.dumps({"error": f"Tool call timeout for {tool_name}"})
                                message_history[conversation_id].append({
                                    "role": "tool",
                                    "content": error_result,
                                    "tool_call_id": tool_call.id
                                })
                            except Exception as e:
                                logger.error(f"Tool call failed: {str(e)}")
                                error_result = json.dumps({"error": f"Tool call failed: {str(e)}"})
                                message_history[conversation_id].append({
                                    "role": "tool",
                                    "content": error_result,
                                    "tool_call_id": tool_call.id
                                })
                        
                        # Continue the loop to call LLM again with tool results
                        continue
                    
                    else:
                        logger.warning(f"Unexpected finish reason: {choice.finish_reason}")
                        return {"status": "error", "error": f"Unexpected finish reason: {choice.finish_reason}"}
                
                # If we reach here, we've hit the max iterations
                logger.warning(f"Reached maximum iterations ({max_iterations}) without final answer")
                return {"status": "error", "error": "Maximum conversation iterations reached"}

        except asyncio.TimeoutError:
            logger.error(f"Timeout processing message for conversation {conversation_id}")
            return {"status": "error", "error": "Processing timeout"}
        except ConnectionError as e:
            logger.error(f"Connection error for conversation {conversation_id}: {str(e)}")
            return {"status": "error", "error": f"Connection error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error processing message for conversation {conversation_id}: {str(e)}")
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
    host = os.getenv('PYTHON_AI_HOST', 'localhost')
    port = int(os.getenv('PYTHON_AI_PORT', 8888))
    
    required_env_vars = ['BASE_API_URL', 'ALIBABA_API_KEY']
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