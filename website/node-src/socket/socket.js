// socket.js
import net from 'net';
import { getDb } from '../utilities/database.js';
import { logMessage } from '../utilities/logger.js';

class AIHandler {
  constructor(io, roomManager) {
    this.io = io;
    this.roomManager = roomManager;
    this.pythonAI = {
      host: process.env.PYTHON_AI_HOST || 'localhost',
      port: process.env.PYTHON_AI_PORT || 8888,
      timeout: process.env.PYTHON_AI_TIMEOUT || 90000
    };
  }

  // Get AI response from Python service
  async getAIResponse(conversationId, userMessage, username) {
    return new Promise((resolve) => {
      const client = new net.Socket();
      let responseBuffer = '';

      const timeout = setTimeout(() => {
        client.destroy();
        logMessage("ERR", `Python AI service timeout for conversation ${conversationId}`);
        this.handleAIError(conversationId, 'AI service timeout');
        resolve(null);
      }, this.pythonAI.timeout);

      client.connect(this.pythonAI.port, this.pythonAI.host, () => {
        logMessage("INF", `Connected to Python AI service for conversation ${conversationId}`);

        const requestData = {
          type: 'chat',
          conversationId: conversationId,
          message: userMessage,
          username: username,
          timestamp: new Date().toISOString()
        };

        client.write(JSON.stringify(requestData) + '\n');
      });

      client.on('data', (data) => {
        responseBuffer += data.toString();

        const lines = responseBuffer.split('\n');

        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].trim();
          if (line) {
            try {
              const response = JSON.parse(line);
              // Xử lý response từ Python AI
              this.handleAIResponse(conversationId, response);
            } catch (parseError) {
              logMessage("ERR", `Error parsing AI response: ${parseError.message}`);
            }
          }
        }

        responseBuffer = lines[lines.length - 1];
      });

      client.on('error', (error) => {
        clearTimeout(timeout);
        logMessage("ERR", `Python AI service connection error: ${error.message}`);
        this.handleAIError(conversationId, 'AI service connection error');
        resolve(null);
      });

      client.on('close', () => {
        clearTimeout(timeout);
        logMessage("INF", `Python AI service connection closed for conversation ${conversationId}`);
        resolve(true);
      });
    });
  }

  // Handle AI response from Python service
  async handleAIResponse(conversationId, response) {
    try {
      // Extract response data
      const { content, status, error, chart_image_base64 } = response;

      if (status === 'error' || error) {
        logMessage("ERR", `AI service error: ${error || 'Unknown error'}`);
        this.handleAIError(conversationId, error || 'AI processing error');
        return;
      }

      // Check if we have content or chart data
      if (!content && !chart_image_base64) {
        logMessage("WRN", `Empty AI response (no content and no chart) for conversation ${conversationId}`);
        this.handleAIError(conversationId, 'Empty AI response');
        return;
      }

      const db = await getDb();
      const roomName = `conversation_${conversationId}`;

      // Tạo message object trước khi lưu database
      const messageData = {
        conversationId: conversationId,
        role: 'assistant',
        content: content || null,
        url_chart: chart_image_base64 || null,
        createdAt: new Date().toISOString(),
        userId: null,
        username: 'AI Assistant'
      };

      // Log để debug
      logMessage("INF", `Processing AI response for conversation ${conversationId}`);
      logMessage("INF", `Content length: ${content ? content.length : 0}`);
      logMessage("INF", `Chart data: ${chart_image_base64 ? 'Present' : 'None'}`);

      // Lưu vào database
      const messageResult = await db.run(
        'INSERT INTO messages (conversationId, role, content, url_chart, createdAt) VALUES (?, ?, ?, ?, ?)',
        [conversationId, 'assistant', content, chart_image_base64, messageData.createdAt]
      );

      if (messageResult.lastID) {
        // Cập nhật conversation timestamp
        await db.run(
          'UPDATE conversations SET updatedAt = ? WHERE id = ?',
          [messageData.createdAt, conversationId]
        );

        // Thêm ID từ database vào message data
        messageData.id = messageResult.lastID;

        // Dừng typing indicator
        this.io.to(roomName).emit('typing', {
          userId: null,
          username: 'AI Assistant',
          conversationId: conversationId,
          isTyping: false
        });

        // Gửi message qua WebSocket với đầy đủ dữ liệu
        this.io.to(roomName).emit('new_message', messageData);

        // Gửi conversation update
        this.io.to(roomName).emit('conversation_updated', {
          conversationId: conversationId,
          updatedAt: messageData.createdAt,
          lastMessage: messageData
        });

        // Log thành công
        const chartStatus = chart_image_base64 ? 'with chart' : 'text only';
        logMessage("INF", `AI response ${chartStatus} sent to conversation ${conversationId}`);
        logMessage("INF", `Message ID: ${messageResult.lastID}`);

      } else {
        logMessage("ERR", `Failed to save message to database for conversation ${conversationId}`);
        this.handleAIError(conversationId, 'Failed to save message');
      }

    } catch (error) {
      logMessage("ERR", `Error handling AI response: ${error.message}`, error.stack);
      this.handleAIError(conversationId, 'Failed to process AI response');
    }
  }

  // Handle AI service errors
  handleAIError(conversationId, errorMessage) {
    const roomName = `conversation_${conversationId}`;

    this.io.to(roomName).emit('typing', {
      userId: null,
      username: 'AI Assistant',
      conversationId: conversationId,
      isTyping: false
    });

    this.io.to(roomName).emit('ai_error', {
      conversationId: conversationId,
      error: errorMessage || 'AI service is temporarily unavailable',
      timestamp: new Date().toISOString()
    });

    logMessage("ERR", `AI service error for conversation ${conversationId}: ${errorMessage}`);
  }

  // Get AI config
  getAIConfig() {
    return {
      host: this.pythonAI.host,
      port: this.pythonAI.port,
      timeout: this.pythonAI.timeout
    };
  }

  // Test Python AI service connection
  async testPythonAIConnection() {
    return new Promise((resolve) => {
      const client = new net.Socket();
      const timeout = setTimeout(() => {
        client.destroy();
        resolve(false);
      }, 8888);

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

export default AIHandler;