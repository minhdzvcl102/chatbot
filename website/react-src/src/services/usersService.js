import axios from 'axios';
import { BACKEND_URL } from "../config/config";
const API_BASE_URL = BACKEND_URL || 'http://localhost:3000';

export const userServices = {
  // Create new user
  async createUser(email, username, password, role, token) {
    try {
      console.log('👤 Creating user:', username, 'with role:', role);

      const response = await axios.post(
        `${API_BASE_URL}/account/createUser`,
        {
          email,
          username,
          password,
          role
        },
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        }
      );

      console.log('✅ User created successfully:', response.data);
      return response.data;
    } catch (error) {
      console.error('❌ Create user error:', error.response?.data || error.message);
      throw new Error(error.response?.data?.message || 'Failed to create user');
    }
  },

  // Get all users
  async getAllUsers(token,id) {
    try {
      console.log('Loading all users');

      const response = await axios.get(
        `${API_BASE_URL}/account/getAllUsers/${id}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
    
      console.log(' Users loaded:', response.data.users?.length || 0, 'users');
      return response.data;
    } catch (error) {
      console.error('❌ Error loading users:', error.response?.data || error.message);
      throw new Error(error.response?.data?.message || 'Failed to fetch users');
    }
  },

  // Delete user
  async deleteUser(userId, token) {
    try {
      console.log('🗑️ Deleting user:', userId);

      await axios.delete(
        `${API_BASE_URL}/account/deleteUser/${userId}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      console.log('✅ User deleted successfully');
      return true;
    } catch (error) {
      console.error('❌ Error deleting user:', error.response?.data || error.message);
      throw new Error(error.response?.data?.message || 'Failed to delete user');
    }
  },

  // Update user
  async updateUser(userId, userData, token) {
    try {
      console.log('📝 Updating user:', userId, 'with data:', userData);

      const response = await axios.put(
        `${API_BASE_URL}/account/updateUser/${userId}`,
        userData,
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        }
      );

      console.log('✅ User updated successfully:', response.data);
      return response.data;
    } catch (error) {
      console.error('❌ Error updating user:', error.response?.data || error.message);
      throw new Error(error.response?.data?.message || 'Failed to update user');
    }
  }
};