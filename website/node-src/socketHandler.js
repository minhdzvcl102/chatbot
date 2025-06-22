// websocket/socketHandler.js
import { Server } from 'socket.io';
import jwt from 'jsonwebtoken';
import net from 'net';
import { getDb } from './utilities/database.js';
import { logMessage } from './utilities/logger.js';

class WebSocketHandler {
  constructor(server) {
    this.io = new Server(server, {
      cors: {
        origin: process.env.FRONTEND_URL || "http://localhost:3000",
        methods: ["GET", "POST"],
        credentials: true
      }
    });
    
    this.connectedUsers = new Map(); // userId -> socket info
    this.roomUsers = new Map(); // conversationId -> Set of userIds
    this.userRooms = new Map(); // userId -> Set of conversationIds
    
    // Python AI service connection settings
    this.pythonAI = {
      host: process.env.PYTHON_AI_HOST || 'localhost',
      port: process.env.PYTHON_AI_PORT || 8888,
      timeout: process.env.PYTHON_AI_TIMEOUT || 30000
    };
    
    this.setupMiddleware();
    this.setupEventHandlers();
    
    logMessage("INF", "🔌 WebSocket server initialized");
  }

  // JWT Authentication middleware
  setupMiddleware() {
    this.io.use(async (socket, next) => {
      try {
        const token = socket.handshake.auth.token;
        
        if (!token) {
          logMessage("WRN", `❌ No token provided for socket ${socket.id}`);
          return next(new Error('Authentication error: No token provided'));
        }

        // Verify JWT token
        const decoded = jwt.verify(token, process.env.JWT_SECRET || 'your-secret-key');
        
        // Get user info from database
        const db = await getDb();
        const user = await db.get('SELECT id, username, email FROM users WHERE id = ?', [decoded.userId]);
        
        if (!user) {
          logMessage("WRN", `❌ User not found for token: ${decoded.userId}`);
          return next(new Error('Authentication error: User not found'));
        }

        // Attach user info to socket
        socket.userId = user.id;
        socket.username = user.username;
        socket.email = user.email;
        
        logMessage("INF", `✅ Socket ${socket.id} authenticated for user ${user.username} (ID: ${user.id})`);
        next();
        
      } catch (error) {
        logMessage("ERR", `❌ Socket authentication error: ${error.message}`);
        next(new Error('Authentication error: Invalid token'));
      }
    });
  }

  // Setup event handlers
  setupEventHandlers() {
    this.io.on('connection', (socket) => {
      this.handleConnection(socket);
    });
  }

  // Handle new socket connection
  handleConnection(socket) {
    const userId = socket.userId;
    const username = socket.username;
    
    logMessage("INF", `🔗 User ${username} (${userId}) connected with socket ${socket.id}`);
    
    // Store user connection
    this.connectedUsers.set(userId, {
      socketId: socket.id,
      username: username,
      email: socket.email,
      connectedAt: new Date(),
      socket: socket
    });

    // Send connection confirmation
    socket.emit('connected', {
      message: 'Connected successfully',
      userId: userId,
      username: username,
      socketId: socket.id
    });

    // Setup event handlers for this socket
    this.setupSocketEvents(socket);
    
    // Handle disconnection
    socket.on('disconnect', (reason) => {
      this.handleDisconnection(socket, reason);
    });
  }

  // Setup events for individual socket
  setupSocketEvents(socket) {
    const userId = socket.userId;
    
    // Join conversation room
    socket.on('join_conversation', async (data) => {
      await this.handleJoinConversation(socket, data);
    });

    // Leave conversation room
    socket.on('leave_conversation', async (data) => {
      await this.handleLeaveConversation(socket, data);
    });

    // Send message
    socket.on('send_message', async (data) => {
      await this.handleSendMessage(socket, data);
    });

    // Typing indicator
    socket.on('typing', (data) => {
      this.handleTyping(socket, data);
    });

    // File upload notification
    socket.on('file_uploaded', (data) => {
      this.handleFileUploaded(socket, data);
    });

    // Get online users in conversation
    socket.on('get_online_users', (data) => {
      this.handleGetOnlineUsers(socket, data);
    });
  }

  // Handle join conversation
  async handleJoinConversation(socket, data) {
    try {
      const { conversationId } = data;
      const userId = socket.userId;
      
      if (!conversationId) {
        socket.emit('error', { message: 'Conversation ID is required' });
        return;
      }

      // Verify user has access to this conversation
      const db = await getDb();
      const conversation = await db.get(
        'SELECT * FROM conversations WHERE id = ? AND userId = ?',
        [conversationId, userId]
      );

      if (!conversation) {
        logMessage("WRN", `❌ User ${userId} tried to join unauthorized conversation ${conversationId}`);
        socket.emit('error', { message: 'Unauthorized access to conversation' });
        return;
      }

      // Join the socket to the room
      const roomName = `conversation_${conversationId}`;
      socket.join(roomName);
      
      // Track room membership
      if (!this.roomUsers.has(conversationId)) {
        this.roomUsers.set(conversationId, new Set());
      }
      if (!this.userRooms.has(userId)) {
        this.userRooms.set(userId, new Set());
      }
      
      this.roomUsers.get(conversationId).add(userId);
      this.userRooms.get(userId).add(conversationId);

      logMessage("INF", `👥 User ${socket.username} joined conversation ${conversationId}`);
      
      // Notify user they joined successfully
      socket.emit('joined_conversation', {
        conversationId: conversationId,
        message: 'Successfully joined conversation'
      });

      // Notify other users in the room
      socket.to(roomName).emit('user_joined', {
        userId: userId,
        username: socket.username,
        conversationId: conversationId
      });

      // Send online users list
      this.sendOnlineUsers(conversationId);
      
    } catch (error) {
      logMessage("ERR", `Error joining conversation: ${error.message}`, error.stack);
      socket.emit('error', { message: 'Failed to join conversation' });
    }
  }

  // Handle leave conversation
  async handleLeaveConversation(socket, data) {
    try {
      const { conversationId } = data;
      const userId = socket.userId;
      
      if (!conversationId) {
        socket.emit('error', { message: 'Conversation ID is required' });
        return;
      }

      const roomName = `conversation_${conversationId}`;
      socket.leave(roomName);
      
      // Update room tracking
      if (this.roomUsers.has(conversationId)) {
        this.roomUsers.get(conversationId).delete(userId);
        if (this.roomUsers.get(conversationId).size === 0) {
          this.roomUsers.delete(conversationId);
        }
      }
      
      if (this.userRooms.has(userId)) {
        this.userRooms.get(userId).delete(conversationId);
        if (this.userRooms.get(userId).size === 0) {
          this.userRooms.delete(userId);
        }
      }

      logMessage("INF", `👋 User ${socket.username} left conversation ${conversationId}`);
      
      // Notify user they left successfully
      socket.emit('left_conversation', {
        conversationId: conversationId,
        message: 'Successfully left conversation'
      });

      // Notify other users in the room
      socket.to(roomName).emit('user_left', {
        userId: userId,
        username: socket.username,
        conversationId: conversationId
      });

      // Update online users list
      this.sendOnlineUsers(conversationId);
      
    } catch (error) {
      logMessage("ERR", `Error leaving conversation: ${error.message}`, error.stack);
      socket.emit('error', { message: 'Failed to leave conversation' });
    }
  }

  // Handle send message
  async handleSendMessage(socket, data) {
    try {
      const { conversationId, content, role = 'user' } = data;
      const userId = socket.userId;
      
      if (!conversationId || !content || content.trim() === '') {
        socket.emit('error', { message: 'Conversation ID and content are required' });
        return;
      }

      // Verify user has access to this conversation
      const db = await getDb();
      const conversation = await db.get(
        'SELECT * FROM conversations WHERE id = ? AND userId = ?',
        [conversationId, userId]
      );

      if (!conversation) {
        logMessage("WRN", `❌ User ${userId} tried to send message to unauthorized conversation ${conversationId}`);
        socket.emit('error', { message: 'Unauthorized access to conversation' });
        return;
      }

      // Save message to database
      const messageResult = await db.run(
        'INSERT INTO messages (conversationId, role, content, createdAt) VALUES (?, ?, ?, ?)',
        [conversationId, role, content.trim(), new Date().toISOString()]
      );

      if (!messageResult.lastID) {
        throw new Error('Failed to save message to database');
      }

      // Update conversation timestamp
      await db.run(
        'UPDATE conversations SET updatedAt = ? WHERE id = ?',
        [new Date().toISOString(), conversationId]
      );

      // Get the saved message
      const savedMessage = await db.get('SELECT * FROM messages WHERE id = ?', [messageResult.lastID]);

      const messageData = {
        id: savedMessage.id,
        conversationId: conversationId,
        role: role,
        content: content.trim(),
        createdAt: savedMessage.createdAt,
        userId: userId,
        username: socket.username
      };

      logMessage("INF", `📤 Message sent by ${socket.username} to conversation ${conversationId}`);

      // Broadcast message to all users in the conversation room
      const roomName = `conversation_${conversationId}`;
      this.io.to(roomName).emit('new_message', messageData);

      // If this is a user message, get AI response from Python service
      if (role === 'user') {
        // Show typing indicator for AI
        this.io.to(roomName).emit('typing', {
          userId: null,
          username: 'AI Assistant',
          conversationId: conversationId,
          isTyping: true
        });

        // Get AI response from Python service
        this.getAIResponse(conversationId, content, socket.username);
      }

      // Update conversation info for all users
      this.io.to(roomName).emit('conversation_updated', {
        conversationId: conversationId,
        updatedAt: new Date().toISOString(),
        lastMessage: messageData
      });
      
    } catch (error) {
      logMessage("ERR", `Error sending message: ${error.message}`, error.stack);
      socket.emit('error', { message: 'Failed to send message' });
    }
  }

  // Handle typing indicator
  handleTyping(socket, data) {
    try {
      const { conversationId, isTyping } = data;
      const userId = socket.userId;
      
      if (!conversationId) {
        socket.emit('error', { message: 'Conversation ID is required' });
        return;
      }

      const roomName = `conversation_${conversationId}`;
      
      // Broadcast typing status to other users in the room
      socket.to(roomName).emit('typing', {
        userId: userId,
        username: socket.username,
        conversationId: conversationId,
        isTyping: isTyping
      });

      logMessage("INF", `⌨️ User ${socket.username} ${isTyping ? 'started' : 'stopped'} typing in conversation ${conversationId}`);
      
    } catch (error) {
      logMessage("ERR", `Error handling typing: ${error.message}`, error.stack);
    }
  }

  // Handle file upload notification
  handleFileUploaded(socket, data) {
    try {
      const { conversationId, file } = data;
      const userId = socket.userId;
      
      if (!conversationId || !file) {
        socket.emit('error', { message: 'Conversation ID and file info are required' });
        return;
      }

      const roomName = `conversation_${conversationId}`;
      
      // Broadcast file upload to all users in the room
      this.io.to(roomName).emit('file_uploaded', {
        conversationId: conversationId,
        file: file,
        uploadedBy: {
          userId: userId,
          username: socket.username
        },
        uploadedAt: new Date().toISOString()
      });

      logMessage("INF", `📁 File uploaded by ${socket.username} to conversation ${conversationId}: ${file.originalName}`);
      
    } catch (error) {
      logMessage("ERR", `Error handling file upload: ${error.message}`, error.stack);
    }
  }

  // Handle get online users
  handleGetOnlineUsers(socket, data) {
    try {
      const { conversationId } = data;
      
      if (!conversationId) {
        socket.emit('error', { message: 'Conversation ID is required' });
        return;
      }

      this.sendOnlineUsers(conversationId, socket);
      
    } catch (error) {
      logMessage("ERR", `Error getting online users: ${error.message}`, error.stack);
    }
  }

