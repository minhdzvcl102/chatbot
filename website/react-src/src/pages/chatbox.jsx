import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileText,
  Download,
  Trash2,
  X,
  Bot,
  Upload,
  AlertCircle,
} from "lucide-react";
import AppLayout from "../components/AppLayout";
import SidebarWrapper from "../components/SidebarWrapper";
import SidebarContent from "../components/SidebarContent";
import ChatInput from "../components/ChatInput";
import ResponsePanel from "../components/ResponsePanel";
import ResponsePanelWrapper from "../components/ResponsePanelWrapper";
import { APP_WEBSOCKET_URL } from "../config/config";
import {
  conversationService,
  authService,
} from "../services/conversationService";
import { messageService } from "../services/messageService";
import { uploadService } from "../services/uploadService";
import { useWebSocket, useTypingIndicator } from "../hooks/useWebSocket";

const Chatbox = () => {
  const userID = localStorage.getItem("user.id");
  const [activeTab, setActiveTab] = useState("history");
  const [showNewChatForm, setShowNewChatForm] = useState(false);
  const [newChatName, setNewChatName] = useState("");
  const [conversations, setConversations] = useState([]);
  const [message, setMessage] = useState("");
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [selectedConversationId, setSelectedConversationId] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [responseCollapsed, setResponseCollapsed] = useState(false);
  const [currentResponse, setCurrentResponse] = useState(null);

  // Simplified AI processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [lastUserMessage, setLastUserMessage] = useState("");
  
  // NEW: State để theo dõi AI response realtime
  const [currentAIResponse, setCurrentAIResponse] = useState(null);

  const serverUrl = APP_WEBSOCKET_URL || "ws://localhost:3000";
  const authToken = localStorage.getItem("authToken");
  const {
    isConnected,
    messages,
    connectionError,
    joinConversation,
    leaveConversation,
    sendMessage: sendWebSocketMessage,
    sendTyping,
    notifyFileUploaded,
    onlineUsers,
    typingUsers,
    chartUrl,
    addMessage,
    clearMessages,
    setMessagesFromAPI,
  } = useWebSocket(authToken, serverUrl);

  const { startTyping, stopTyping } = useTypingIndicator(
    selectedConversationId,
    1000
  );

  const fileInputRef = useRef();
  const avatarRef = useRef();
  const messagesEndRef = useRef();
  const navigate = useNavigate();

  useEffect(() => {
    console.log("🚀 Component mounted, loading conversations...");
    loadConversations();
  }, []);

  useEffect(() => {
    if (selectedConversationId) {
      console.log("🔗 Joining WebSocket conversation:", selectedConversationId);
      joinConversation(selectedConversationId);
      loadMessages(selectedConversationId);
      loadUploadedFiles(selectedConversationId);
    } else {
      setUploadedFiles([]);
      clearMessages();
      setCurrentResponse(null);
      setCurrentAIResponse(null); // NEW: Clear current AI response
    }

    return () => {
      if (selectedConversationId) {
        leaveConversation(selectedConversationId);
      }
    };
  }, [
    selectedConversationId,
    joinConversation,
    leaveConversation,
    clearMessages,
  ]);

  useEffect(() => {
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      if (lastMessage.role === "assistant" || lastMessage.role === "bot") {
        setCurrentResponse(lastMessage);
        setCurrentAIResponse(null); // NEW: Clear realtime response khi đã có message final
        setIsProcessing(false);
      }
      scrollToBottom();
    }
  }, [messages]);

  // NEW: Effect để xử lý AI response events
  useEffect(() => {
    if (!selectedConversationId) return;

    const handleAIResponse = (data) => {
      console.log('🤖 Real-time AI response received:', data);
      console.log('📊 Chart data present:', !!data.url_chart);
      
      // Cập nhật current AI response ngay lập tức
      setCurrentAIResponse({
        id: `ai_response_${Date.now()}`,
        role: 'assistant',
        content: data.content || 'Đang tạo phản hồi...',
        url_chart: data.url_chart || null,
        createdAt: new Date().toISOString(),
        username: 'AI Assistant',
        isRealtime: true
      });
      
      // Nếu có chart, cập nhật response panel ngay lập tức
      if (data.url_chart) {
        setCurrentResponse({
          id: `ai_response_${Date.now()}`,
          role: 'assistant',
          content: data.content || 'Đang tạo phản hồi...',
          url_chart: data.url_chart,
          createdAt: new Date().toISOString(),
          username: 'AI Assistant'
        });
      }
      
      setIsProcessing(false);
    };

    const handleAIError = (data) => {
      console.error('🤖❌ AI error:', data);
      setCurrentAIResponse(null);
      setIsProcessing(false);
    };

    // Subscribe to AI response events
    const wsService = window.websocketService || {};
    if (wsService.on) {
      const unsubscribeAIResponse = wsService.on('ai_response', handleAIResponse);
      const unsubscribeAIError = wsService.on('ai_error', handleAIError);

      return () => {
        if (unsubscribeAIResponse) unsubscribeAIResponse();
        if (unsubscribeAIError) unsubscribeAIError();
      };
    }
  }, [selectedConversationId]);

  useEffect(() => {
    if (selectedConversationId) {
      const selectedConv = conversations.find(
        (c) => c.id === selectedConversationId
      );
      console.log("🔄 Selected conversation changed:");
      console.log("   ID:", selectedConversationId);
      console.log("   Title:", selectedConv?.user);
    } else {
      console.log("❌ No conversation selected");
      setCurrentResponse(null);
      setCurrentAIResponse(null); // NEW: Clear current AI response
    }
  }, [selectedConversationId, conversations]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const loadConversations = async () => {
    try {
      const formattedConversations =
        await conversationService.getConversations();
      setConversations(formattedConversations);
      if (formattedConversations.length > 0 && !selectedConversationId) {
        const firstId = formattedConversations[0].id;
        console.log("🎯 Auto-selecting first conversation ID:", firstId);
        setSelectedConversationId(firstId);
      }
    } catch (error) {
      console.error("❌ Error loading conversations:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (conversationId) => {
    if (!conversationId) return;
    try {
      setLoadingMessages(true);
      const conversationMessages = await messageService.getMessages(
        conversationId
      );
      setMessagesFromAPI(conversationMessages);
      const latestAIResponse = conversationMessages
        .filter((msg) => msg.role === "assistant" || msg.role === "bot")
        .pop();
      if (latestAIResponse) {
        setCurrentResponse(latestAIResponse);
      } else {
        setCurrentResponse(null);
      }
    } catch (error) {
      console.error("❌ Error loading messages:", error);
      clearMessages();
      setCurrentResponse(null);
    } finally {
      setLoadingMessages(false);
    }
  };

  const loadUploadedFiles = async (conversationId) => {
    if (!conversationId) return;
    try {
      setLoadingFiles(true);
      const files = await uploadService.getUploadedFiles(conversationId);
      setUploadedFiles(files);
    } catch (error) {
      console.error("❌ Error loading files:", error);
      setUploadedFiles([]);
    } finally {
      setLoadingFiles(false);
    }
  };

  const createConversation = async (title) => {
    try {
      const newConvId = await conversationService.createConversation(title);
      await loadConversations();
      console.log("🎯 Setting selected conversation ID to:", newConvId);
      setSelectedConversationId(newConvId);
    } catch (error) {
      console.error("❌ Error creating conversation:", error);
    }
  };

  const updateConversationTitle = async (conversationId, newTitle) => {
    try {
      await conversationService.updateConversation(conversationId, newTitle);
      setConversations((prev) =>
        prev.map((conv) =>
          conv.id === conversationId ? { ...conv, user: newTitle } : conv
        )
      );
    } catch (error) {
      console.error("❌ Error updating conversation:", error);
    }
  };

  const deleteConversation = async (conversationId) => {
    try {
      await conversationService.deleteConversation(conversationId);
      setConversations((prev) =>
        prev.filter((conv) => conv.id !== conversationId)
      );
      if (selectedConversationId === conversationId) {
        const remaining = conversations.filter(
          (conv) => conv.id !== conversationId
        );
        const newSelectedId = remaining.length > 0 ? remaining[0].id : null;
        console.log(
          "🔄 Deleted selected conversation, switching to:",
          newSelectedId
        );
        setSelectedConversationId(newSelectedId);
      }
    } catch (error) {
      console.error("❌ Error deleting conversation:", error);
    }
  };

  const logout = async () => {
    try {
      if (localStorage.getItem("authToken")) {
        await authService.logout();
        navigate("/login");
      }
    } catch (error) {
      console.error("❌ Logout failed:", error);
    }
  };

  const handleFileUpload = async (file) => {
    if (!file || !selectedConversationId) return;
    if (file.type !== "application/pdf") {
      setUploadError("Chỉ hỗ trợ file PDF");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setUploadError("File không được vượt quá 20MB");
      return;
    }
    try {
      setUploadingFile(true);
      setUploadError("");
      console.log("📤 Uploading file:", file.name);
      const result = await uploadService.uploadFile(
        selectedConversationId,
        file
      );
      console.log("✅ File uploaded successfully:", result);
      notifyFileUploaded(selectedConversationId, result.file);
      await loadUploadedFiles(selectedConversationId);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (error) {
      console.error("❌ Upload error:", error);
      setUploadError(error.message || "Lỗi khi upload file");
    } finally {
      setUploadingFile(false);
    }
  };

  const handleDeleteFile = async (fileId) => {
    if (!selectedConversationId) return;
    try {
      console.log("🗑️ Deleting file:", fileId);
      await uploadService.deleteFile(selectedConversationId, fileId);
      console.log("✅ File deleted successfully");
      await loadUploadedFiles(selectedConversationId);
    } catch (error) {
      console.error("❌ Delete file error:", error);
    }
  };

  const handleDownloadFile = (file) => {
    const fileUrl = uploadService.getFileUrl(file.fileName);
    window.open(fileUrl, "_blank");
  };

  const handleCopyResponse = async () => {
    if (currentResponse?.content) {
      try {
        await navigator.clipboard.writeText(currentResponse.content);
        console.log("✅ Response copied to clipboard");
      } catch (error) {
        console.error("❌ Failed to copy response:", error);
      }
    }
  };

  const handleDownloadResponse = () => {
    if (currentResponse?.content) {
      const blob = new Blob([currentResponse.content], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ai-response-${Date.now()}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  const handleRegenerateResponse = async () => {
    if (lastUserMessage && selectedConversationId) {
      try {
        setIsProcessing(true);
        setCurrentResponse(null);
        setCurrentAIResponse(null); // NEW: Clear realtime response
        sendWebSocketMessage(selectedConversationId, lastUserMessage);
      } catch (error) {
        console.error("❌ Error regenerating response:", error);
        setIsProcessing(false);
      }
    }
  };

  const handleCreateNewChat = async () => {
    const title = newChatName.trim() || "Cuộc hội thoại mới";
    console.log("🎬 Handling new chat creation with title:", title);
    await createConversation(title);
    setNewChatName("");
    setShowNewChatForm(false);
  };

  const handleSend = async () => {
    console.log("🚀 handleSend called at:", new Date().toISOString());
    if (!message.trim() || !selectedConversationId || sendingMessage || !userID) {
      console.log("⚠️ Cannot send message:", {
        message: message.trim(),
        selectedConversationId,
        sendingMessage,
        userID,
      });
      return;
    }

    try {
      setSendingMessage(true);
      setIsProcessing(true);
      setCurrentAIResponse(null); // NEW: Clear previous realtime response
      setLastUserMessage(message);
      console.log(
        "📤 Sending message in conversation ID:",
        selectedConversationId
      );
      console.log("📝 Message content:", message);
      sendWebSocketMessage(selectedConversationId, message, "user", userID);
      setMessage("");
    } catch (error) {
      console.error("❌ Error sending message:", error);
      setIsProcessing(false);
    } finally {
      setSendingMessage(false);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      console.log("📎 File selected:", file.name);
      setSelectedFile(file);
      setShowFileUpload(true);
    }
  };

  const handleTyping = (e) => {
    setMessage(e.target.value);
    startTyping();
  };

  const handleStopTyping = () => {
    stopTyping();
  };

  const handleLogout = () => {
    console.log("🔓 Logout button clicked");
    setMenuOpen(false);
    setShowLogoutModal(true);
    logout();
  };

  const confirmLogout = () => {
    console.log("✅ Logout confirmed");
    setShowLogoutModal(false);
    navigate("/login");
  };

  const handleSelectConversation = (conversationId) => {
    console.log("👆 User manually selected conversation ID:", conversationId);
    setSelectedConversationId(conversationId);
  };

  const formatMessageTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const userMessages = messages.filter((msg) => msg.role === "user");
  // NEW: Tạo danh sách messages để hiển thị (bao gồm cả AI response realtime)
  const displayMessages = [...messages];
  
  // Nếu có AI response realtime, thêm vào cuối danh sách
  if (currentAIResponse) {
    displayMessages.push(currentAIResponse);
  } else if (isProcessing) {
    // Chỉ hiển thị "đang xử lý" khi không có AI response realtime
    displayMessages.push({
      id: "processing",
      role: "assistant",
      content: "Đang xử lý câu hỏi...",
      createdAt: new Date().toISOString(),
      isProcessing: true,
    });
  }

  if (loading) {
    return (
      <AppLayout>
        <div className="flex flex-1 items-center items-center justify-center">
          <div className="text-lg text-gray-500">Loading...</div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout
      headerRight={
        <div className="relative" ref={avatarRef}>
          <img
            src="https://randomuser.me/api/portraits/men/75.jpg"
            alt="user avatar"
            className="w-10 h-10 rounded-full object-cover border cursor-pointer hover:ring-2 hover:ring-blue-400 transition"
            onClick={() => setMenuOpen((v) => !v)}
          />
          {menuOpen && (
            <div
              className="absolute right-0 top-14 w-48 bg-white rounded-xl shadow-xl border border-gray-100 z-30 animate-fade-in"
              style={{ minWidth: 180 }}
            >
              <div className="absolute -top-2 right-8 w-4 h-4 bg-white border-l border-t border-gray-100 rotate-45 z-10"></div>
              <ul className="py-2">
                <li className="flex items-center gap-2 px-5 py-2 text-gray-700 hover:bg-gray-50 cursor-pointer transition">
                  Hồ sơ cá nhân
                </li>
                <li className="flex items-center gap-2 px-5 py-2 text-gray-700 hover:bg-gray-50 cursor-pointer transition">
                  Đổi mật khẩu
                </li>
                <li
                  className="flex items-center gap-2 px-5 py-2 text-red-600 hover:bg-red-50 cursor-pointer transition border-t border-gray-100 mt-1"
                  onClick={handleLogout}
                >
                  Đăng xuất
                </li>
              </ul>
            </div>
          )}
          {showLogoutModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
              <div className="bg-white rounded-xl shadow-lg p-8 min-w-[320px] max-w-xs flex flex-col items-center animate-fade-in pointer-events-auto">
                <h3 className="text-lg font-bold mb-4 text-center">
                  Bạn có chắc muốn đăng xuất không?
                </h3>
                <div className="flex gap-3 mt-2">
                  <button
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-blue-700 transition"
                    onClick={confirmLogout}
                  >
                    Xác nhận
                  </button>
                  <button
                    className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm font-semibold hover:bg-gray-200 transition"
                    onClick={() => setShowLogoutModal(false)}
                  >
                    Hủy
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      }
    >
      <SidebarWrapper
        isCollapsed={isCollapsed}
        onToggle={() => setIsCollapsed((v) => !v)}
      >
        <SidebarContent
          conversations={conversations}
          setConversations={setConversations}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          setShowNewChatForm={setShowNewChatForm}
          onUpdateConversation={updateConversationTitle}
          onDeleteConversation={deleteConversation}
          selectedConversationId={selectedConversationId}
          onSelectConversation={handleSelectConversation}
          uploadedFiles={uploadedFiles}
          onDownloadFile={handleDownloadFile}
          handleDeleteFile={handleDeleteFile}
        />
      </SidebarWrapper>

      <div className="flex-1 flex flex-col h-full min-h-0">
        <div className="flex-1 overflow-y-auto min-h-0 px-4">
          {conversations.length === 0 ? (
            <div className="w-full h-full flex flex-col flex-1 justify-center items-center">
              <p className="text-lg text-gray-500 font-semibold">
                Không có đoạn hội thoại nào tồn tại.
              </p>
            </div>
          ) : !selectedConversationId ? (
            <div className="w-full h-full flex flex-col flex-1 gap-4 justify-center items-center">
              <h1 className="text-3 font-bold text-black mb-2 text-center">
                ChatGPT 3.5
              </h1>
              <p className="text-gray-500 text-center max-w-lg mx-auto">
                Chọn một cuộc hội thoại để bắt đầu chat.
              </p>
            </div>
          ) : loadingMessages ? (
            <div className="w-full h-full flex flex-col flex-1 justify-center items-center">
              <div className="text-lg text-gray-500">Đang tải tin nhắn...</div>
            </div>
          ) : (
            <div className="w-full max-w-4xl mx-auto py-4">
              {displayMessages.length === 0 ? (
                <div className="w-full h-full flex flex-col flex-1 gap-4 justify-center items-center py-20">
                  <h1 className="text-3xl font-bold text-black mb-2 text-center">
                    ChatGPT 3.5
                  </h1>
                  <p className="text-gray-500 text-center max-w-lg mx-auto">
                    Bắt đầu cuộc hội thoại bằng cách gửi tin nhắn đầu tiên.
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  {displayMessages
                    .sort(
                      (a, b) => new Date(a.createdAt) - new Date(b.createdAt)
                    )
                    .map((msg, index) => (
                      <div
                        key={msg.id || index}
                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"
                          }`}
                      >
                        {msg.role === "user" ? (
                          // Tin nhắn của User
                          <div className="flex max-w-[80%] flex-row-reverse gap-3">
                            <div className="flex-shrink-0">
                              <img
                                src="https://randomuser.me/api/portraits/men/75.jpg"
                                alt="User"
                                className="w-8 h-8 rounded-full object-cover"
                              />
                            </div>
                            <div className="flex flex-col items-end">
                              <div className="px-4 py-3 rounded-2xl bg-blue-600 text-white rounded-br-md">
                                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                                  {msg.content}
                                </p>
                              </div>
                              <span className="text-xs text-gray-500 mt-1 px-1">
                                {formatMessageTime(msg.createdAt)}
                              </span>
                            </div>
                          </div>
                        ) : (
                          // Tin nhắn của AI/Bot
                          <div className="flex max-w-[80%] gap-3">
                            <div className="flex-shrink-0">
                              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
                                <Bot size={16} className="text-white" />
                              </div>
                            </div>
                            <div className="flex flex-col">
                              <div
                                className={`px-4 py-3 rounded-2xl rounded-bl-md ${msg.isProcessing || msg.isRealtime
                                  ? "bg-gray-50 text-gray-600"
                                  : "bg-gray-100 text-gray-800"
                                  }`}
                              >
                                <div className="text-sm leading-relaxed whitespace-pre-wrap flex items-center gap-2">
                                  {msg.isProcessing && (
                                    <div className="flex items-center gap-1">
                                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                                      <div
                                        className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                                        style={{ animationDelay: "0.1s" }}
                                      ></div>
                                      <div
                                        className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                                        style={{ animationDelay: "0.2s" }}
                                      ></div>
                                    </div>
                                  )}
                                  {msg.content}
                                </div>
                                {/* NEW: Hiển thị biểu đồ ngay lập tức cho cả realtime và final message */}
                                {msg.url_chart && (
                                  <div className="mt-3">
                                    <img
                                      src={'data:image/png;base64,' + msg.url_chart}
                                      alt="Biểu đồ"
                                      className="rounded-lg border border-gray-200 max-w-xs sm:max-w-sm md:max-w-md lg:max-w-lg"
                                    />
                                  </div>
                                )}
                              </div>
                              {!msg.isProcessing && !msg.isRealtime && (
                                <span className="text-xs text-gray-500 mt-1 px-1">
                                  {formatMessageTime(msg.createdAt)}
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}

                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          )}
        </div>

        {conversations.length > 0 && selectedConversationId && (
          <div className="w-full">
            <ChatInput
              message={message}
              setMessage={setMessage}
              handleSend={handleSend}
              handleFileChange={handleFileChange}
              fileInputRef={fileInputRef}
              selectedFile={selectedFile}
              disabled={sendingMessage}
              isProcessing={isProcessing}
              onChange={handleTyping}
              onBlur={handleStopTyping}
            />
          </div>
        )}
      </div>

      <ResponsePanelWrapper
        isCollapsed={responseCollapsed}
        onToggle={() => setResponseCollapsed((prev) => !prev)}
      >
        <ResponsePanel
          currentResponse={currentResponse}
          isGenerating={isProcessing}
          chartUrl={chartUrl}
          onCopyResponse={handleCopyResponse}
          onDownloadResponse={handleDownloadResponse}
          onRegenerateResponse={handleRegenerateResponse}
        />
      </ResponsePanelWrapper>

      {showFileUpload && selectedFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="bg-white rounded-xl shadow-lg p-8 min-w-[320px] max-w-xs flex flex-col items-center animate-fade-in">
            <div className="relative w-full">
              <button
                onClick={() => {
                  setShowFileUpload(false);
                  setSelectedFile(null);
                  setUploadError("");
                  if (fileInputRef.current) {
                    fileInputRef.current.value = "";
                  }
                }}
                className="absolute top-0 right-0 mt-2 mr-2 text-gray-400 hover:text-gray-600"
                title="Đóng"
              >
                <X size={20} />
              </button>
              <h3 className="text-lg font-bold mb-4 text-center">
                Upload File
              </h3>
            </div>

            <div className="mb-4">
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <FileText size={24} className="text-blue-600" />
                <div className="flex-1">
                  <div className="font-medium text-gray-900">
                    {selectedFile.name}
                  </div>
                  <div className="text-sm text-gray-500">
                    {formatFileSize(selectedFile.size)}
                  </div>
                </div>
              </div>
            </div>

            {uploadError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
                <AlertCircle size={16} className="text-red-600" />
                <span className="text-sm text-red-700">{uploadError}</span>
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={() => handleFileUpload(selectedFile)}
                disabled={uploadingFile}
                className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg font-semibold hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {uploadingFile ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Đang upload...
                  </>
                ) : (
                  <>
                    <Upload size={16} />
                    Upload
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  setShowFileUpload(false);
                  setSelectedFile(null);
                  setUploadError("");
                  if (fileInputRef.current) {
                    fileInputRef.current.value = "";
                  }
                }}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg font-semibold hover:bg-gray-200 transition"
                disabled={uploadingFile}
              >
                Hủy
              </button>
            </div>
          </div>
        </div>
      )}

      {showNewChatForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="bg-white rounded-xl shadow-lg p-8 min-w-[320px] max-w-xs flex flex-col items-center animate-fade-in">
            <h3 className="text-lg font-bold mb-4 text-center">
              Tạo đoạn hội thoại mới
            </h3>
            <input
              type="text"
              className="w-full px-4 py-2 rounded-lg border border-gray-200 mb-4 focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="Nhập tên đoạn chat (tuỳ chọn)"
              value={newChatName}
              onChange={(e) => setNewChatName(e.target.value)}
              autoFocus
            />
            <div className="flex gap-3 mt-2">
              <button
                className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-blue-700 transition"
                onClick={handleCreateNewChat}
              >
                Tạo mới
              </button>
              <button
                className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm font-semibold hover:bg-gray-200 transition"
                onClick={() => {
                  setShowNewChatForm(false);
                  setNewChatName("");
                }}
              >
                Hủy
              </button>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default Chatbox;
