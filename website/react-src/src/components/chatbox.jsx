import React, { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
// Cài đặt thư viện icon: npm install lucide-react
import {
  MessageSquare,
  Plus,
  FileText,
  Paperclip,
  Send,
  User,
  Menu,
  ChevronLeft,
  ChevronRight,
  UserCircle,
  KeyRound,
  LogOut,
  Pencil,
  Trash2,
  MoreVertical,
} from "lucide-react";
import AppLayout from "./AppLayout";
import SidebarWrapper from "./SidebarWrapper";
import SidebarContent from "./SidebarContent";
import ChatInput from "./ChatInput";
import ChatHistory from "./ChatHistory";

// --- Dữ liệu mẫu cho Lịch sử Chat ---
const chatHistory = [
  {
    id: 1,
    user: "ChatGPT",
    type: "AI chat",
    avatar: "https://randomuser.me/api/portraits/men/32.jpg",
    messages: [],
  },
];

const documentList = [
  {
    id: 1,
    name: "Document.pdf",
    size: "1,2MB",
    type: "file pdf",
    icon: <FileText size={20} className="text-gray-400" />,
  },
];

const Chatbox = () => {
  const [activeTab, setActiveTab] = useState("history");
  const [showNewChatForm, setShowNewChatForm] = useState(false);
  const [newChatName, setNewChatName] = useState("");
  const [chats, setChats] = useState(chatHistory);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [selectedChatId, setSelectedChatId] = useState(chats[0]?.id || null);
  const [message, setMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef();
  const navigate = useNavigate();
  // Đăng xuất modal
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  // Avatar menu
  const [menuOpen, setMenuOpen] = useState(false);
  const avatarRef = useRef();
  const logout = async () => {
    try {
      if (localStorage.getItem('authToken')) {
        await fetch('/account/logout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('authToken')}`
          }
        });
        localStorage.removeItem('authToken'); // Xoá token khỏi localStorage
        navigate('/login'); // Chuyển hướng về trang đăng nhập
      }
    } catch (error) {
      console.error("Logout failed:", error);
    }
  }
  // Gửi message (demo)
  const handleSend = () => {
    if (!message.trim()) return;
    setChats((prevChats) =>
      prevChats.map((chat) =>
        chat.id === selectedChatId
          ? {
            ...chat,
            messages: [
              ...chat.messages,
              {
                id: Date.now(),
                text: message,
                sender: "user",
                time: new Date().toLocaleTimeString(),
              },
            ],
          }
          : chat
      )
    );
    setMessage("");
  };
  // Đính kèm file (demo)
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

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
          {/* AvatarMenu và modal logout giữ nguyên như cũ, có thể tách riêng nếu muốn */}
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
                  onClick={() => {
                    setMenuOpen(false);
                    setShowLogoutModal(true);
                    logout()
                  }}
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
                    onClick={() => {
                      setShowLogoutModal(false);
                      navigate("/login");
                    }}
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
          chats={chats}
          setChats={setChats}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          setShowNewChatForm={setShowNewChatForm}
          isCollapsed={isCollapsed}
        />
      </SidebarWrapper>
      {/* Main content */}
      <div className="flex-1 flex flex-col h-full min-h-0">
        {/* Vùng chat cuộn riêng */}
        <div className="flex-1 overflow-y-auto min-h-0 px-0">
          {chats.length === 0 ? (
            <div className="w-full h-full flex flex-col flex-1 justify-center items-center">
              <p className="text-lg text-gray-500 font-semibold">
                Không có đoạn hội thoại nào tồn tại.
              </p>
            </div>
          ) : (
            <div className="w-full h-full flex flex-col flex-1 gap-4">
              {(() => {
                const currentChat = chats.find((c) => c.id === selectedChatId);
                if (!currentChat || currentChat.messages.length === 0) {
                  return (
                    <>
                      <h1 className="text-3xl font-bold text-black mb-2 text-center">
                        ChatGPT 3.5
                      </h1>
                      <p className="text-gray-500 text-center max-w-lg mx-auto">
                        This is a preview of the next generation of AI chat,
                        available for a limited time.
                      </p>
                    </>
                  );
                }
                return (
                  <div className="flex flex-col gap-3 w-full">
                    {currentChat.messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={`flex ${msg.sender === "user"
                          ? "justify-end"
                          : "justify-start"
                          }`}
                      >
                        <div
                          className={`px-6 py-3 rounded-xl max-w-[90%] text-base ${msg.sender === "user"
                            ? "bg-blue-100 text-blue-900"
                            : "bg-gray-100 text-gray-800"
                            }`}
                        >
                          {msg.text}
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>
          )}
        </div>
        {/* Input message cố định dưới cùng */}
        {chats.length > 0 && (
          <div className="w-full">
            <ChatInput
              message={message}
              setMessage={setMessage}
              handleSend={handleSend}
              handleFileChange={handleFileChange}
              fileInputRef={fileInputRef}
              selectedFile={selectedFile}
            />
          </div>
        )}
      </div>
      {/* Modal tạo New chat */}
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
                onClick={() => {
                  const name = newChatName.trim() || "Cuộc hội thoại mới";
                  const newId = Date.now();
                  setChats((prev) => [
                    {
                      id: newId,
                      user: name,
                      type: "AI chat",
                      avatar: "https://randomuser.me/api/portraits/men/32.jpg",
                      messages: [],
                    },
                    ...prev,
                  ]);
                  setSelectedChatId(newId);
                  setNewChatName("");
                  setShowNewChatForm(false);
                }}
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
