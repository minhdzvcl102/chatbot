// useWebSocket.js
import { useEffect, useRef, useState, useCallback } from 'react';
import websocketService from '../services/websocketService';

export const useWebSocket = (authToken, serverUrl) => {
    const [isConnected, setIsConnected] = useState(false);
    const [connectionError, setConnectionError] = useState(null);
    const [currentConversation, setCurrentConversation] = useState(null);
    const [onlineUsers, setOnlineUsers] = useState([]);
    const [messages, setMessages] = useState([]);
    const [typingUsers, setTypingUsers] = useState(() => new Set());

    const unsubscribeRefs = useRef([]);

    // Hàm update message để cập nhật tin nhắn hiện có
    const updateMessage = useCallback((messageId, updates) => {
        setMessages(prevMessages =>
            prevMessages.map(msg =>
                msg.id === messageId ? { ...msg, ...updates } : msg
            )
        );
    }, []);

    // Hàm kiểm tra và xử lý message duplicate
    const addMessageSafely = useCallback((newMessage) => {
        setMessages(prevMessages => {
            // Kiểm tra duplicate theo ID
            const isDuplicate = prevMessages.some(msg => msg.id === newMessage.id);
            if (isDuplicate) {
                console.warn('Duplicate message detected, ignoring:', newMessage);
                return prevMessages;
            }

            // Kiểm tra duplicate theo content và timestamp gần nhau (trong vòng 1 giây)
            const similarMessage = prevMessages.find(msg => 
                msg.role === newMessage.role && 
                msg.content === newMessage.content &&
                Math.abs(new Date(msg.createdAt) - new Date(newMessage.createdAt)) < 1000
            );

            if (similarMessage) {
                console.warn('Similar message detected, updating existing:', similarMessage.id);
                // Cập nhật message hiện có với dữ liệu mới (có thể có chart)
                return prevMessages.map(msg =>
                    msg.id === similarMessage.id ? { ...msg, ...newMessage } : msg
                );
            }

            // Thêm message mới
            console.log('Adding new message:', newMessage);
            return [...prevMessages, newMessage];
        });
    }, []);

    // Kết nối WebSocket
    useEffect(() => {
        if (!authToken) return;

        // Set token và kết nối
        websocketService.setAuthToken(authToken);
        websocketService.connect(serverUrl);

        // Setup event listeners
        const unsubscribes = [
            websocketService.on('connected', () => {
                console.log('✅ WebSocket connected');
                setIsConnected(true);
                setConnectionError(null);
            }),

            websocketService.on('disconnected', () => {
                console.log('❌ WebSocket disconnected');
                setIsConnected(false);
            }),

            websocketService.on('connection_error', (data) => {
                console.error('❌ WebSocket connection error:', data);
                setConnectionError(data.error);
                setIsConnected(false);
            }),

            websocketService.on('authenticated', (data) => {
                console.log('✅ WebSocket authenticated:', data);
            }),

            websocketService.on('joined_conversation', (data) => {
                console.log('🏠 Joined conversation:', data.conversationId);
                setCurrentConversation(data.conversationId);
            }),

            websocketService.on('left_conversation', (data) => {
                console.log('🚪 Left conversation:', data.conversationId);
                if (currentConversation === data.conversationId) {
                    setCurrentConversation(null);
                    setOnlineUsers([]);
                    setTypingUsers(new Set());
                }
            }),

            websocketService.on('new_message', (data) => {
                console.log('📨 New message received:', data);
                console.log('📊 Chart data present:', !!data.url_chart);
                
                // Đảm bảo message có đầy đủ thông tin
                const messageWithDefaults = {
                    ...data,
                    id: data.id || Date.now(), // Fallback ID nếu không có
                    createdAt: data.createdAt || new Date().toISOString(),
                    role: data.role || 'assistant',
                    username: data.username || 'AI Assistant'
                };

                addMessageSafely(messageWithDefaults);
            }),

            websocketService.on('ai_response', (data) => {
                console.log('🤖 AI response received:', data);
                console.log('📊 Chart data present:', !!data.url_chart);
                
                const messageWithDefaults = {
                    ...data,
                    id: data.id || Date.now(),
                    createdAt: data.createdAt || new Date().toISOString(),
                    role: data.role || 'assistant',
                    username: data.username || 'AI Assistant'
                };

                addMessageSafely(messageWithDefaults);
            }),

            websocketService.on('online_users', (data) => {
                console.log('👥 Online users updated:', data.onlineUsers);
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
            }),

            websocketService.on('ai_error', (data) => {
                console.error('🤖❌ AI error:', data);
                setConnectionError(data.error);
            })
        ];

        // Lưu references để cleanup
        unsubscribeRefs.current = unsubscribes;

        return () => {
            // Cleanup
            unsubscribes.forEach(unsubscribe => unsubscribe());
            websocketService.cleanup();
        };
    }, [authToken, serverUrl, addMessageSafely]);

    // Debug: Log messages khi thay đổi
    useEffect(() => {
        console.log('📝 Messages updated, total:', messages.length);
        const messagesWithChart = messages.filter(msg => msg.url_chart);
        console.log('📊 Messages with chart:', messagesWithChart.length);
    }, [messages]);

    // Join conversation
    const joinConversation = useCallback((conversationId) => {
        if (!conversationId) return false;

        console.log('🏠 Joining conversation:', conversationId);
        
        // Clear previous conversation data
        setOnlineUsers([]);
        setTypingUsers(new Set());

        return websocketService.joinConversation(conversationId);
    }, []);

    // Leave conversation
    const leaveConversation = useCallback((conversationId) => {
        console.log('🚪 Leaving conversation:', conversationId);
        
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
        console.log('📤 Sending message:', { conversationId, content, role });
        return websocketService.sendMessage(conversationId, content, role);
    }, []);

    // Send typing indicator
    const sendTyping = useCallback((conversationId, isTyping) => {
        return websocketService.sendTyping(conversationId, isTyping);
    }, []);

    // Notify file uploaded
    const notifyFileUploaded = useCallback((conversationId, fileInfo) => {
        console.log('📎 File uploaded notification:', fileInfo);
        return websocketService.notifyFileUploaded(conversationId, fileInfo);
    }, []);

    // Get online users
    const getOnlineUsers = useCallback((conversationId) => {
        return websocketService.getOnlineUsers(conversationId);
    }, []);

    // Manual retry connection
    const retryConnection = useCallback(() => {
        console.log('🔄 Retrying connection...');
        websocketService.retryConnection();
    }, []);

    // Add message to local state (for optimistic updates)
    const addMessage = useCallback((message) => {
        console.log('➕ Adding message manually:', message);
        addMessageSafely(message);
    }, [addMessageSafely]);

    // Clear messages
    const clearMessages = useCallback(() => {
        console.log('🧹 Clearing messages');
        setMessages([]);
    }, []);

    // Set messages từ API
    const setMessagesFromAPI = useCallback((msgs) => {
        console.log('📥 Setting messages from API:', msgs.length);
        console.log('📊 Messages with chart from API:', msgs.filter(m => m.url_chart).length);
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
        updateMessage,

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