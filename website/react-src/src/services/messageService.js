import axios from 'axios';

const API_BASE_URL = 'http://localhost:3000';

// Get auth token from localStorage
const getAuthHeaders = () => {
  const token = localStorage.getItem('authToken');
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json'
  };
};

// Message API calls
export const messageService = {
  // Get messages for a conversation
  async getMessages(conversationId) {
    try {
      console.log("📡 Loading messages for conversation:", conversationId);
      const response = await axios.get(`${API_BASE_URL}/chat/conversations/${conversationId}/messages`, {
        headers: getAuthHeaders()
      });
      
      console.log("📋 Loaded messages:", response.data.messages);
      return response.data.messages;
    } catch (error) {
      console.error("❌ Error loading messages:", error);
      if (error.response?.status === 404) {
        throw new Error('Conversation not found or unauthorized');
      }
      throw error;
    }
  },

  // Send a new message
  async sendMessage(conversationId, content) {
    try {
      console.log("📤 Sending message to conversation:", conversationId);
      console.log("📝 Message content:", content);
      
      const messageData = {
        content: content,
        role: 'user'
      };

      const response = await axios.post(`${API_BASE_URL}/chat/conversations/${conversationId}/messages`, 
        messageData, 
        {
          headers: getAuthHeaders()
        }
      );
      
      console.log("✅ Message sent successfully:", response.data);
      
      // Return the saved message
      return {
        savedMessage: response.data.savedMessage,
        success: true
      };
    } catch (error) {
      console.error("❌ Error sending message:", error);
      if (error.response?.status === 404) {
        throw new Error('Conversation not found or unauthorized');
      }
      if (error.response?.status === 400) {
        throw new Error('Message content is required');
      }
      throw error;
    }
  },

  // Send assistant message (for cases where you want to send AI messages manually)
  async sendAssistantMessage(conversationId, content) {
    try {
      console.log("🤖 Sending assistant message to conversation:", conversationId);
      
      const messageData = {
        content: content,
        role: 'assistant'
      };

      const response = await axios.post(`${API_BASE_URL}/chat/conversations/${conversationId}/messages`, 
        messageData, 
        {
          headers: getAuthHeaders()
        }
      );
      
      console.log("✅ Assistant message sent successfully:", response.data);
      return response.data.userMessage; // This will be the assistant message
    } catch (error) {
      console.error("❌ Error sending assistant message:", error);
      throw error;
    }
  },

  // Format message for display in UI
  formatMessageForDisplay(message) {
    return {
      id: message.id,
      content: message.content,
      role: message.role,
      timestamp: new Date(message.createdAt).toLocaleString(),
      createdAt: message.createdAt,
      isUser: message.role === 'user',
      isAssistant: message.role === 'assistant'
    };
  },

  // Format multiple messages for display
  formatMessagesForDisplay(messages) {
    return messages.map(message => this.formatMessageForDisplay(message));
  },

  // Get conversation summary (last few messages)
  async getConversationSummary(conversationId, limit = 5) {
    try {
      const messages = await this.getMessages(conversationId);
      const recentMessages = messages.slice(-limit);
      return this.formatMessagesForDisplay(recentMessages);
    } catch (error) {
      console.error("❌ Error getting conversation summary:", error);
      throw error;
    }
  }
};