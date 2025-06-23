import React from "react";
import { Bot, Copy, Download, RefreshCw } from "lucide-react";

const ResponsePanel = ({ 
  currentResponse, 
  isGenerating, 
  onCopyResponse, 
  onDownloadResponse, 
  onRegenerateResponse 
}) => {
  const formatMessageTime = (timestamp) => {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    return date.toLocaleTimeString("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
            <Bot size={16} className="text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">AI Response</h3>
            <p className="text-xs text-gray-500">Phản hồi từ trợ lý AI</p>
          </div>
        </div>
        
        {currentResponse && !isGenerating && (
          <div className="flex items-center gap-2">
            <button
              onClick={onCopyResponse}
              className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition"
              title="Sao chép"
            >
              <Copy size={16} />
            </button>
            <button
              onClick={onDownloadResponse}
              className="p-2 text-gray-500 hover:text-green-600 hover:bg-green-50 rounded-lg transition"
              title="Tải xuống"
            >
              <Download size={16} />
            </button>
            <button
              onClick={onRegenerateResponse}
              className="p-2 text-gray-500 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition"
              title="Tạo lại"
            >
              <RefreshCw size={16} />
            </button>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {isGenerating ? (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-4"></div>
            <p className="text-gray-600 text-center">
              AI đang tạo phản hồi...
            </p>
            <div className="mt-4 flex items-center gap-2">
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
            </div>
          </div>
        ) : currentResponse ? (
          <div className="space-y-4">
            {/* Response metadata */}
            <div className="flex items-center justify-between text-xs text-gray-500 pb-2 border-b border-gray-100">
              <span>Thời gian: {formatMessageTime(currentResponse.createdAt)}</span>
              <span>{currentResponse.content?.length || 0} ký tự</span>
            </div>

            {/* Response content */}
            <div className="prose prose-sm max-w-none">
              <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">
                {currentResponse.content}
              </div>
            </div>

            {/* Response actions footer */}
            <div className="mt-6 pt-4 border-t border-gray-100">
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={onCopyResponse}
                  className="flex items-center gap-2 px-3 py-2 bg-blue-50 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-100 transition"
                >
                  <Copy size={14} />
                  Sao chép
                </button>
                <button
                  onClick={onDownloadResponse}
                  className="flex items-center gap-2 px-3 py-2 bg-green-50 text-green-700 rounded-lg text-sm font-medium hover:bg-green-100 transition"
                >
                  <Download size={14} />
                  Tải xuống
                </button>
                <button
                  onClick={onRegenerateResponse}
                  className="flex items-center gap-2 px-3 py-2 bg-purple-50 text-purple-700 rounded-lg text-sm font-medium hover:bg-purple-100 transition"
                >
                  <RefreshCw size={14} />
                  Tạo lại
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mb-4">
              <Bot size={24} className="text-gray-400" />
            </div>
            <h4 className="text-lg font-semibold text-gray-700 mb-2">
              Chưa có phản hồi
            </h4>
            <p className="text-gray-500 max-w-sm">
              Gửi tin nhắn để nhận phản hồi từ AI. Phản hồi sẽ hiển thị ở đây.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ResponsePanel;