import { Server } from 'socket.io';
import jwt from 'jsonwebtoken';
import { getDb } from '../utilities/database.js';
import { logMessage } from '../utilities/logger.js';
import RoomManager from './roomManager.js';
import AIHandler from './socket.js';

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
    this.roomManager = new RoomManager(this.io);
    this.aiHandler = new AIHandler(this.io, this.roomManager);
    
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

        const decoded = jwt.verify(token, process.env.JWT_SECRET || 'your-secret-key');
        
        const db = await getDb();
        const user = await db.get('SELECT id, username, email FROM users WHERE id = ?', [decoded.userId]);
        
        if (!user) {
          logMessage("WRN", `❌ User not found for token: ${decoded.userId}`);
          return next(new Error('Authentication error: User not found'));
        }

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
    
    this.connectedUsers.set(userId, {
      socketId: socket.id,
      username: username,
      email: socket.email,
      connectedAt: new Date(),
      socket: socket
    });

    socket.emit('connected', {
      message: 'Connected successfully',
      userId: userId,
      username: username,
      socketId: socket.id
    });

    this.setupSocketEvents(socket);
    
    socket.on('disconnect', (reason) => {
      this.handleDisconnection(socket, reason);
    });
  }

  // Setup events for individual socket
  setupSocketEvents(socket) {
    socket.on('join_conversation', async (data) => {
      await this.roomManager.handleJoinConversation(socket, data);
    });

    socket.on('leave_conversation', async (data) => {
      await this.roomManager.handleLeaveConversation(socket, data);
    });

    socket.on('send_message', async (data) => {
      await this.handleSendMessage(socket, data);
    });

    socket.on('typing', (data) => {
      this.handleTyping(socket, data);
    });

    socket.on('file_uploaded', (data) => {
      this.handleFileUploaded(socket, data);
    });

    socket.on('get_online_users', (data) => {
      this.roomManager.handleGetOnlineUsers(socket, data);
    });
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

      const messageResult = await db.run(
        'INSERT INTO messages (conversationId, role, content, createdAt) VALUES (?, ?, ?, ?)',
        [conversationId, role, content.trim(), new Date().toISOString()]
      );

      if (!messageResult.lastID) {
        throw new Error('Failed to save message to database');
      }

      await db.run(
        'UPDATE conversations SET updatedAt = ? WHERE id = ?',
        [new Date().toISOString(), conversationId]
      );

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

      const roomName = `conversation_${conversationId}`;
      this.io.to(roomName).emit('new_message', messageData);

      if (role === 'user') {
        this.io.to(roomName).emit('typing', {
          userId: null,
          username: 'AI Assistant',
          conversationId: conversationId,
          isTyping: true
        });

        this.aiHandler.getAIResponse(conversationId, content, socket.username);
      }

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

  // Handle disconnection
  handleDisconnection(socket, reason) {
    const userId = socket.userId;
    const username = socket.username;
    
    logMessage("INF", `🔌 User ${username} (${userId}) disconnected: ${reason}`);
    
    this.roomManager.handleDisconnection(socket, userId, username);
    this.connectedUsers.delete(userId);
  }

  // Get server statistics
  getStats() {
    return {
      connectedUsers: this.connectedUsers.size,
      activeRooms: this.roomManager.getRoomCount(),
      totalConnections: this.io.engine.clientsCount,
      pythonAIConfig: this.aiHandler.getAIConfig()
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

  // Test Python AI service connection
  async testPythonAIConnection() {
    return await this.aiHandler.testPythonAIConnection();
  }
}

export default WebSocketHandler;