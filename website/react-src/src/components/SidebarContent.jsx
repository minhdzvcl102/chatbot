import React from "react";
import {
  Plus,
  MessageSquare,
  FileText,
  MoreVertical,
  Pencil,
  Trash2,
  Download,
} from "lucide-react";

const SidebarContent = ({
  conversations,
  setConversations,
  activeTab,
  setActiveTab,
  setShowNewChatForm,
  onUpdateConversation,
  onDeleteConversation,
  selectedConversationId,
  onSelectConversation,
  uploadedFiles,
  onDownloadFile,
  handleDeleteFile
}) => {
  const [menuChatId, setMenuChatId] = React.useState(null);
  const [editChatId, setEditChatId] = React.useState(null);
  const [editChatName, setEditChatName] = React.useState("");
  const [search, setSearch] = React.useState("");

  const filteredConversations = conversations.filter((conversation) =>
    conversation.user.toLowerCase().includes(search.toLowerCase())
  );

  const handleRenameSubmit = async (e, conversationId) => {
    e.preventDefault();
    const newTitle = editChatName.trim();
    if (
      newTitle &&
      newTitle !== conversations.find((c) => c.id === conversationId)?.user
    ) {
      await onUpdateConversation(conversationId, newTitle);
    }
    setEditChatId(null);
    setEditChatName("");
  };

  const handleDeleteConversation = async (conversationId) => {
    await onDeleteConversation(conversationId);
    setMenuChatId(null);
  };

  return (
    <>
      {/* User info + New chat */}
      <div className="flex items-center gap-3 px-6 py-4">
        <img
          src={
            conversations[0]?.avatar ||
            "https://randomuser.me/api/portraits/men/32.jpg"
          }
          alt="avatar"
          className="w-9 h-9 rounded-full object-cover border"
        />
        <div>
          <div className="font-semibold text-black">INDA</div>
          <div className="text-xs text-green-600">Data Analytic chat</div>
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

      {/* Content based on active tab */}
      <div className="flex-1 overflow-y-auto px-6 pb-4">
        {activeTab === "history" ? (
          <>
            <div className="text-xs text-gray-400 font-semibold mb-2 mt-2">
              Chat History
            </div>

            {/* Search input */}
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm kiếm đoạn hội thoại..."
              className="w-full mb-3 px-3 py-2 rounded-lg border border-gray-200 bg-gray-50 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />

            {/* Conversations list */}
            <ul className="space-y-2">
              {filteredConversations.map((conversation) => (
                <li
                  key={conversation.id}
                  className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition relative ${
                    selectedConversationId === conversation.id
                      ? "bg-blue-50 border border-blue-200"
                      : "bg-gray-50 hover:bg-gray-100"
                  }`}
                  onClick={() => onSelectConversation(conversation.id)}
                >
                  <div className="flex-1">
                    {editChatId === conversation.id ? (
                      <form
                        onSubmit={(e) => handleRenameSubmit(e, conversation.id)}
                        className="flex items-center gap-2"
                      >
                        <input
                          autoFocus
                          type="text"
                          value={editChatName}
                          onChange={(e) => setEditChatName(e.target.value)}
                          className="px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                          onClick={(e) => e.stopPropagation()}
                        />
                        <button
                          type="submit"
                          className="text-blue-600 text-xs font-semibold"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Lưu
                        </button>
                      </form>
                    ) : (
                      <>
                        <div className="font-medium text-black text-sm">
                          {conversation.user}
                        </div>
                        <div className="text-xs text-gray-500">
                          {conversation.type}
                        </div>
                      </>
                    )}
                  </div>
                  <span
                    className="text-gray-400 cursor-pointer px-1 py-1 rounded hover:bg-gray-200 relative"
                    onClick={(e) => {
                      e.stopPropagation();
                      setMenuChatId(
                        menuChatId === conversation.id ? null : conversation.id
                      );
                    }}
                  >
                    <MoreVertical size={20} />
                    {menuChatId === conversation.id && (
                      <ChatItemMenu
                        onRename={() => {
                          setEditChatId(conversation.id);
                          setEditChatName(conversation.user);
                          setMenuChatId(null);
                        }}
                        onDelete={() =>
                          handleDeleteConversation(conversation.id)
                        }
                      />
                    )}
                  </span>
                </li>
              ))}
              {filteredConversations.length === 0 && (
                <li className="text-gray-400 text-sm text-center py-4 select-none">
                  {search
                    ? "Không tìm thấy đoạn hội thoại nào."
                    : "Không có đoạn hội thoại nào."}
                </li>
              )}
            </ul>
          </>
        ) : (
          <>
            <div className="text-xs text-gray-400 font-semibold mb-2 mt-2">
              Tài liệu đã upload ({uploadedFiles.length})
            </div>
            {uploadedFiles.length === 0 ? (
              <div className="text-sm text-gray-400 text-center py-4 select-none">
                Không có tài liệu nào.
              </div>
            ) : (
              <ul className="space-y-2">
                {uploadedFiles.map((file) => (
                  <li
                    key={file.id}
                    className="flex items-center gap-3 p-3 rounded-lg bg-white border border-gray-200 justify-between"
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <FileText
                        size={16}
                        className="text-blue-600 flex-shrink-0"
                      />
                      <div className="min-w-0">
                        <div className="font-medium text-gray-900 truncate">
                          {file.originalName}
                        </div>
                        <div className="text-xs text-gray-500">
                          {(file.fileSize / (1024 * 1024)).toFixed(2)} MB
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => onDownloadFile(file)}
                        className="p-1 text-gray-400 hover:text-blue-600 transition"
                        title="Tải xuống"
                      >
                        <Download size={16} />
                      </button>
                      <button
                        onClick={() => handleDeleteFile(file.id)}
                        className="p-1 text-gray-400 hover:text-red-600 transition"
                        title="Xóa file"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </>
  );
};

// Dropdown menu for each chat item
const ChatItemMenu = ({ onRename, onDelete }) => {
  const menuRef = React.useRef();

  React.useEffect(() => {
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        // Close menu when clicking outside
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div
      ref={menuRef}
      className="absolute right-0 top-7 w-28 bg-white rounded-lg shadow-lg border border-gray-100 z-30 animate-fade-in text-[15px]"
    >
      <ul className="py-1">
        <li
          className="flex items-center gap-2 px-3 py-1.5 text-gray-700 hover:bg-gray-50 cursor-pointer transition rounded"
          onClick={(e) => {
            e.stopPropagation();
            onRename();
          }}
        >
          <Pencil size={15} className="text-blue-500" />
          <span>Đổi tên</span>
        </li>
        <li
          className="flex items-center gap-2 px-3 py-1.5 text-red-600 hover:bg-red-50 cursor-pointer transition border-t border-gray-100 mt-1 rounded"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          <Trash2 size={15} className="text-red-500" />
          <span>Xóa</span>
        </li>
      </ul>
    </div>
  );
};

export default SidebarContent;
