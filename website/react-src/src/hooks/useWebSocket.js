
import { useEffect, useRef, useState, useCallback } from 'react';
import websocketService from '../services/websocketService';

export const useWebSocket = (authToken, serverUrl) => {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [typingUsers, setTypingUsers] = useState(new Set());

  const unsubscribeRefs = useRef([]);

  // Kết nối WebSocket
  useEffect(() => {
    if (!authToken) return;

    // Set token và kết nối
    websocketService.setAuthToken(authToken);
    websocketService.connect(serverUrl);

    // Setup event listeners
    const unsubscribes = [
      websocketService.on('connected', () => {
        setIsConnected(true);
        setConnectionError(null);
      }),

      websocketService.on('disconnected', () => {
        setIsConnected(false);
      }),

      websocketService.on('connection_error', (data) => {
        setConnectionError(data.error);
        setIsConnected(false);
      }),

      websocketService.on('authenticated', (data) => {
        console.log('✅ WebSocket authenticated:', data);
      }),

      websocketService.on('joined_conversation', (data) => {
        setCurrentConversation(data.conversationId);
      }),

      websocketService.on('left_conversation', (data) => {
        if (currentConversation === data.conversationId) {
          setCurrentConversation(null);
          setOnlineUsers([]);
          setTypingUsers(new Set());
        }
      }),

    websocketService.on('new_message', (data) => {
      console.log('New message received:', data);
      setMessages((prev) => {
        console.log('Current messages:', prev);
        if (prev.some((msg) => msg.id === data.id)) {
          console.warn('Duplicate message detected:', data);
          return prev;
        }
        return [...prev, data];
      });
    }),

    websocketService.on('ai_response', (data) => {
      setMessages(prev => [...prev, data]);
    }),

      websocketService.on('online_users', (data) => {
        setOnlineUsers(data.onlineUsers || []);
      }),

      websocketService.on('typing', (data) => {
        setTypingUsers(prev => {
          const newSet = new Set(prev);
          if (data.isTyping) {
            newSet.add(data.userId);
          } else {
            newSet.delete(data.userId);
          }
          return newSet;
        });
      }),

      websocketService.on('user_joined', (data) => {
        console.log('👋 User joined:', data);
      }),

      websocketService.on('user_left', (data) => {
        console.log('🚶 User left:', data);
        setTypingUsers(prev => {
          const newSet = new Set(prev);
          newSet.delete(data.userId);
          return newSet;
        });
      }),

      websocketService.on('error', (data) => {
        console.error('❌ WebSocket error:', data);
        setConnectionError(data.message);
      })
    ];

// Lưu references để cleanup
unsubscribeRefs.current = unsubscribes;

return () => {
  // Cleanup
  unsubscribes.forEach(unsubscribe => unsubscribe());
  websocketService.cleanup();
};
  }, [authToken, serverUrl]);

// Join conversation
const joinConversation = useCallback((conversationId) => {
  if (!conversationId) return false;

  // Clear previous conversation data
  setOnlineUsers([]);
  setTypingUsers(new Set());

  return websocketService.joinConversation(conversationId);
}, []);

// Leave conversation
const leaveConversation = useCallback((conversationId) => {
  const result = websocketService.leaveConversation(conversationId);
  if (result) {
    setCurrentConversation(null);
    setMessages([]);
    setOnlineUsers([]);
    setTypingUsers(new Set());
  }
  return result;
}, []);

// Send message
const sendMessage = useCallback((conversationId, content, role = 'user') => {
  return websocketService.sendMessage(conversationId, content, role);
}, []);

// Send typing indicator
const sendTyping = useCallback((conversationId, isTyping) => {
  return websocketService.sendTyping(conversationId, isTyping);
}, []);

// Notify file uploaded
const notifyFileUploaded = useCallback((conversationId, fileInfo) => {
  return websocketService.notifyFileUploaded(conversationId, fileInfo);
}, []);

// Get online users
const getOnlineUsers = useCallback((conversationId) => {
  return websocketService.getOnlineUsers(conversationId);
}, []);

// Manual retry connection
const retryConnection = useCallback(() => {
  websocketService.retryConnection();
}, []);

// Add message to local state (for optimistic updates)
const addMessage = useCallback((message) => {
  setMessages(prev => [...prev, message]);
}, []);

// Clear messages
const clearMessages = useCallback(() => {
  setMessages([]);
}, []);

 const setMessagesFromAPI = useCallback((msgs) => {
  setMessages(msgs);
}, []);

return {
  // Connection state
  isConnected,
  connectionError,
  currentConversation,

  // Data
  messages,
  onlineUsers,
  typingUsers: Array.from(typingUsers),

  // Actions
  setMessagesFromAPI,
  joinConversation,
  leaveConversation,
  sendMessage,
  sendTyping,
  notifyFileUploaded,
  getOnlineUsers,
  retryConnection,
  addMessage,
  clearMessages,

  // Utils
  socketInfo: websocketService.getSocketInfo(),
  isSocketConnected: websocketService.isSocketConnected()
};
};

// Hook for typing indicator with debounce
export const useTypingIndicator = (conversationId, delay = 1000) => {
  const [isTyping, setIsTyping] = useState(false);
  const timeoutRef = useRef(null);

  const startTyping = useCallback(() => {
    if (!isTyping) {
      setIsTyping(true);
      websocketService.sendTyping(conversationId, true);
    }

    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Set new timeout to stop typing
    timeoutRef.current = setTimeout(() => {
      setIsTyping(false);
      websocketService.sendTyping(conversationId, false);
    }, delay);
  }, [conversationId, isTyping, delay]);

  const stopTyping = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    if (isTyping) {
      setIsTyping(false);
      websocketService.sendTyping(conversationId, false);
    }
  }, [conversationId, isTyping]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return {
    isTyping,
    startTyping,
    stopTyping
  };
};

export default useWebSocket;