  // Send online users list
  sendOnlineUsers(conversationId, targetSocket = null) {
    try {
      const onlineUsers = [];
      
      if (this.roomUsers.has(conversationId)) {
        const userIds = this.roomUsers.get(conversationId);
        
        for (const userId of userIds) {
          const userInfo = this.connectedUsers.get(userId);
          if (userInfo) {
            onlineUsers.push({
              userId: userId,
              username: userInfo.username,
              email: userInfo.email,
              connectedAt: userInfo.connectedAt
            });
          }
        }
      }

      const roomName = `conversation_${conversationId}`;
      const eventData = {
        conversationId: conversationId,
        onlineUsers: onlineUsers,
        count: onlineUsers.length
      };

      if (targetSocket) {
        targetSocket.emit('online_users', eventData);
      } else {
        this.io.to(roomName).emit('online_users', eventData);
      }

      logMessage("INF", `👥 Sent online users list for conversation ${conversationId}: ${onlineUsers.length} users`);
      
    } catch (error) {
      logMessage("ERR", `Error sending online users: ${error.message}`, error.stack);
    }
  }

  // Get AI response from Python service via socket
  async getAIResponse(conversationId, userMessage, username) {
    return new Promise((resolve) => {
      const client = new net.Socket();
      let responseBuffer = '';
      
      // Set timeout
      const timeout = setTimeout(() => {
        client.destroy();
        logMessage("ERR", `⏰ Python AI service timeout for conversation ${conversationId}`);
        this.handleAIError(conversationId, 'AI service timeout');
        resolve(null);
      }, this.pythonAI.timeout);

      // Connect to Python AI service
      client.connect(this.pythonAI.port, this.pythonAI.host, () => {
        logMessage("INF", `🔗 Connected to Python AI service for conversation ${conversationId}`);
        
        // Prepare request data
        const requestData = {
          type: 'chat',
          conversationId: conversationId,
          message: userMessage,
          username: username,
          timestamp: new Date().toISOString()
        };

        // Send request to Python service
        client.write(JSON.stringify(requestData) + '\n');
      });

      // Handle data received from Python service
      client.on('data', (data) => {
        responseBuffer += data.toString();
        
        // Check if we have a complete response (assuming newline-delimited JSON)
        const lines = responseBuffer.split('\n');
        
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].trim();
          if (line) {
            try {
              const response = JSON.parse(line);
              this.handleAIResponse(conversationId, response);
            } catch (parseError) {
              logMessage("ERR", `Error parsing AI response: ${parseError.message}`);
            }
          }
        }
        
        // Keep the last incomplete line
        responseBuffer = lines[lines.length - 1];
      });

      // Handle connection errors
      client.on('error', (error) => {
        clearTimeout(timeout);
        logMessage("ERR", `Python AI service connection error: ${error.message}`);
        this.handleAIError(conversationId, 'AI service connection error');
        resolve(null);
      });

      // Handle connection close
      client.on('close', () => {
        clearTimeout(timeout);
        logMessage("INF", `🔌 Python AI service connection closed for conversation ${conversationId}`);
        resolve(true);
      });
    });
  }

  // Handle AI response from Python service
  async handleAIResponse(conversationId, response) {
    try {
      const { content, status, error } = response;
      
      if (status === 'error' || error) {
        logMessage("ERR", `AI service error: ${error || 'Unknown error'}`);
        this.handleAIError(conversationId, error || 'AI processing error');
        return;
      }

      if (!content || content.trim() === '') {
        logMessage("WRN", `Empty AI response for conversation ${conversationId}`);
        this.handleAIError(conversationId, 'Empty AI response');
        return;
      }

      // Save AI response to database
      const db = await getDb();
      const messageResult = await db.run(
        'INSERT INTO messages (conversationId, role, content, createdAt) VALUES (?, ?, ?, ?)',
        [conversationId, 'assistant', content.trim(), new Date().toISOString()]
      );

      if (messageResult.lastID) {
        // Update conversation timestamp
        await db.run(
          'UPDATE conversations SET updatedAt = ? WHERE id = ?',
          [new Date().toISOString(), conversationId]
        );

        // Get the saved message
        const savedMessage = await db.get('SELECT * FROM messages WHERE id = ?', [messageResult.lastID]);

        const aiMessageData = {
          id: savedMessage.id,
          conversationId: conversationId,
          role: 'assistant',
          content: content.trim(),
          createdAt: savedMessage.createdAt,
          userId: null,
          username: 'AI Assistant'
        };

        const roomName = `conversation_${conversationId}`;
        
        // Stop typing indicator
        this.io.to(roomName).emit('typing', {
          userId: null,
          username: 'AI Assistant',
          conversationId: conversationId,
          isTyping: false
        });

        // Broadcast AI response to all users in the conversation room
        this.io.to(roomName).emit('new_message', aiMessageData);

        // Update conversation info
        this.io.to(roomName).emit('conversation_updated', {
          conversationId: conversationId,
          updatedAt: new Date().toISOString(),
          lastMessage: aiMessageData
        });

        logMessage("INF", `🤖 AI response sent to conversation ${conversationId}`);
      }
      
    } catch (error) {
      logMessage("ERR", `Error handling AI response: ${error.message}`, error.stack);
      this.handleAIError(conversationId, 'Failed to process AI response');
    }
  }

  // Handle AI service errors
  handleAIError(conversationId, errorMessage) {
    const roomName = `conversation_${conversationId}`;
    
    // Stop typing indicator
    this.io.to(roomName).emit('typing', {
      userId: null,
      username: 'AI Assistant',
      conversationId: conversationId,
      isTyping: false
    });

    // Send error message to users
    this.io.to(roomName).emit('ai_error', {
      conversationId: conversationId,
      error: errorMessage || 'AI service is temporarily unavailable',
      timestamp: new Date().toISOString()
    });

    logMessage("ERR", `AI service error for conversation ${conversationId}: ${errorMessage}`);
  }

  // Handle disconnection
  handleDisconnection(socket, reason) {
    const userId = socket.userId;
    const username = socket.username;
    
    logMessage("INF", `🔌 User ${username} (${userId}) disconnected: ${reason}`);
    
    // Clean up user rooms
    if (this.userRooms.has(userId)) {
      const userConversations = this.userRooms.get(userId);
      
      for (const conversationId of userConversations) {
        const roomName = `conversation_${conversationId}`;
        
        // Notify other users in each room
        socket.to(roomName).emit('user_left', {
          userId: userId,
          username: username,
          conversationId: conversationId
        });
        
        // Update room users
        if (this.roomUsers.has(conversationId)) {
          this.roomUsers.get(conversationId).delete(userId);
          if (this.roomUsers.get(conversationId).size === 0) {
            this.roomUsers.delete(conversationId);
          } else {
            // Update online users list for remaining users
            this.sendOnlineUsers(conversationId);
          }
        }
      }
      
      this.userRooms.delete(userId);
    }
    
    // Remove user from connected users
    this.connectedUsers.delete(userId);
  }

  // Get server statistics
  getStats() {
    return {
      connectedUsers: this.connectedUsers.size,
      activeRooms: this.roomUsers.size,
      totalConnections: this.io.engine.clientsCount,
      pythonAIConfig: {
        host: this.pythonAI.host,
        port: this.pythonAI.port,
        timeout: this.pythonAI.timeout
      }
    };
  }

  // Broadcast system message to all users
  broadcastSystemMessage(message) {
    this.io.emit('system_message', {
      message: message,
      timestamp: new Date().toISOString()
    });
    
    logMessage("INF", `📢 System message broadcasted: ${message}`);
  }

  // Broadcast message to specific conversation
  broadcastToConversation(conversationId, event, data) {
    const roomName = `conversation_${conversationId}`;
    this.io.to(roomName).emit(event, data);
    
    logMessage("INF", `📡 Broadcasted ${event} to conversation ${conversationId}`);
  }

  // Test Python AI service connection
  async testPythonAIConnection() {
    return new Promise((resolve) => {
      const client = new net.Socket();
      const timeout = setTimeout(() => {
        client.destroy();
        resolve(false);
      }, 5000);

      client.connect(this.pythonAI.port, this.pythonAI.host, () => {
        clearTimeout(timeout);
        client.destroy();
        resolve(true);
      });

      client.on('error', () => {
        clearTimeout(timeout);
        resolve(false);
      });
    });
  }
}

export default WebSocketHandler;