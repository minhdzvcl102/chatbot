import React from "react";

const AppLayout = ({ children, headerRight }) => {
  return (
    <div className="flex flex-col h-screen bg-[#f7f9fb]">
      <header className="flex justify-between items-center h-16 px-8 border-b border-gray-100 bg-white">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-black">Brainwave</span>
        </div>
        {headerRight && <div>{headerRight}</div>}
      </header>
      <div className="flex flex-1 min-h-0">{children}</div>
    </div>
  );
};

export default AppLayout;
