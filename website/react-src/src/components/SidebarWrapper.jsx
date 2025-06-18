import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

const SidebarWrapper = ({ children, isCollapsed, onToggle }) => {
  return (
    <>
      <aside
        className={`relative bg-white border-r border-gray-100 h-screen flex flex-col transition-all duration-300 ${
          isCollapsed ? "w-0 min-w-0 overflow-hidden" : "w-80 min-w-[300px]"
        }`}
      >
        {!isCollapsed && (
          <>
            {children}
            <button
              className="absolute top-1/2 -right-4 z-20 transform -translate-y-1/2 bg-white border border-gray-200 rounded-full shadow p-1 flex items-center justify-center hover:bg-gray-50 transition"
              style={{ boxShadow: "0 2px 8px 0 rgba(0,0,0,0.06)" }}
              onClick={onToggle}
            >
              <ChevronLeft size={22} />
            </button>
          </>
        )}
        {isCollapsed && (
          <button
            className="fixed left-0 top-1/2 z-50 transform -translate-y-1/2 bg-white border border-gray-200 rounded-full shadow p-1 flex items-center justify-center hover:bg-gray-50 transition"
            style={{ boxShadow: "0 2px 8px 0 rgba(0,0,0,0.06)" }}
            onClick={onToggle}
          >
            <ChevronRight size={22} />
          </button>
        )}
      </aside>
    </>
  );
};

export default SidebarWrapper;
