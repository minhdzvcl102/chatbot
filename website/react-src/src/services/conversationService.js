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

// Conversation API calls
export const conversationService = {
  // Get all conversations
  async getConversations() {
    try {
      console.log("📡 Loading conversations from API...");
      const response = await axios.get(`${API_BASE_URL}/chat/conversations`, {
        headers: getAuthHeaders()
      });
      
      const formattedConversations = response.data.conversations.map(conv => ({
        id: conv.id,
        user: conv.title,
        type: "AI chat",
        avatar: "https://randomuser.me/api/portraits/men/32.jpg",
        content: conv.content,
        createdAt: conv.createdAt,
        updatedAt: conv.updatedAt
      }));
      
      console.log("📋 Loaded conversations:", formattedConversations);
      return formattedConversations;
    } catch (error) {
      console.error("❌ Error loading conversations:", error);
      throw error;
    }
  },

  // Create new conversation
  async createConversation(title) {
    try {
      console.log("🆕 Creating new conversation with title:", title);
      const response = await axios.post(`${API_BASE_URL}/chat/conversations`, {
        title: title,
        content: "[]" // Fixed: Send non-empty content
      }, {
        headers: getAuthHeaders()
      });
      
      if (response.status === 201) {
        console.log("✅ Conversation created successfully, ID:", response.data.conversationId);
        return response.data.conversationId;
      }
    } catch (error) {
      console.error("❌ Error creating conversation:", error);
      console.error("Response data:", error.response?.data);
      throw error;
    }
  },

  // Update conversation title
  async updateConversation(conversationId, newTitle) {
    try {
      console.log("✏️ Updating conversation title:", { conversationId, newTitle });
      await axios.put(`${API_BASE_URL}/chat/conversations/${conversationId}`, {
        title: newTitle
      }, {
        headers: getAuthHeaders()
      });
      
      console.log("✅ Conversation title updated successfully");
      return true;
    } catch (error) {
      console.error("❌ Error updating conversation:", error);
      throw error;
    }
  },

  // Delete conversation
  async deleteConversation(conversationId) {
    try {
      console.log("🗑️ Deleting conversation ID:", conversationId);
      await axios.delete(`${API_BASE_URL}/chat/conversations/${conversationId}`, {
        headers: getAuthHeaders()
      });
      
      console.log("✅ Conversation deleted successfully");
      return true;
    } catch (error) {
      console.error("❌ Error deleting conversation:", error);
      throw error;
    }
  }
};

// Auth API calls
export const authService = {
  // Logout user
  async logout() {
    try {
      console.log("🚪 Logging out...");
      await axios.post(`${API_BASE_URL}/account/logout`);
      localStorage.removeItem('authToken');
      return true;
    } catch (error) {
      console.error("❌ Logout failed:", error);
      throw error;
    }
  }
};