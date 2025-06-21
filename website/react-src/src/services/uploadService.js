import axios from 'axios';
import { BACKEND_URL } from "../config/config";
const API_BASE_URL = BACKEND_URL || 'http://localhost:3000';

export const uploadService = {
  // Upload file to conversation
  async uploadFile(conversationId, file) {
    try {
      console.log('📤 Uploading file:', file.name, 'to conversation:', conversationId);

      const formData = new FormData();
      formData.append('file', file);

      const token = localStorage.getItem('authToken');
      const response = await axios.post(
        `${API_BASE_URL}/chat/conversations/${conversationId}/upload`,
        formData,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'multipart/form-data',
          }
        }
      );

      console.log('✅ File uploaded successfully:', response.data);
      return response.data;
    } catch (error) {
      console.error('❌ Upload error:', error.response?.data || error.message);
      throw new Error(error.response?.data?.message || 'Upload failed');
    }
  },

  // Get uploaded files for a conversation
  async getUploadedFiles(conversationId) {
    try {
      console.log('📁 Loading uploaded files for conversation:', conversationId);

      const token = localStorage.getItem('authToken');
      const response = await axios.get(
        `${API_BASE_URL}/chat/conversations/${conversationId}/files`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          }
        }
      );

      console.log('📁 Files loaded:', response.data.files?.length || 0, 'files');
      return response.data.files || [];
    } catch (error) {
      console.error('❌ Error loading files:', error.response?.data || error.message);
      throw new Error(error.response?.data?.message || 'Failed to load files');
    }
  },

  // Delete uploaded file
  async deleteFile(conversationId, fileId) {
    try {
      console.log('🗑️ Deleting file:', fileId, 'from conversation:', conversationId);

      const token = localStorage.getItem('authToken');
      await axios.delete(
        `${API_BASE_URL}/chat/conversations/${conversationId}/files/${fileId}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          }
        }
      );

      console.log('✅ File deleted successfully');
      return true;
    } catch (error) {
      console.error('❌ Error deleting file:', error.response?.data || error.message);
      throw new Error(error.response?.data?.message || 'Failed to delete file');
    }
  },

  // Get file download URL
  getFileUrl(fileName) {
    return `${API_BASE_URL}/chat/files/${fileName}`;
  }
};
