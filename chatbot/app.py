import socket
import json
import threading
import time
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

# Add random import back for fallback responses
import random

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_service.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Set console encoding to UTF-8
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, host='localhost', port=8888):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.clients = {}
        self.conversation_history = {}
        
        # AI service configuration
        self.max_history_length = int(os.getenv('MAX_HISTORY_LENGTH', '20'))
        self.response_delay = float(os.getenv('AI_RESPONSE_DELAY', '0.5'))
        
        # Initialize OpenAI client with DashScope
        self.openai_client = None
        self.setup_openai_client()
        
        logger.info(f"🤖 AI Service initialized on {host}:{port}")
    
    def setup_openai_client(self):
        """Setup OpenAI client with Alibaba DashScope"""
        try:
            api_key = os.getenv("ALIBABA_API_KEY")
            base_url = os.getenv("BASE_API_URL")
            
            if not api_key:
                logger.warning("⚠️ ALIBABA_API_KEY not found, using fallback responses")
                return
            
            self.openai_client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            
            logger.info("✅ OpenAI client initialized with DashScope")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI client: {e}")
            logger.warning("⚠️ Falling back to local responses")
    
    def start_server(self):
        """Start the socket server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            
            self.running = True
            logger.info(f"🚀 AI Service server started on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    logger.info(f"🔗 New connection from {address}")
                    
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        logger.error(f"❌ Socket error: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Failed to start server: {e}")
        finally:
            self.cleanup()
    
    def handle_client(self, client_socket, address):
        """Handle individual client connection"""
        client_id = f"{address[0]}:{address[1]}"
        self.clients[client_id] = {
            'socket': client_socket,
            'address': address,
            'connected_at': datetime.now()
        }
        
        try:
            buffer = ""
            while self.running:
                # Receive data from client
                data = client_socket.recv(4096).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                
                # Process complete messages (newline-delimited JSON)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    
                    if line:
                        try:
                            request = json.loads(line)
                            response = self.process_request(request)
                            
                            if response:
                                response_json = json.dumps(response) + '\n'
                                client_socket.send(response_json.encode('utf-8'))
                                
                        except json.JSONDecodeError as e:
                            logger.error(f"❌ JSON decode error from {client_id}: {e}")
                            error_response = {
                                'status': 'error',
                                'error': 'Invalid JSON format',
                                'timestamp': datetime.now().isoformat()
                            }
                            client_socket.send((json.dumps(error_response) + '\n').encode('utf-8'))
                        
                        except Exception as e:
                            logger.error(f"❌ Error processing request from {client_id}: {e}")
                            error_response = {
                                'status': 'error',
                                'error': str(e),
                                'timestamp': datetime.now().isoformat()
                            }
                            client_socket.send((json.dumps(error_response) + '\n').encode('utf-8'))
                
        except ConnectionResetError:
            logger.info(f"🔌 Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"❌ Error handling client {client_id}: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
            
            if client_id in self.clients:
                del self.clients[client_id]
            
            logger.info(f"👋 Client {client_id} connection closed")
    
    def process_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process AI request and generate response"""
        try:
            request_type = request.get('type', 'chat')
            conversation_id = request.get('conversationId')
            message = request.get('message', '')
            username = request.get('username', 'User')
            
            logger.info(f"📥 Processing {request_type} request for conversation {conversation_id}")
            
            if request_type == 'chat':
                return self.handle_chat_request(conversation_id, message, username)
            elif request_type == 'system':
                return self.handle_system_request(request)
            else:
                return {
                    'status': 'error',
                    'error': f'Unknown request type: {request_type}',
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Error processing request: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def handle_chat_request(self, conversation_id: str, message: str, username: str) -> Dict[str, Any]:
        """Handle chat request and generate AI response"""
        try:
            # Initialize conversation history if not exists
            if conversation_id not in self.conversation_history:
                self.conversation_history[conversation_id] = []
            
            # Add user message to history
            self.conversation_history[conversation_id].append({
                'role': 'user',
                'content': message,
                'username': username,
                'timestamp': datetime.now().isoformat()
            })
            
            # Trim history if too long
            if len(self.conversation_history[conversation_id]) > self.max_history_length:
                self.conversation_history[conversation_id] = self.conversation_history[conversation_id][-self.max_history_length:]
            
            # Simulate AI processing delay
            time.sleep(self.response_delay)
            
            # Generate AI response based on the message
            ai_response = self.generate_ai_response(message, conversation_id, username)
            
            # Add AI response to history
            self.conversation_history[conversation_id].append({
                'role': 'assistant',
                'content': ai_response,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"🤖 Generated AI response for conversation {conversation_id}")
            
            return {
                'status': 'success',
                'content': ai_response,
                'conversation_id': conversation_id,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error handling chat request: {e}")
            return {
                'status': 'error',
                'error': f'Failed to process chat request: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def generate_ai_response(self, message: str, conversation_id: str, username: str) -> str:
        """Generate AI response using OpenAI/DashScope or fallback to local responses"""
        
        # Try OpenAI/DashScope first
        if self.openai_client:
            try:
                return self.generate_openai_response(message, conversation_id, username)
            except Exception as e:
                logger.error(f"❌ OpenAI API error: {e}")
                logger.info("🔄 Falling back to local response generation")
        
        # Fallback to local response generation
        return self.generate_local_response(message, conversation_id, username)
    
    def generate_openai_response(self, message: str, conversation_id: str, username: str) -> str:
        """Generate response using OpenAI/DashScope API"""
        try:
            logger.info(f"🤖 Generating OpenAI response for user: {username}")
            
            # Prepare conversation history for API
            messages: List[ChatCompletionMessageParam] = []
            
            # Add conversation context
            if conversation_id in self.conversation_history:
                history = self.conversation_history[conversation_id]
                # Take last few messages for context (limit to save tokens)
                recent_history = history[-10:] if len(history) > 10 else history
                
                for msg in recent_history:
                    if msg['role'] in ['user', 'assistant']:
                        content = msg['content']
                        if msg['role'] == 'user' and 'username' in msg:
                            content = f"{msg['username']}: {content}"
                        
                        messages.append({
                            "role": msg['role'],
                            "content": content
                        })
            
            # Add current message
            messages.append({
                "role": "user", 
                "content": f"{username}: {message}"
            })
            
            # Add system message for context
            system_message = {
                "role": "system",
                "content": f"""Bạn là một AI assistant thông minh và hữu ích. 
                Hãy trả lời bằng tiếng Việt một cách tự nhiên và thân thiện.
                Người dùng hiện tại là {username}.
                Hãy trả lời ngắn gọn và phù hợp với ngữ cảnh cuộc hội thoại."""
            }
            messages.insert(0, system_message)
            
            # Call OpenAI API
            response = self.openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "qwen-turbo"),
                messages=messages,
                max_tokens=int(os.getenv("MAX_TOKENS", "500")),
                temperature=float(os.getenv("TEMPERATURE", "0.7")),
                stream=False
            )
            
            ai_response = response.choices[0].message.content.strip()
            logger.info(f"✅ OpenAI response generated successfully")
            
            return ai_response
            
        except Exception as e:
            logger.error(f"❌ Error calling OpenAI API: {e}")
            raise e
    
    def generate_local_response(self, message: str, conversation_id: str, username: str) -> str:
        """Generate fallback response locally"""
        message_lower = message.lower().strip()
        
        # Greeting responses
        greetings = ['hello', 'hi', 'hey', 'xin chào', 'chào', 'good morning', 'good afternoon', 'good evening']
        if any(greeting in message_lower for greeting in greetings):
            responses = [
                f"Xin chào {username}! Tôi có thể giúp gì cho bạn hôm nay?",
                f"Chào {username}! Bạn cần hỗ trợ gì không?",
                f"Hello {username}! Rất vui được gặp bạn. Tôi có thể hỗ trợ gì?",
                f"Chào bạn {username}! Tôi ở đây để giúp đỡ. Bạn muốn hỏi gì?"
            ]
            return random.choice(responses)
        
        # Question responses  
        if any(starter in message_lower for starter in ['what', 'how', 'why', 'gì', 'sao', 'thế nào', 'tại sao', 'làm sao']):
            responses = [
                f"Đây là một câu hỏi hay! Để tôi suy nghĩ về điều đó cho bạn.",
                f"Câu hỏi thú vị! Dựa trên hiểu biết của tôi, đây là quan điểm của tôi:",
                f"Tôi rất vui khi giúp bạn hiểu rõ hơn về vấn đề này.",
                f"Đó là điều đáng khám phá. Đây là những gì tôi có thể chia sẻ:"
            ]
            base_response = random.choice(responses)
            
            # Add context-specific information
            if any(word in message_lower for word in ['thời tiết', 'weather']):
                return f"{base_response} Tôi không có quyền truy cập dữ liệu thời tiết thời gian thực, nhưng tôi khuyên bạn nên kiểm tra dịch vụ thời tiết đáng tin cậy."
            elif any(word in message_lower for word in ['thời gian', 'time', 'giờ']):
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return f"{base_response} Thời gian server hiện tại là {current_time}."
            elif any(word in message_lower for word in ['giúp', 'help', 'hỗ trợ']):
                return f"{base_response} Tôi là trợ lý AI được thiết kế để giúp với các nhiệm vụ khác nhau và trả lời câu hỏi. Bạn có thể hỏi tôi bất cứ điều gì!"
            else:
                return f"{base_response} Tôi sẽ cố gắng cung cấp thông tin hữu ích về câu hỏi của bạn."
        
        # Programming/technical questions
        programming_keywords = ['code', 'programming', 'function', 'algorithm', 'debug', 'error', 'javascript', 'python', 'nodejs', 'lập trình', 'code', 'thuật toán']
        if any(keyword in message_lower for keyword in programming_keywords):
            responses = [
                "Tôi rất vui khi giúp bạn với câu hỏi lập trình! Bạn có thể cung cấp chi tiết cụ thể hơn không?",
                "Câu hỏi lập trình là chuyên môn của tôi! Bạn muốn được hỗ trợ khía cạnh nào cụ thể?",
                "Để tôi giúp bạn với vấn đề kỹ thuật này. Bạn có thể chia sẻ thêm ngữ cảnh không?",
                "Tôi có thể hỗ trợ với các vấn đề coding. Bạn đang làm việc với ngôn ngữ lập trình hoặc framework nào?"
            ]
            return random.choice(responses)
        
        # Farewell responses
        farewells = ['bye', 'goodbye', 'see you', 'farewell', 'take care', 'tạm biệt', 'chào', 'hẹn gặp lại']
        if any(farewell in message_lower for farewell in farewells):
            responses = [
                f"Tạm biệt {username}! Rất vui được trò chuyện với bạn.",
                f"Chăm sóc bản thân nhé {username}! Bạn có thể quay lại bất cứ lúc nào.",
                f"Hẹn gặp lại {username}! Chúc bạn một ngày tuyệt vời!",
                f"Tạm biệt {username}! Cảm ơn bạn đã trò chuyện."
            ]
            return random.choice(responses)
        
        # Thank you responses
        thanks = ['thank', 'thanks', 'appreciate', 'cảm ơn', 'cám ơn', 'thanks']
        if any(thank in message_lower for thank in thanks):
            responses = [
                f"Bạn rất được chào đón {username}! Vui khi được giúp đỡ.",
                f"Không có gì {username}! Đó là điều tôi ở đây để làm.",
                f"Vui khi có thể giúp được {username}! Hãy hỏi tôi nếu bạn cần gì khác.",
                f"Không có chi {username}! Tôi rất vui khi được hỗ trợ bạn."
            ]
            return random.choice(responses)
        
        # Default responses for general messages
        default_responses = [
            f"Tôi hiểu những gì bạn đang nói, {username}. Bạn có thể nói thêm về điều đó không?",
            f"Điều đó thú vị, {username}. Bạn có muốn thảo luận thêm về chủ đề này không?",
            f"Tôi nghe bạn, {username}. Tôi có thể giúp bạn điều gì với vấn đề này?",
            f"Cảm ơn bạn đã chia sẻ, {username}. Bạn muốn biết thêm về điều gì?",
            f"Tôi hiểu, {username}. Có điều gì cụ thể bạn muốn được hỗ trợ không?",
            f"Điều đó có lý, {username}. Tôi có thể giúp gì cho bạn hôm nay không?"
        ]
        
        return random.choice(default_responses)
    
    def handle_system_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle system requests like health checks, stats, etc."""
        try:
            command = request.get('command', '')
            
            if command == 'health':
                return {
                    'status': 'success',
                    'health': 'healthy',
                    'uptime': time.time(),
                    'active_clients': len(self.clients),
                    'active_conversations': len(self.conversation_history),
                    'timestamp': datetime.now().isoformat()
                }
            
            elif command == 'stats':
                return {
                    'status': 'success',
                    'stats': {
                        'active_clients': len(self.clients),
                        'active_conversations': len(self.conversation_history),
                        'total_messages': sum(len(history) for history in self.conversation_history.values()),
                        'server_start_time': datetime.now().isoformat(),
                        'configuration': {
                            'max_history_length': self.max_history_length,
                            'response_delay': self.response_delay
                        }
                    },
                    'timestamp': datetime.now().isoformat()
                }
            
            elif command == 'clear_history':
                conversation_id = request.get('conversation_id')
                if conversation_id and conversation_id in self.conversation_history:
                    del self.conversation_history[conversation_id]
                    return {
                        'status': 'success',
                        'message': f'History cleared for conversation {conversation_id}',
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {
                        'status': 'error',
                        'error': 'Invalid or missing conversation_id',
                        'timestamp': datetime.now().isoformat()
                    }
            
            else:
                return {
                    'status': 'error',
                    'error': f'Unknown system command: {command}',
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Error handling system request: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def cleanup(self):
        """Clean up server resources"""
        logger.info("🧹 Cleaning up AI Service...")
        
        self.running = False
        
        # Close all client connections
        for client_id, client_info in self.clients.items():
            try:
                client_info['socket'].close()
            except:
                pass
        
        self.clients.clear()
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        logger.info("✅ AI Service cleanup completed")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Received signal {signum}, shutting down...")
        self.cleanup()
        sys.exit(0)

def main():
    """Main function to start the AI service"""
    # Load environment variables
    load_dotenv()
    
    # Get configuration from environment variables
    host = os.getenv('AI_SERVICE_HOST', 'localhost')
    port = int(os.getenv('AI_SERVICE_PORT', '8888'))
    
    # Create AI service instance
    ai_service = AIService(host, port)
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, ai_service.signal_handler)
    signal.signal(signal.SIGTERM, ai_service.signal_handler)
    
    try:
        # Start the server
        ai_service.start_server()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
    finally:
        ai_service.cleanup()

if __name__ == "__main__":
    main()