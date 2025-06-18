import React from "react";
import { Paperclip, Send } from "lucide-react";

const ChatInput = ({
  message,
  setMessage,
  handleSend,
  handleFileChange,
  fileInputRef,
  selectedFile,
}) => {
  return (
    <div className="w-full flex items-center pb-8">
      <div className="flex items-center w-full max-w-3xl mx-auto bg-white border border-gray-200 rounded-xl overflow-hidden">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Message AI..."
          className="flex-1 px-5 py-4 text-base bg-transparent focus:outline-none"
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
        />
        <button
          className="p-3 text-gray-400 hover:text-blue-600 transition"
          type="button"
          onClick={() => fileInputRef.current && fileInputRef.current.click()}
        >
          <Paperclip size={20} />
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            onChange={handleFileChange}
          />
        </button>
        <button
          className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded-none rounded-r-xl transition text-base"
          onClick={handleSend}
        >
          Send
          <Send size={18} className="inline ml-2 -mt-1" />
        </button>
      </div>
    </div>
  );
};

export default ChatInput;
