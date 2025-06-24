import { getDb } from '../utilities/database.js';
import { logMessage } from '../utilities/logger.js';

class RoomManager {
  constructor(io) {
    this.io = io;
    this.roomUsers = new Map(); // conversationId -> Set of userIds
    this.userRooms = new Map(); // userId -> Set of conversationIds
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

      const roomName = `conversation_${conversationId}`;
      socket.join(roomName);
      
      if (!this.roomUsers.has(conversationId)) {
        this.roomUsers.set(conversationId, new Set());
      }
      if (!this.userRooms.has(userId)) {
        this.userRooms.set(userId, new Set());
      }
      
      this.roomUsers.get(conversationId).add(userId);
      this.userRooms.get(userId).add(conversationId);

      logMessage("INF", `👥 User ${socket.username} joined conversation ${conversationId}`);
      
      socket.emit('joined_conversation', {
        conversationId: conversationId,
        message: 'Successfully joined conversation'
      });

      socket.to(roomName).emit('user_joined', {
        userId: userId,
        username: socket.username,
        conversationId: conversationId
      });

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
      
      socket.emit('left_conversation', {
        conversationId: conversationId,
        message: 'Successfully left conversation'
      });

      socket.to(roomName).emit('user_left', {
        userId: userId,
        username: socket.username,
        conversationId: conversationId
      });

      this.sendOnlineUsers(conversationId);
      
    } catch (error) {
      logMessage("ERR", `Error leaving conversation: ${error.message}`, error.stack);
      socket.emit('error', { message: 'Failed to leave conversation' });
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
          const socket = this.io.sockets.sockets.get(
            Array.from(this.io.sockets.sockets.values()).find(s => s.userId === userId)?.id
          );
          if (socket) {
            onlineUsers.push({
              userId: userId,
              username: socket.username,
              email: socket.email,
              connectedAt: socket.connectedAt || new Date()
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

  // Handle disconnection
  handleDisconnection(socket, userId, username) {
    if (this.userRooms.has(userId)) {
      const userConversations = this.userRooms.get(userId);
      
      for (const conversationId of userConversations) {
        const roomName = `conversation_${conversationId}`;
        
        socket.to(roomName).emit('user_left', {
          userId: userId,
          username: username,
          conversationId: conversationId
        });
        
        if (this.roomUsers.has(conversationId)) {
          this.roomUsers.get(conversationId).delete(userId);
          if (this.roomUsers.get(conversationId).size === 0) {
            this.roomUsers.delete(conversationId);
          } else {
            this.sendOnlineUsers(conversationId);
          }
        }
      }
      
      this.userRooms.delete(userId);
    }
  }

  // Get room count
  getRoomCount() {
    return this.roomUsers.size;
  }

  // Broadcast message to specific conversation
  broadcastToConversation(conversationId, event, data) {
    const roomName = `conversation_${conversationId}`;
    this.io.to(roomName).emit(event, data);
    
    logMessage("INF", `📡 Broadcasted ${event} to conversation ${conversationId}`);
  }
}

export default RoomManager;