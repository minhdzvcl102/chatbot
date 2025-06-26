import React, { useState, useEffect, useRef } from "react";
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
// import ChatHistory from "./ChatHistory"; // Có thể không cần import nếu không dùng trực tiếp
import axios from "axios";

// Import custom Hook useWebSocket
import useWebSocket from "../websocket"; // Điều chỉnh đường dẫn nếu cần

// --- Dữ liệu mẫu cho Lịch sử Chat ---
const chatHistory = [
  {
    id: 1,
    user: "ChatGPT",
    type: "AI chat",
    avatar: "https://randomuser.me/api/portraits/men/32.jpg",
    messages: [], // This will hold the actual chat messages
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
  const [inputMessage, setInputMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef();
  const navigate = useNavigate();

  // Sử dụng custom Hook useWebSocket ở đây
  const WEBSOCKET_URL = "ws://localhost:8080";
  const ws = useWebSocket(WEBSOCKET_URL, selectedChatId, setChats); // Truyền các props cần thiết

  // Đăng xuất modal
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  // Avatar menu
  const [menuOpen, setMenuOpen] = useState(false);
  const avatarRef = useRef();

  const [lastUploadedPdf, setLastUploadedPdf] = useState(null);
  const [uploadedPdfs, setUploadedPdfs] = useState([]);
  const [showPdfList, setShowPdfList] = useState(false);

  const logout = async () => {
    try {
      if (localStorage.getItem("authToken")) {
        await axios.post("http://localhost:3001" + "/account/logout");
        localStorage.removeItem("authToken");
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
          ws.current.close(); // Đóng kết nối WebSocket khi đăng xuất
        }
        navigate("/login");
      }
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  // Gửi message (hỏi AI hoặc hỏi về PDF)
  const handleSend = () => {
    if (!inputMessage.trim()) return;

    // Lấy lịch sử hội thoại hiện tại (user + assistant)
    const currentChat = chats.find((c) => c.id === selectedChatId);
    const messages = [];
    if (currentChat && currentChat.messages.length > 0) {
      currentChat.messages.forEach((msg) => {
        messages.push({
          role: msg.sender === "user" ? "user" : "assistant",
          content: msg.text,
        });
      });
    }
    // Thêm message mới của user
    messages.push({ role: "user", content: inputMessage });

    // Nếu là hội thoại mới (chưa có system message), prepend system message
    if (!messages.length || messages[0].role !== "system") {
      messages.unshift({
        role: "system",
        content:
          "Bạn là trợ lý AI, hãy trả lời bằng tiếng Việt, hiểu các tham chiếu như 'đoạn trên', 'ý trước', và chấp nhận viết tắt, sai chính tả của người dùng.",
      });
    }

    if (lastUploadedPdf) {
      // Gửi câu hỏi về PDF vừa upload, truyền messages thay vì chỉ question
      fetch("http://localhost:5000/pdf/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: lastUploadedPdf,
          messages,
        }),
      })
        .then((res) => res.json())
        .then((data) => {
          setChats((prevChats) =>
            prevChats.map((chat) =>
              chat.id === selectedChatId
                ? {
                    ...chat,
                    messages: [
                      ...chat.messages,
                      {
                        id: Date.now(),
                        text: inputMessage,
                        sender: "user",
                        time: new Date().toLocaleTimeString(),
                      },
                      data.answer
                        ? {
                            id: Date.now() + 1,
                            text: data.answer,
                            sender: "ai",
                            time: new Date().toLocaleTimeString(),
                          }
                        : null,
                    ].filter(Boolean),
                  }
                : chat
            )
          );
          if (data.error) {
            alert("Lỗi: " + data.error);
          }
        })
        .catch(() => {
          alert("Lỗi kết nối tới AI Service!");
        });
      setInputMessage("");
      return;
    }

    // Nếu không có file PDF, gửi như chat bình thường (truyền messages)
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: "user_message", messages }));
    }
    setChats((prevChats) =>
      prevChats.map((chat) =>
        chat.id === selectedChatId
          ? {
              ...chat,
              messages: [
                ...chat.messages,
                {
                  id: Date.now(),
                  text: inputMessage,
                  sender: "user",
                  time: new Date().toLocaleTimeString(),
                },
              ],
            }
          : chat
      )
    );
    setInputMessage("");
  };

  // Đính kèm file (upload PDF qua nút kẹp giấy)
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result.split(",")[1];
      fetch("http://localhost:5000/file/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_content: base64,
          filename: file.name, // Đúng tên file gốc
        }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.status === "success" && data.txt_file) {
            setLastUploadedPdf(file.name);
            setUploadedPdfs((prev) =>
              prev.includes(file.name) ? prev : [...prev, file.name]
            );
            alert(
              `Đã upload file PDF: ${file.name}. Bạn có thể hỏi về nội dung file này!`
            );
          } else {
            alert("Đã nhận file : " + JSON.stringify(data));
          }
        })
        .catch((err) => {
          alert("Lỗi upload file PDF!");
        });
    };
    reader.readAsDataURL(file);
  };

  const currentChat = chats.find((c) => c.id === selectedChatId);

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
                  onClick={() => {
                    setMenuOpen(false);
                    setShowLogoutModal(true);
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
                      logout();
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
          setSelectedChatId={setSelectedChatId}
          selectedChatId={selectedChatId}
        />
      </SidebarWrapper>
      {/* Main content */}
      <div className="flex-1 flex flex-col h-full min-h-0">
        <div className="flex-1 overflow-y-auto min-h-0 px-0">
          {/* (Tùy chọn) Hiển thị thông báo nếu có file PDF vừa upload */}
          {lastUploadedPdf && (
            <div className="px-4 py-2 text-sm text-blue-700 bg-blue-50 rounded mx-4 my-2">
              Bạn đang hỏi về file <b>{lastUploadedPdf}</b>. Hãy nhập câu hỏi để
              hỏi AI về nội dung file này!
              <button
                className="ml-2 text-xs text-blue-500 underline"
                onClick={() => setLastUploadedPdf(null)}
              >
                Hủy hỏi về file này
              </button>
            </div>
          )}

          {chats.length === 0 || !selectedChatId ? (
            <div className="w-full h-full flex flex-col flex-1 justify-center items-center">
              <p className="text-lg text-gray-500 font-semibold">
                Không có đoạn hội thoại nào tồn tại.
              </p>
            </div>
          ) : (
            <div className="w-full h-full flex flex-col flex-1 gap-4 pt-4">
              {currentChat && currentChat.messages.length === 0 ? (
                <>
                  <h1 className="text-3xl font-bold text-black mb-2 text-center">
                    ChatGPT 3.5
                  </h1>
                  <p className="text-gray-500 text-center max-w-lg mx-auto">
                    This is a preview of the next generation of AI chat,
                    available for a limited time.
                  </p>
                </>
              ) : (
                <div className="flex flex-col gap-3 w-full px-4">
                  {currentChat?.messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${
                        msg.sender === "user" ? "justify-end" : "justify-start"
                      }`}
                    >
                      <div
                        className={`px-6 py-3 rounded-xl max-w-[90%] text-base ${
                          msg.sender === "user"
                            ? "bg-blue-100 text-blue-900"
                            : "bg-gray-100 text-gray-800"
                        }`}
                      >
                        {msg.text}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        {chats.length > 0 && selectedChatId && (
          <div className="w-full">
            {/* Nút mở danh sách file PDF đã upload */}
            {uploadedPdfs.length > 0 && (
              <div className="relative px-4 pb-2">
                <button
                  className="flex items-center gap-2 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded text-sm border border-gray-300 text-gray-700"
                  onClick={() => setShowPdfList((v) => !v)}
                >
                  <Paperclip size={16} /> Các file đã upload
                </button>
                {showPdfList && (
                  <div className="absolute bottom-full left-4 mb-2 w-64 bg-white border border-gray-200 rounded shadow-lg z-50 animate-fade-in">
                    <div className="p-2 font-semibold text-gray-700 border-b">
                      Chọn file PDF để hỏi:
                    </div>
                    {uploadedPdfs.map((pdf) => (
                      <button
                        key={pdf}
                        className={`w-full text-left px-4 py-2 text-sm hover:bg-blue-100 ${
                          lastUploadedPdf === pdf
                            ? "bg-blue-50 text-blue-900 font-bold"
                            : "text-gray-800"
                        }`}
                        onClick={() => {
                          setLastUploadedPdf(pdf);
                          setShowPdfList(false);
                        }}
                      >
                        {pdf}
                      </button>
                    ))}
                    <button
                      className="w-full px-4 py-2 text-xs text-gray-500 hover:bg-gray-100 border-t"
                      onClick={() => setShowPdfList(false)}
                    >
                      Đóng
                    </button>
                  </div>
                )}
              </div>
            )}
            <ChatInput
              message={inputMessage}
              setMessage={setInputMessage}
              handleSend={handleSend}
              handleFileChange={handleFileChange}
              fileInputRef={fileInputRef}
              selectedFile={selectedFile}
            />
          </div>
        )}
      </div>
      {showNewChatForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
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
