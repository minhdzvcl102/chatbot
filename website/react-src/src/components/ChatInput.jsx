import React from "react";
import { Send, Paperclip } from "lucide-react";

const ChatInput = ({
  message,
  setMessage,
  handleSend,
  handleFileChange,
  fileInputRef,
  selectedFile,
  disabled,
  isProcessing, // Add this new prop
  onChange,
  onBlur,
}) => {
  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Determine if input should be disabled
  const isInputDisabled = disabled || isProcessing;

  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-4 border-t border-gray-200 bg-white">
      <div className="flex items-center gap-3">
        <input
          type="file"
          accept="application/pdf"
          onChange={handleFileChange}
          ref={fileInputRef}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="p-2 text-gray-500 hover:text-blue-600 transition disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={isInputDisabled}
        >
          <Paperclip size={20} />
        </button>
        <textarea
          className="flex-1 px-4 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none disabled:bg-gray-50 disabled:cursor-not-allowed"
          placeholder={isProcessing ? "Đang xử lý câu hỏi..." : "Nhập tin nhắn..."}
          value={message}
          onChange={(e) => {
            setMessage(e.target.value);
            onChange?.(e);
          }}
          onBlur={onBlur}
          onKeyPress={handleKeyPress}
          disabled={isInputDisabled}
          rows={1}
          style={{ minHeight: "40px" }}
        />
        <button
          onClick={handleSend}
          className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={isInputDisabled || !message.trim()}
        >
          <Send size={20} />
        </button>
      </div>
      
      {/* Optional: Show processing indicator */}
      {isProcessing && (
        <div className="flex items-center justify-center mt-2 text-sm text-gray-600">
          <div className="flex items-center gap-2">
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
            <span>AI đang xử lý câu hỏi của bạn...</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatInput;