import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileText,
  Download,
  Trash2,
  X,
  Upload,
  AlertCircle,
} from "lucide-react";
import AppLayout from "../components/AppLayout";
import SidebarWrapper from "../components/SidebarWrapper";
import SidebarContent from "../components/SidebarContent";
import ChatInput from "../components/ChatInput";
import {
  conversationService,
  authService,
} from "../services/conversationService";
import { messageService } from "../services/messageService";
import { uploadService } from "../services/uploadService";

const Chatbox = () => {
  // State management
  const [activeTab, setActiveTab] = useState("history");
  const [showNewChatForm, setShowNewChatForm] = useState(false);
  const [newChatName, setNewChatName] = useState("");
  const [conversations, setConversations] = useState([]);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [selectedConversationId, setSelectedConversationId] = useState(null);
  const [message, setMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);

  // File upload states
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const fileInputRef = useRef();
  const avatarRef = useRef();
  const messagesEndRef = useRef();
  const navigate = useNavigate();

  // Load conversations on component mount
  useEffect(() => {
    console.log("🚀 Component mounted, loading conversations...");
    loadConversations();
  }, []);

  // Load messages when conversation is selected
  useEffect(() => {
    if (selectedConversationId) {
      loadMessages(selectedConversationId);
      loadUploadedFiles(selectedConversationId);
    } else {
      setMessages([]);
      setUploadedFiles([]);
    }
  }, [selectedConversationId]);

  // Auto scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Track selectedConversationId changes
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
    }
  }, [selectedConversationId, conversations]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // API handler functions
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
      setMessages(conversationMessages);
    } catch (error) {
      console.error("❌ Error loading messages:", error);
      setMessages([]);
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
      await loadConversations(); // Reload conversations

      console.log("🎯 Setting selected conversation ID to:", newConvId);
      setSelectedConversationId(newConvId);
    } catch (error) {
      console.error("❌ Error creating conversation:", error);
    }
  };

  const updateConversationTitle = async (conversationId, newTitle) => {
    try {
      await conversationService.updateConversation(conversationId, newTitle);

      // Update local state
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

      // Update local state
      setConversations((prev) =>
        prev.filter((conv) => conv.id !== conversationId)
      );

      // If deleted conversation was selected, select another one
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

  // File upload handlers
  const handleFileUpload = async (file) => {
    if (!file || !selectedConversationId) return;

    // Validate file type
    if (file.type !== "application/pdf") {
      setUploadError("Chỉ hỗ trợ file PDF");
      return;
    }

    // Validate file size (10MB limit)
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

      // Reload files list
      await loadUploadedFiles(selectedConversationId);

      // Clear selected file
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

      // Reload files list
      await loadUploadedFiles(selectedConversationId);
    } catch (error) {
      console.error("❌ Delete file error:", error);
    }
  };

  const handleDownloadFile = (file) => {
    const fileUrl = uploadService.getFileUrl(file.fileName);
    window.open(fileUrl, "_blank");
  };

  // Event handlers
  const handleCreateNewChat = async () => {
    const title = newChatName.trim() || "Cuộc hội thoại mới";
    console.log("🎬 Handling new chat creation with title:", title);
    await createConversation(title);
    setNewChatName("");
    setShowNewChatForm(false);
  };

  const handleSend = async () => {
    if (!message.trim() || !selectedConversationId || sendingMessage) {
      console.log("⚠️ Cannot send message:", {
        message: message.trim(),
        selectedConversationId,
        sendingMessage,
      });
      return;
    }

    try {
      setSendingMessage(true);
      console.log(
        "📤 Sending message in conversation ID:",
        selectedConversationId
      );
      console.log("📝 Message content:", message);

      // Send the message
      await messageService.sendMessage(selectedConversationId, message);

      // Clear the input
      setMessage("");

      // Reload messages to get the latest ones (including AI response if implemented)
      await loadMessages(selectedConversationId);
    } catch (error) {
      console.error("❌ Error sending message:", error);
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

  if (loading) {
    return (
      <AppLayout>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-lg text-gray-500">Đang tải...</div>
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

      {/* Main content */}
      <div className="flex-1 flex flex-col h-full min-h-0">
        {/* Chat display area */}
        <div className="flex-1 overflow-y-auto min-h-0 px-4">
          {conversations.length === 0 ? (
            <div className="w-full h-full flex flex-col flex-1 justify-center items-center">
              <p className="text-lg text-gray-500 font-semibold">
                Không có đoạn hội thoại nào tồn tại.
              </p>
            </div>
          ) : !selectedConversationId ? (
            <div className="w-full h-full flex flex-col flex-1 gap-4 justify-center items-center">
              <h1 className="text-3xl font-bold text-black mb-2 text-center">
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
              {messages.length === 0 ? (
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
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${
                        msg.role === "user" ? "justify-end" : "justify-start"
                      }`}
                    >
                      <div
                        className={`flex max-w-[80%] ${
                          msg.role === "user" ? "flex-row-reverse" : "flex-row"
                        } gap-3`}
                      >
                        {/* Avatar */}
                        <div className="flex-shrink-0">
                          {msg.role === "user" ? (
                            <img
                              src="https://randomuser.me/api/portraits/men/75.jpg"
                              alt="User"
                              className="w-8 h-8 rounded-full object-cover"
                            />
                          ) : (
                            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-semibold">
                              AI
                            </div>
                          )}
                        </div>

                        {/* Message content */}
                        <div
                          className={`flex flex-col ${
                            msg.role === "user" ? "items-end" : "items-start"
                          }`}
                        >
                          <div
                            className={`px-4 py-3 rounded-2xl ${
                              msg.role === "user"
                                ? "bg-blue-600 text-white rounded-br-md"
                                : "bg-gray-100 text-gray-800 rounded-bl-md"
                            }`}
                          >
                            <p className="text-sm leading-relaxed whitespace-pre-wrap">
                              {msg.content}
                            </p>
                          </div>
                          <span className="text-xs text-gray-500 mt-1 px-1">
                            {formatMessageTime(msg.createdAt)}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}

                  {sendingMessage && (
                    <div className="flex justify-end">
                      <div className="flex max-w-[80%] flex-row-reverse gap-3">
                        <div className="flex-shrink-0">
                          <img
                            src="https://randomuser.me/api/portraits/men/75.jpg"
                            alt="User"
                            className="w-8 h-8 rounded-full object-cover"
                          />
                        </div>
                        <div className="flex flex-col items-end">
                          <div className="px-4 py-3 rounded-2xl bg-blue-600 text-white rounded-br-md opacity-70">
                            <p className="text-sm">Đang gửi...</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Chat input */}
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
            />
          </div>
        )}
      </div>

      {/* File upload modal */}
      {showFileUpload && selectedFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-xl shadow-lg p-6 min-w-[400px] max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">Upload File</h3>
              <button
                onClick={() => {
                  setShowFileUpload(false);
                  setSelectedFile(null);
                  setUploadError("");
                  if (fileInputRef.current) {
                    fileInputRef.current.value = "";
                  }
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X size={20} />
              </button>
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

      {/* New chat modal */}
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
                Huỷ
              </button>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default Chatbox;
