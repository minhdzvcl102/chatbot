// services/websocketService.js - Frontend (Complete)
import { io } from 'socket.io-client';

class WebSocketService {
  constructor() {
    this.socket = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.currentConversationId = null;
    this.eventCallbacks = new Map();
    this.authToken = null;
  }

  // Kết nối WebSocket
  connect(serverUrl = 'http://localhost:3000') {
    if (this.socket) {
      this.disconnect();
    }

    // Lấy token từ state management (thay vì localStorage)
    const token = this.getAuthToken();
    if (!token) {
      console.error('❌ No auth token found');
      this.emit('auth_error', { message: 'No authentication token' });
      return;
    }

    console.log('🔌 Connecting to WebSocket server:', serverUrl);

    this.socket = io(serverUrl, {
      auth: {
        token: token
      },
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
      timeout: 10000
    });

    this.setupEventListeners();
  }

  // Lấy auth token (cần implement theo state management của bạn)
  getAuthToken() {
    // Thay thế bằng cách lấy token từ state management
    // Ví dụ: return store.getState().auth.token;
    // Hoặc từ context: return authContext.token;
    
    // Tạm thời sử dụng biến trong memory thay vì localStorage
    return this.authToken || null;
  }

  // Set auth token
  setAuthToken(token) {
    this.authToken = token;
  }

  // Thiết lập các event listeners
  setupEventListeners() {
    if (!this.socket) return;

    // Connection events
    this.socket.on('connect', () => {
      console.log('✅ WebSocket connected:', this.socket.id);
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.emit('connected', { socketId: this.socket.id });
    });

    this.socket.on('disconnect', (reason) => {
      console.log('❌ WebSocket disconnected:', reason);
      this.isConnected = false;
      this.emit('disconnected', { reason });
    });

    this.socket.on('connect_error', (error) => {
      console.error('❌ WebSocket connection error:', error.message);
      this.isConnected = false;
      this.emit('connection_error', { error: error.message });
    });

    this.socket.on('reconnect', (attemptNumber) => {
      console.log('🔄 WebSocket reconnected after', attemptNumber, 'attempts');
      this.isConnected = true;
      this.emit('reconnected', { attemptNumber });
      
      // Rejoin current conversation if exists
      if (this.currentConversationId) {
        this.joinConversation(this.currentConversationId);
      }
    });

    this.socket.on('reconnect_failed', () => {
      console.error('❌ WebSocket reconnection failed');
      this.isConnected = false;
      this.emit('reconnection_failed');
    });

    // Authentication events
    this.socket.on('connected', (data) => {
      console.log('🎉 Authentication successful:', data);
      this.emit('authenticated', data);
    });

    // Conversation events
    this.socket.on('joined_conversation', (data) => {
      console.log('🏠 Joined conversation:', data);
      this.currentConversationId = data.conversationId;
      this.emit('joined_conversation', data);
    });

    this.socket.on('left_conversation', (data) => {
      console.log('🚪 Left conversation:', data);
      if (this.currentConversationId === data.conversationId) {
        this.currentConversationId = null;
      }
      this.emit('left_conversation', data);
    });

    // Message events
    this.socket.on('new_message', (data) => {
      console.log('📨 New message received:', data);
      this.emit('new_message', data);
    });

    this.socket.on('ai_response', (data) => {
      console.log('🤖 AI response received:', data);
      this.emit('ai_response', data);
    });

    // User activity events
    this.socket.on('typing', (data) => {
      console.log('⌨️ Typing indicator:', data);
      this.emit('typing', data);
    });

    this.socket.on('user_joined', (data) => {
      console.log('👋 User joined:', data);
      this.emit('user_joined', data);
    });

    this.socket.on('user_left', (data) => {
      console.log('🚶 User left:', data);
      this.emit('user_left', data);
    });

    // Online users events
    this.socket.on('online_users', (data) => {
      console.log('👥 Online users updated:', data);
      this.emit('online_users', data);
    });

    // File upload events
    this.socket.on('file_uploaded', (data) => {
      console.log('📁 File uploaded:', data);
      this.emit('file_uploaded', data);
    });

    // Conversation update events
    this.socket.on('conversation_updated', (data) => {
      console.log('🔄 Conversation updated:', data);
      this.emit('conversation_updated', data);
    });

    // System events
    this.socket.on('system_message', (data) => {
      console.log('📢 System message:', data);
      this.emit('system_message', data);
    });

    // Error events
    this.socket.on('error', (data) => {
      console.error('❌ WebSocket error:', data);
      this.emit('error', data);
    });
  }

  // Ngắt kết nối WebSocket
  disconnect() {
    if (this.socket) {
      console.log('🔌 Disconnecting WebSocket...');
      this.socket.disconnect();
      this.socket = null;
    }
    this.isConnected = false;
    this.currentConversationId = null;
    this.eventCallbacks.clear();
  }

