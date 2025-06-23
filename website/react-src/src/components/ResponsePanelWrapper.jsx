import React from "react";
import { ChevronLeft, ChevronRight, Bot } from "lucide-react";

const ResponsePanelWrapper = ({ children, isCollapsed, onToggle }) => {
  return (
    <>
      <aside
        className={`relative bg-white border-l border-gray-100 h-screen flex flex-col transition-all duration-300 ${
          isCollapsed ? "w-0 min-w-0 overflow-hidden" : "w-[500px] min-w-[500px] lg:w-[600px] lg:min-w-[600px] xl:w-[700px] xl:min-w-[700px]"
        }`}
      >
        {!isCollapsed && (
          <>
            {children}
            <button
              className="absolute top-1/2 -left-4 z-20 transform -translate-y-1/2 bg-white border border-gray-200 rounded-full shadow p-1 flex items-center justify-center hover:bg-gray-50 transition"
              style={{ boxShadow: "0 2px 8px 0 rgba(0,0,0,0.06)" }}
              onClick={onToggle}
              title="Ẩn panel phản hồi"
            >
              <ChevronRight size={22} />
            </button>
          </>
        )}
        {isCollapsed && (
          <button
            className="fixed right-0 top-1/2 z-50 transform -translate-y-1/2 bg-white border border-gray-200 rounded-full shadow p-1 flex items-center justify-center hover:bg-gray-50 transition"
            style={{ boxShadow: "0 2px 8px 0 rgba(0,0,0,0.06)" }}
            onClick={onToggle}
            title="Hiện panel phản hồi"
          >
            <ChevronLeft size={22} />
          </button>
        )}
      </aside>
             
      {/* Floating toggle button with AI icon when collapsed */}
      {isCollapsed && (
        <div className="fixed right-4 bottom-4 z-40">
          <button
            onClick={onToggle}
            className="bg-blue-600 text-white p-3 rounded-full shadow-lg hover:bg-blue-700 transition transform hover:scale-105"
            title="Mở panel phản hồi AI"
          >
            <Bot size={24} />
          </button>
        </div>
      )}
    </>
  );
};

export default ResponsePanelWrapper;