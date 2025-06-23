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

# Set up logging with more detailed format
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

# Global variables
message_history = {}
SYS_PROMPT = {
    "role": "system",
    "content": """You are a helpful assistant. Your job is to assist the user by all means possible.
    Make sure to format your message like utilizing newlines, lists and tables."""
}

class AISocketServer:
    def __init__(self, host='localhost', port=8888):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = {}
        self.running = False
        self.connection_timeout = 30  # seconds
        self.max_retries = 3
        
    async def mcpCall(self, tool_call: dict, client):
        """Handle MCP tool calls with better error handling"""
        try:
            if tool_call["type"] == "tool":
                if len(tool_call["function"]["arguments"].items()) != 0:
                    return await client.call_tool(tool_call["function"]["name"], tool_call["function"]["arguments"])
                else:
                    return await client.call_tool(tool_call["function"]["name"])
            elif tool_call["type"] == "resource":
                return await client.read_resource(tool_call["function"]["name"])
            elif tool_call["type"] == "resource_template":
                a_uri = re.split(r"{|}", tool_call["function"]["name"])
                i = 0
                for key, value in tool_call["function"]["arguments"].items():
                    a_uri[i * 2 + 1] = value
                    i += 1
                uri = "".join(a_uri)
                return await client.read_resource(uri)
        except Exception as e:
            logger.error(f"Error in mcpCall: {str(e)}")
            raise

    async def initialize_mcp_client(self):
        """Initialize MCP client with retry logic"""
        server_path = os.path.join(os.path.dirname(__file__), "..", "mcp-server", "server.py")
        python_cmd = os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "python.exe")
        
        # Check if files exist
        if not os.path.exists(server_path):
            raise FileNotFoundError(f"MCP server script not found: {server_path}")
        if not os.path.exists(python_cmd):
            raise FileNotFoundError(f"Python executable not found: {python_cmd}")
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempting to initialize MCP client (attempt {attempt + 1}/{self.max_retries})")
                client = Client(PythonStdioTransport(script_path=server_path, python_cmd=python_cmd))
                await client.__aenter__()
                return client
            except Exception as e:
                logger.warning(f"MCP client initialization attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1)  # Wait before retry

    async def process_message(self, conversation_id, user_message, username):
        """Process user message and get AI response with better error handling"""
        client = None
        try:
            logger.info(f"Processing message for conversation {conversation_id}")
            
            # Initialize MCP client with retry logic
            client = await self.initialize_mcp_client()
            
            # Load tools and resources with timeout
            async with asyncio.timeout(10):  # 10 second timeout
                tool_list = await client.list_tools()
                resource_list = await client.list_resources()
                resource_template_list = await client.list_resource_templates()
            
            tools = [json.loads(tool.model_dump_json()) for tool in tool_list]
            tools = helper_functions.mcp_tools_to_tool_list(tools)
            resources = [json.loads(resource.model_dump_json()) for resource in resource_list]
            resources = helper_functions.mcp_resources_to_tool_list(resources)
            resource_templates = [json.loads(resource_template.model_dump_json()) for resource_template in resource_template_list]
            resource_templates = helper_functions.mcp_resource_templates_to_tool_list(resource_templates)

            tool_list_names = [tool["function"]["name"] for tool in tools]
            resource_list_names = [resource["function"]["name"] for resource in resources]
            resource_template_list_names = [resource_template["function"]["name"] for resource_template in resource_templates]
            
            tool_lookup = {tool: "tool" for tool in tool_list_names}
            tool_lookup.update({resource: "resource" for resource in resource_list_names})
            tool_lookup.update({resource_template: "resource_template" for resource_template in resource_template_list_names})
            list_of_tools = tools + resources + resource_templates

            # Initialize LLM with timeout and retry logic
            llm = AsyncOpenAI(
                base_url=os.getenv("BASE_API_URL"),
                api_key=os.getenv("ALIBABA_API_KEY"),
                timeout=30.0  # Add timeout
            )

            # Initialize message history for conversation
            if conversation_id not in message_history:
                message_history[conversation_id] = []

            # Add user message to history
            message_history[conversation_id].append({"role": "user", "content": user_message})

            # Call LLM with timeout
            async with asyncio.timeout(30):  # 30 second timeout
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
                tool_calls = [tool.to_dict() for tool in response.choices[0].message.tool_calls]
                message_history[conversation_id].append({
                    "role": "assistant", 
                    "content": None, 
                    "tool_calls": response.choices[0].message.tool_calls
                })
                
                for i in range(len(tool_calls)):
                    try:
                        tool_calls[i]["function"]["arguments"] = json.loads(tool_calls[i]["function"]["arguments"])
                        tool_calls[i]["type"] = tool_lookup[tool_calls[i]["function"]["name"]]
                        
                        # Execute tool call with timeout
                        async with asyncio.timeout(15):
                            tmp = await self.mcpCall(tool_calls[i], client)
                        
                        message_history[conversation_id].append({
                            "role": "tool",
                            "content": tmp[0].text,
                            "tool_call_id": tool_calls[i]["id"]
                        })
                        
                        if "error" in tmp[0].text:
                            logger.error(f"Tool call error: {tmp[0].text}")
                            return {"status": "error", "error": json.loads(tmp[0].text)}
                        
                    except asyncio.TimeoutError:
                        logger.error(f"Tool call timeout for tool: {tool_calls[i]['function']['name']}")
                        return {"status": "error", "error": "Tool call timeout"}
                    except Exception as e:
                        logger.error(f"Error in tool call {i}: {str(e)}")
                        return {"status": "error", "error": f"Tool call failed: {str(e)}"}

                # Run LLM again with tool results
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
            # Clean up MCP client
            if client:
                try:
                    await client.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing MCP client: {str(e)}")

    def handle_client(self, client_socket, address):
        """Handle individual client connection with improved error handling"""
        logger.info(f"New client connected from {address}")
        client_socket.settimeout(self.connection_timeout)
        
        try:
            while self.running:
                try:
                    # Receive data from client with timeout
                    data = client_socket.recv(4096).decode('utf-8')
                    if not data:
                        logger.info(f"Client {address} closed connection")
                        break

                    # Parse JSON request
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
                                # Process message asynchronously with proper event loop handling
                                try:
                                    # Check if we're in an async context
                                    try:
                                        loop = asyncio.get_running_loop()
                                        # We're already in an async context, create a new thread
                                        import concurrent.futures
                                        with concurrent.futures.ThreadPoolExecutor() as executor:
                                            future = executor.submit(self._run_async_processing, conversation_id, user_message, username)
                                            response = future.result(timeout=60)  # 60 second timeout
                                    except RuntimeError:
                                        # No running event loop, create new one
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
                            
                            # Send response back to client
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
        """Helper method to run async processing in a new event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.process_message(conversation_id, user_message, username)
            )
        finally:
            loop.close()

    def start_server(self):
        """Start the socket server with improved error handling"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.settimeout(1.0)  # Allow periodic checks for self.running
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            logger.info(f"AI Socket Server started on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        name=f"Client-{address[0]}:{address[1]}"
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.timeout:
                    # This is expected due to server socket timeout
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"Error accepting client connection: {e}")
                        time.sleep(1)  # Brief pause before retrying
                    
        except Exception as e:
            logger.error(f"Error starting server: {e}")
        finally:
            self.stop_server()

    def stop_server(self):
        """Stop the socket server"""
        logger.info("Stopping server...")
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            logger.info("AI Socket Server stopped")

def main():
    # Get host and port from environment variables
    host = os.getenv('PYTHON_AI_HOST', 'localhost')
    port = int(os.getenv('PYTHON_AI_PORT', 8888))
    
    # Validate environment variables
    required_env_vars = ['BASE_API_URL', 'ALIBABA_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return
    
    # Create and start the server
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