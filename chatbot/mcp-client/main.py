
import asyncio
import json
import os
import re
import socket
import threading
import time
from dotenv import load_dotenv
from fastmcp.client import Client
from fastmcp.client.transports import PythonStdioTransport
from openai import AsyncOpenAI
import helper_functions
import logging

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
SYS_PROMPT = {
    "role": "system",
    "content": """You are a helpful assistant. Your job is to assist the user by all means possible.
    Make sure to format your message like utilizing newlines, lists and tables.
    For chart-related requests, use the query_for_chart tool to retrieve chart metadata."""
}

class AISocketServer:
    def __init__(self, host='localhost', port=8888):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = {}
        self.running = False
        self.connection_timeout = 30
        self.max_retries = 3
        
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
                for key, value in tool_args.items():
                    if i * 2 + 1 < len(a_uri):
                        a_uri[i * 2 + 1] = str(value)
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
            
            client = await self.initialize_mcp_client()
            
            async with asyncio.timeout(10):
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
                timeout=30.0
            )

            if conversation_id not in message_history:
                message_history[conversation_id] = []

            message_history[conversation_id].append({"role": "user", "content": user_message})

            # Check for chart request
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
                async with asyncio.timeout(30):
                    response = await llm.chat.completions.create(
                        model="qwen-plus",
                        messages=[SYS_PROMPT] + message_history[conversation_id],
                        tools=list_of_tools
                    )

                if not response.choices or len(response.choices) == 0:
                    logger.error("Empty choices in LLM response")
                    return {"status": "error", "error": "No response from LLM"}

                if response.choices[0].finish_reason == "stop":
                    answer = response.choices[0].message.content
                    message_history[conversation_id].append({"role": "assistant", "content": answer})
                    logger.info(f"Generated answer for conversation {conversation_id}")
                    return {"status": "success", "content": answer}

                elif response.choices[0].finish_reason == "tool_calls":
                    tool_calls = []
                    for tool in response.choices[0].message.tool_calls:
                        tool_dict = {
                            "id": tool.id,
                            "type": "function",
                            "function": {
                                "name": tool.function.name,
                                "arguments": tool.function.arguments
                            }
                        }
                        tool_calls.append(tool_dict)
                    
                    message_history[conversation_id].append({
                        "role": "assistant", 
                        "content": None, 
                        "tool_calls": response.choices[0].message.tool_calls
                    })
                    
                    for i, tool_call in enumerate(tool_calls):
                        try:
                            if isinstance(tool_call["function"]["arguments"], str):
                                tool_call["function"]["arguments"] = json.loads(tool_call["function"]["arguments"])
                            
                            tool_name = tool_call["function"]["name"]
                            if tool_name in tool_lookup:
                                tool_call["type"] = tool_lookup[tool_name]
                            else:
                                logger.error(f"Unknown tool: {tool_name}")
                                continue
                            
                            logger.info(f"Executing tool call {i+1}/{len(tool_calls)}: {tool_name}")
                            
                            async with asyncio.timeout(15):
                                result = await self.mcpCall(tool_call, client)
                            
                            if result and len(result) > 0:
                                result_text = result[0].text
                                
                                try:
                                    result_json = json.loads(result_text)
                                    if "error" in result_json:
                                        logger.error(f"Tool call error: {result_json['error']}")
                                        return {"status": "error", "error": result_json["error"]}
                                except json.JSONDecodeError:
                                    pass
                                
                                message_history[conversation_id].append({
                                    "role": "tool",
                                    "content": result_text,
                                    "tool_call_id": tool_call["id"]
                                })
                            else:
                                logger.warning(f"Empty result from tool call: {tool_name}")
                                message_history[conversation_id].append({
                                    "role": "tool",
                                    "content": "No result returned",
                                    "tool_call_id": tool_call["id"]
                                })
                            
                        except asyncio.TimeoutError:
                            logger.error(f"Tool call timeout for tool: {tool_call['function']['name']}")
                            return {"status": "error", "error": "Tool call timeout"}
                        except Exception as e:
                            logger.error(f"Error in tool call {i}: {str(e)}")
                            return {"status": "error", "error": f"Tool call failed: {str(e)}"}

                    try:
                        async with asyncio.timeout(30):
                            response = await llm.chat.completions.create(
                                model="qwen-plus",
                                messages=[SYS_PROMPT] + message_history[conversation_id],
                                tools=list_of_tools
                            )
                        
                        if response.choices[0].finish_reason == "stop":
                            answer = response.choices[0].message.content
                            message_history[conversation_id].append({"role": "assistant", "content": answer})
                            logger.info(f"Generated answer after tool call for conversation {conversation_id}")
                            return {"status": "success", "content": answer}
                            
                    except asyncio.TimeoutError:
                        logger.error("LLM timeout after tool calls")
                        return {"status": "error", "error": "LLM response timeout"}

                return {"status": "error", "error": "Unexpected error in processing"}

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
                    await client.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing MCP client: {str(e)}")

    def handle_client(self, client_socket, address):
        logger.info(f"New client connected from {address}")
        client_socket.settimeout(self.connection_timeout)
        
        try:
            while self.running:
                try:
                    data = client_socket.recv(4096).decode('utf-8')
                    if not data:
                        logger.info(f"Client {address} closed connection")
                        break

                    try:
                        request = json.loads(data.strip())
                        logger.info(f"Received request from {address}: {request.get('type', 'unknown')}")
                        
                        if request.get('type') == 'chat':
                            conversation_id = request.get('conversationId')
                            user_message = request.get('message')
                            username = request.get('username', 'User')
                            
                            if not conversation_id or not user_message:
                                response = {"status": "error", "error": "Missing conversationId or message"}
                            else:
                                try:
                                    try:
                                        loop = asyncio.get_running_loop()
                                        import concurrent.futures
                                        with concurrent.futures.ThreadPoolExecutor() as executor:
                                            future = executor.submit(self._run_async_processing, conversation_id, user_message, username)
                                            response = future.result(timeout=60)
                                    except RuntimeError:
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        try:
                                            response = loop.run_until_complete(
                                                self.process_message(conversation_id, user_message, username)
                                            )
                                        finally:
                                            loop.close()
                                except Exception as e:
                                    logger.error(f"Error in async processing: {str(e)}")
                                    response = {"status": "error", "error": f"Processing failed: {str(e)}"}
                            
                            response_json = json.dumps(response) + '\n'
                            client_socket.send(response_json.encode('utf-8'))
                            logger.info(f"Sent response to {address}: {response.get('status', 'unknown')}")
                            
                        else:
                            error_response = {"status": "error", "error": "Unknown request type"}
                            client_socket.send((json.dumps(error_response) + '\n').encode('utf-8'))
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error from {address}: {e}")
                        error_response = {"status": "error", "error": "Invalid JSON format"}
                        client_socket.send((json.dumps(error_response) + '\n').encode('utf-8'))
                
                except socket.timeout:
                    logger.warning(f"Socket timeout for client {address}")
                    break
                except ConnectionResetError:
                    logger.info(f"Client {address} reset connection")
                    break
                except BrokenPipeError:
                    logger.info(f"Broken pipe for client {address}")
                    break
                
        except Exception as e:
            logger.error(f"Error handling client {address}: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
            logger.info(f"Client {address} disconnected")

    def _run_async_processing(self, conversation_id, user_message, username):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.process_message(conversation_id, user_message, username)
            )
        finally:
            loop.close()

    def start_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.settimeout(1.0)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            logger.info(f"AI Socket Server started on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        name=f"Client-{address[0]}:{address[1]}"
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"Error accepting client connection: {e}")
                        time.sleep(1)
                    
        except Exception as e:
            logger.error(f"Error starting server: {e}")
        finally:
            self.stop_server()

    def stop_server(self):
        logger.info("Stopping server...")
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            logger.info("AI Socket Server stopped")

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