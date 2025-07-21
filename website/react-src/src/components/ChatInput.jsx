import React, { useState, useRef, useEffect } from "react";
import { Send, Paperclip, X } from "lucide-react";

const ChatInput = ({
  message,
  setMessage,
  handleSend,
  handleFileChange,
  fileInputRef,
  selectedFile,
  disabled,
  isProcessing,
  onChange,
  onBlur,
}) => {
  const [isFocused, setIsFocused] = useState(false);
  const textareaRef = useRef(null);

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [message]);

  // Determine if input should be disabled
  const isInputDisabled = disabled || isProcessing;

  const removeSelectedFile = () => {
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    // Call parent's file change handler with null/empty event
    handleFileChange({ target: { files: [] } });
  };

  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-4">
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
        {/* Selected file preview */}
        {selectedFile && (
          <div className="px-4 py-3 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-red-100 rounded-lg flex items-center justify-center">
                <span className="text-red-600 text-xs font-medium">PDF</span>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900 truncate max-w-xs">
                  {selectedFile.name}
                </p>
                <p className="text-xs text-gray-500">
                  {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            </div>
            <button
              onClick={removeSelectedFile}
              className="p-1 hover:bg-gray-200 rounded-full transition-colors"
            >
              <X size={16} className="text-gray-500" />
            </button>
          </div>
        )}

        {/* Main input area */}
        <div className="p-4">
          <div className={`flex items-end gap-3 transition-all duration-200 ${
            isFocused ? 'ring-2 ring-blue-500/20' : ''
          } rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors`}>
            {/* File attachment button */}
            <input
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              ref={fileInputRef}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isInputDisabled}
              title="Đính kèm file PDF"
            >
              <Paperclip size={20} />
            </button>

            {/* Text input */}
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                className="w-full px-4 py-3 bg-transparent resize-none focus:outline-none placeholder-gray-500 text-gray-900 disabled:cursor-not-allowed"
                placeholder={isProcessing ? "Đang xử lý câu hỏi..." : "Nhập tin nhắn của bạn..."}
                value={message}
                onChange={(e) => {
                  setMessage(e.target.value);
                  onChange?.(e);
                }}
                onFocus={() => setIsFocused(true)}
                onBlur={(e) => {
                  setIsFocused(false);
                  onBlur?.(e);
                }}
                onKeyPress={handleKeyPress}
                disabled={isInputDisabled}
                rows={1}
                style={{ 
                  minHeight: "44px",
                  maxHeight: "120px",
                  lineHeight: "1.5"
                }}
              />
              
              {/* Character count (optional) */}
              {message.length > 0 && (
                <div className="absolute bottom-1 right-2 text-xs text-gray-400">
                  {message.length}
                </div>
              )}
            </div>

            {/* Send button */}
            <button
              onClick={handleSend}
              disabled={isInputDisabled || !message.trim()}
              className={`p-2 rounded-lg transition-all duration-200 ${
                isInputDisabled || !message.trim()
                  ? 'text-gray-400 cursor-not-allowed'
                  : 'text-white bg-blue-600 hover:bg-blue-700 shadow-lg hover:shadow-xl transform hover:scale-105'
              }`}
              title="Gửi tin nhắn"
            >
              <Send size={20} />
            </button>
          </div>

          {/* Status indicator */}
          {isProcessing && (
            <div className="flex items-center gap-2 mt-3 text-sm text-gray-600">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
              <span>Đang xử lý...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatInput;