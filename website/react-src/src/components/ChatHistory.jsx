import React from "react";

const ChatHistory = ({ chats, selectedChatId, onSelectChat }) => {
  return (
    <ul className="space-y-2">
      {chats.map((chat) => (
        <li
          key={chat.id}
          className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition ${
            selectedChatId === chat.id
              ? "bg-blue-50 border border-blue-200"
              : "bg-gray-50 hover:bg-gray-100"
          }`}
          onClick={() => onSelectChat(chat.id)}
        >
          <div className="flex-1">
            <div className="font-medium text-black text-sm">{chat.user}</div>
            <div className="text-xs text-gray-500">{chat.type}</div>
          </div>
        </li>
      ))}
      {chats.length === 0 && (
        <li className="text-gray-400 text-sm text-center py-4 select-none">
          Không có đoạn hội thoại nào.
        </li>
      )}
    </ul>
  );
};

export default ChatHistory;
