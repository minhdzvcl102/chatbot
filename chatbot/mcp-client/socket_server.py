import socket
import threading
import json
import asyncio
import logging
import time
import sys

# Fix Unicode encoding issues for Windows
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SocketServer:
    def __init__(self, host='localhost', port=8888, process_message_callback=None):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = {}
        self.running = False
        self.connection_timeout = 60
        self.process_message_callback = process_message_callback

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
                                    # Run async function in new event loop
                                    response = self._run_async_processing(
                                        conversation_id, 
                                        user_message, 
                                        username
                                    )
                                except Exception as e:
                                    logger.error(f"Error in async processing: {str(e)}")
                                    response = {"status": "error", "error": f"Processing failed: {str(e)}"}
                            
                            response_json = json.dumps(response, ensure_ascii=False) + '\n'
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
                except UnicodeDecodeError as e:
                    logger.error(f"Unicode decode error from {address}: {e}")
                    error_response = {"status": "error", "error": "Invalid character encoding"}
                    try:
                        client_socket.send((json.dumps(error_response) + '\n').encode('utf-8'))
                    except:
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
        """Run async processing in a new event loop"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.process_message_callback(conversation_id, user_message, username)
                )
            finally:
                # Clean up the loop
                try:
                    # Cancel all pending tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    # Wait for all tasks to be cancelled
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as cleanup_error:
                    logger.warning(f"Error during loop cleanup: {cleanup_error}")
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"Error in _run_async_processing: {str(e)}")
            return {"status": "error", "error": f"Async processing failed: {str(e)}"}

    def start_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.settimeout(1.0)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            logger.info(f"Socket Server started on {self.host}:{self.port}")
            
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
            logger.info("Socket Server stopped")