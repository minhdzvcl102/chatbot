import React from "react";
import {
  Plus,
  MessageSquare,
  FileText,
  MoreVertical,
  Pencil,
  Trash2,
} from "lucide-react";

const SidebarContent = ({
  chats,
  setChats,
  activeTab,
  setActiveTab,
  setShowNewChatForm,
  isCollapsed,
}) => {
  const [menuChatId, setMenuChatId] = React.useState(null);
  const [editChatId, setEditChatId] = React.useState(null);
  const [editChatName, setEditChatName] = React.useState("");
  const [search, setSearch] = React.useState("");
  const filteredChats = chats.filter((chat) =>
    chat.user.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <>
      {/* User info + New chat */}
      <div className="flex items-center gap-3 px-6 py-4">
        <img
          src={
            chats[0]?.avatar || "https://randomuser.me/api/portraits/men/32.jpg"
          }
          alt="avatar"
          className="w-9 h-9 rounded-full object-cover border"
        />
        <div>
          <div className="font-semibold text-black">ChatGPT</div>
          <div className="text-xs text-green-600">AI chat</div>
        </div>
        <button
          className="ml-auto bg-blue-100 text-blue-600 px-3 py-1 rounded-lg flex items-center gap-1 text-sm font-medium hover:bg-blue-200 transition"
          onClick={() => setShowNewChatForm(true)}
        >
          <Plus size={16} /> New chat
        </button>
      </div>
      {/* Tabs */}
      <div className="flex gap-2 px-6 mt-2 mb-2">
        <button
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition ${
            activeTab === "history"
              ? "bg-gray-100 text-black"
              : "text-gray-500 hover:bg-gray-50"
          }`}
          onClick={() => setActiveTab("history")}
        >
          <MessageSquare size={16} /> Chat History
        </button>
        <button
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition ${
            activeTab === "documents"
              ? "bg-gray-100 text-black"
              : "text-gray-500 hover:bg-gray-50"
          }`}
          onClick={() => setActiveTab("documents")}
        >
          <FileText size={16} /> Document Details
        </button>
      </div>
      {/* Nội dung theo tab */}
      <div className="flex-1 overflow-y-auto px-6 pb-4">
        {activeTab === "history" ? (
          <>
            <div className="text-xs text-gray-400 font-semibold mb-2 mt-2">
              Chat History
            </div>
            {/* Ô input tìm kiếm */}
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm kiếm đoạn hội thoại..."
              className="w-full mb-3 px-3 py-2 rounded-lg border border-gray-200 bg-gray-50 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <ul className="space-y-2">
              {filteredChats.map((chat) => (
                <li
                  key={chat.id}
                  className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition relative"
                >
                  <div className="flex-1">
                    {editChatId === chat.id ? (
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          setChats(
                            chats.map((c) =>
                              c.id === chat.id
                                ? { ...c, user: editChatName.trim() || c.user }
                                : c
                            )
                          );
                          setEditChatId(null);
                        }}
                        className="flex items-center gap-2"
                      >
                        <input
                          autoFocus
                          type="text"
                          value={editChatName}
                          onChange={(e) => setEditChatName(e.target.value)}
                          className="px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                        />
                        <button
                          type="submit"
                          className="text-blue-600 text-xs font-semibold"
                        >
                          Lưu
                        </button>
                      </form>
                    ) : (
                      <>
                        <div className="font-medium text-black text-sm">
                          {chat.user}
                        </div>
                        <div className="text-xs text-gray-500">{chat.type}</div>
                      </>
                    )}
                  </div>
                  <span
                    className="text-gray-400 cursor-pointer px-1 py-1 rounded hover:bg-gray-200 relative"
                    onClick={(e) => {
                      e.stopPropagation();
                      setMenuChatId(menuChatId === chat.id ? null : chat.id);
                    }}
                  >
                    <MoreVertical size={20} />
                    {menuChatId === chat.id && (
                      <ChatItemMenu
                        onRename={() => {
                          setEditChatId(chat.id);
                          setEditChatName(chat.user);
                          setMenuChatId(null);
                        }}
                        onDelete={() => {
                          setChats(chats.filter((c) => c.id !== chat.id));
                          setMenuChatId(null);
                        }}
                      />
                    )}
                  </span>
                </li>
              ))}
              {filteredChats.length === 0 && (
                <li className="text-gray-400 text-sm text-center py-4 select-none">
                  Không tìm thấy đoạn hội thoại nào.
                </li>
              )}
            </ul>
          </>
        ) : (
          <div className="text-gray-400 text-sm text-center py-4 select-none">
            Document Details (demo)
          </div>
        )}
      </div>
    </>
  );
};

// Dropdown menu cho từng chat item
const ChatItemMenu = ({ onRename, onDelete }) => {
  const menuRef = React.useRef();
  React.useEffect(() => {
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onRename && onRename(null);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onRename]);
  return (
    <div
      ref={menuRef}
      className="absolute right-0 top-7 w-28 bg-white rounded-lg shadow-lg border border-gray-100 z-30 animate-fade-in text-[15px]"
    >
      <ul className="py-1">
        <li
          className="flex items-center gap-2 px-3 py-1.5 text-gray-700 hover:bg-gray-50 cursor-pointer transition rounded"
          onClick={onRename}
        >
          <Pencil size={15} className="text-blue-500" />
          <span>Đổi tên</span>
        </li>
        <li
          className="flex items-center gap-2 px-3 py-1.5 text-red-600 hover:bg-red-50 cursor-pointer transition border-t border-gray-100 mt-1 rounded"
          onClick={onDelete}
        >
          <Trash2 size={15} className="text-red-500" />
          <span>Xóa</span>
        </li>
      </ul>
    </div>
  );
};

export default SidebarContent;