  // Tham gia conversation
  joinConversation(conversationId) {
    if (!this.socket || !this.isConnected) {
      console.warn('⚠️ WebSocket not connected');
      return false;
    }

    if (!conversationId) {
      console.error('❌ Conversation ID is required');
      return false;
    }

    console.log('🏠 Joining conversation:', conversationId);
    this.socket.emit('join_conversation', { conversationId });
    return true;
  }

  // Rời khỏi conversation
  leaveConversation(conversationId) {
    if (!this.socket || !this.isConnected) {
      console.warn('⚠️ WebSocket not connected');
      return false;
    }

    if (!conversationId) {
      conversationId = this.currentConversationId;
    }

    if (!conversationId) {
      console.error('❌ No conversation to leave');
      return false;
    }

    console.log('🚪 Leaving conversation:', conversationId);
    this.socket.emit('leave_conversation', { conversationId });
    return true;
  }

  // Gửi tin nhắn
  sendMessage(conversationId, content, role = 'user') {
    if (!this.socket || !this.isConnected) {
      console.warn('⚠️ WebSocket not connected');
      return false;
    }

    if (!conversationId || !content || content.trim() === '') {
      console.error('❌ Conversation ID and content are required');
      return false;
    }

    console.log('📤 Sending message to conversation:', conversationId);
    this.socket.emit('send_message', {
      conversationId,
      content: content.trim(),
      role
    });
    return true;
  }

  // Gửi typing indicator
  sendTyping(conversationId, isTyping) {
    if (!this.socket || !this.isConnected) {
      return false;
    }

    if (!conversationId) {
      conversationId = this.currentConversationId;
    }

    if (!conversationId) {
      return false;
    }

    this.socket.emit('typing', {
      conversationId,
      isTyping
    });
    return true;
  }

  // Thông báo file upload
  notifyFileUploaded(conversationId, fileInfo) {
    if (!this.socket || !this.isConnected) {
      console.warn('⚠️ WebSocket not connected');
      return false;
    }

    if (!conversationId || !fileInfo) {
      console.error('❌ Conversation ID and file info are required');
      return false;
    }

    console.log('📁 Notifying file upload:', fileInfo);
    this.socket.emit('file_uploaded', {
      conversationId,
      file: fileInfo
    });
    return true;
  }

  // Lấy danh sách users online
  getOnlineUsers(conversationId) {
    if (!this.socket || !this.isConnected) {
      console.warn('⚠️ WebSocket not connected');
      return false;
    }

    if (!conversationId) {
      conversationId = this.currentConversationId;
    }

    if (!conversationId) {
      console.error('❌ Conversation ID is required');
      return false;
    }

    console.log('👥 Getting online users for conversation:', conversationId);
    this.socket.emit('get_online_users', { conversationId });
    return true;
  }

  // Đăng ký event callback
  on(event, callback) {
    if (!this.eventCallbacks.has(event)) {
      this.eventCallbacks.set(event, new Set());
    }
    this.eventCallbacks.get(event).add(callback);

    // Return function để unsubscribe
    return () => {
      const callbacks = this.eventCallbacks.get(event);
      if (callbacks) {
        callbacks.delete(callback);
        if (callbacks.size === 0) {
          this.eventCallbacks.delete(event);
        }
      }
    };
  }

  // Hủy đăng ký event callback
  off(event, callback) {
    const callbacks = this.eventCallbacks.get(event);
    if (callbacks) {
      callbacks.delete(callback);
      if (callbacks.size === 0) {
        this.eventCallbacks.delete(event);
      }
    }
  }

  // Emit event tới callbacks đã đăng ký
  emit(event, data) {
    const callbacks = this.eventCallbacks.get(event);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in callback for event ${event}:`, error);
        }
      });
    }
  }

  // Kiểm tra trạng thái kết nối
  isSocketConnected() {
    return this.socket && this.isConnected;
  }

  // Lấy thông tin socket hiện tại
  getSocketInfo() {
    if (!this.socket) {
      return null;
    }

    return {
      id: this.socket.id,
      connected: this.isConnected,
      currentConversation: this.currentConversationId,
      reconnectAttempts: this.reconnectAttempts
    };
  }

  // Retry kết nối thủ công
  retryConnection() {
    if (this.socket && !this.isConnected) {
      console.log('🔄 Manual retry connection...');
      this.socket.connect();
    }
  }

  // Cleanup khi component unmount
  cleanup() {
    this.disconnect();
    this.eventCallbacks.clear();
    this.authToken = null;
    this.currentConversationId = null;
  }
}

// Tạo singleton instance
const websocketService = new WebSocketService();

export default websocketService;