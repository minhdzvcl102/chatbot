import React from "react";

const ChatHistory = ({ conversations, selectedConversationId, onSelectConversation }) => {
  return (
    <ul className="space-y-2">
      {conversations.map((conversation) => (
        <li
          key={conversation.id}
          className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition ${
            selectedConversationId === conversation.id
              ? "bg-blue-50 border border-blue-200"
              : "bg-gray-50 hover:bg-gray-100"
          }`}
          onClick={() => onSelectConversation(conversation.id)}
        >
          <div className="flex-1">
            <div className="font-medium text-black text-sm">{conversation.user}</div>
            <div className="text-xs text-gray-500">{conversation.type}</div>
          </div>
        </li>
      ))}
      {conversations.length === 0 && (
        <li className="text-gray-400 text-sm text-center py-4 select-none">
          Không có đoạn hội thoại nào.
        </li>
      )}
    </ul>
  );
};

export default ChatHistory;