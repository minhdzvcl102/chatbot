import React, { useState } from 'react';
// Cài đặt thư viện icon: npm install lucide-react
import { BrainCircuit, MessageSquare, Send, LogOut, Plus, FileText } from 'lucide-react';

// --- Dữ liệu mẫu cho Lịch sử Chat ---
const chatHistory = [
  { id: 1, text: 'How does AI work?' },
  { id: 2, text: 'ChatGPT' },
  { id: 3, text: 'At a cat, made by fusing feline language processing algorithms' },
  { id: 4, text: 'You' },
  { id: 5, text: 'ChatGPT' },
  { id: 6, text: 'It can be used for a wide range of purposes, including' },
];

// --- Component Sidebar (Thanh bên trái) ---
const Sidebar = () => {
  const [activeTab, setActiveTab] = useState('history');

  return (
    <aside className="w-1/4 bg-[#1C1C1C] text-white p-6 flex flex-col">
      {/* Header */}
      <div className="flex items-center mb-10">
        <BrainCircuit size={32} className="text-purple-400 mr-3" />
        <h1 className="text-2xl font-bold">Brainwave</h1>
      </div>

      {/* Các nút chuyển tab */}
      <div className="flex bg-[#2D2D2D] rounded-lg p-1 mb-8">
        <button
          onClick={() => setActiveTab('history')}
          className={`w-1/2 flex items-center justify-center gap-2 py-2 rounded-md text-sm font-semibold transition ${
            activeTab === 'history'
              ? 'bg-gray-700 text-white'
              : 'text-gray-400 hover:bg-gray-700/50'
          }`}
        >
          <MessageSquare size={16} />
          <span>Chat History</span>
        </button>
        <button
          onClick={() => setActiveTab('documents')}
          className={`w-1/2 flex items-center justify-center gap-2 py-2 rounded-md text-sm font-semibold transition ${
            activeTab === 'documents'
              ? 'bg-gray-700 text-white'
              : 'text-gray-400 hover:bg-gray-700/50'
          }`}
        >
          <FileText size={16} />
          <span>Documents</span>
        </button>
      </div>

      {/* Lịch sử Chat */}
      <div className="flex-grow overflow-y-auto">
        <h2 className="text-sm font-semibold text-gray-400 mb-4">Chat History</h2>
        <ul>
          {chatHistory.map((chat) => (
            <li
              key={chat.id}
              className="flex items-center p-2 rounded-lg cursor-pointer hover:bg-gray-700 transition mb-2"
            >
              <MessageSquare size={18} className="text-gray-400 mr-3" />
              <span className="truncate text-sm">{chat.text}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Profile người dùng */}
      <div className="border-t border-gray-700 pt-4 mt-4">
        <div className="flex items-center">
          <img
            src="https://placehold.co/100x100/A9A9A9/FFFFFF?text=A"
            alt="User Avatar"
            className="w-10 h-10 rounded-full mr-3"
          />
          <div>
            <h4 className="font-semibold">Admin</h4>
            <a href="#" className="text-xs text-gray-400 hover:underline">
              View Profile
            </a>
          </div>
        </div>
      </div>
    </aside>
  );
};

// --- Component MainContent (Nội dung chính) ---
const MainContent = () => {
  const [message, setMessage] = useState('');

  return (
    <main className="w-3/4 bg-white flex flex-col h-screen">
      {/* Header của nội dung chính */}
      <header className="flex justify-end p-4 border-b border-gray-200">
        <button className="flex items-center gap-2 text-gray-600 font-semibold px-4 py-2 rounded-lg hover:bg-gray-100 transition">
          <LogOut size={18} />
          <span>Logout</span>
        </button>
      </header>

      {/* Vùng chào mừng */}
      <div className="flex-grow flex flex-col items-center justify-center text-center">
        <h1 className="text-5xl font-bold text-gray-800 mb-2">ChatGPT 3.5</h1>
        <p className="text-gray-500 max-w-md">
          This is a preview of the next generation of AI chat, suitable for a perfect bot.
        </p>
      </div>

      {/* Vùng nhập tin nhắn */}
      <div className="p-6">
        <div className="relative">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Message in..."
            className="w-full py-4 pl-5 pr-16 bg-gray-100 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
          <button className="absolute right-3 top-1/2 -translate-y-1/2 bg-purple-600 p-2 rounded-lg text-white hover:bg-purple-700 transition">
            <Send size={20} />
          </button>
        </div>
      </div>
    </main>
  );
};

// --- Component chính để hiển thị toàn bộ giao diện ---
const ChatGPTInterface = () => {
  return (
    <div className="flex h-screen font-sans bg-gray-100">
      <Sidebar />
      <MainContent />
    </div>
  );
};

export default ChatGPTInterface;
