import { useEffect, useRef } from "react";

const useWebSocket = (url, selectedChatId, setChats) => {
  const ws = useRef(null); // Đây là đối tượng ref

  useEffect(() => {
    const authToken = localStorage.getItem('authToken');
    const wsUrlWithToken = authToken ? `${url}?token=${authToken}` : url;

    // Khởi tạo kết nối WebSocket
    ws.current = new WebSocket(wsUrlWithToken);

    ws.current.onopen = () => {
      console.log("WebSocket connected!");
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // ... (logic xử lý tin nhắn)
        setChats((prevChats) =>
          prevChats.map((chat) =>
            chat.id === selectedChatId
              ? {
                  ...chat,
                  messages: [
                    ...chat.messages,
                    {
                      id: Date.now(),
                      type: data.type === "user_message" ? "user" : "bot",
                      text: data.content,
                      sender: data.type === "user_message" ? "user" : "AI",
                      time: new Date().toLocaleTimeString(),
                    },
                  ],
                }
              : chat
          )
        );
      } catch (error) {
        console.error("Failed to parse message from server:", error);
        // ... (logic xử lý lỗi)
      }
    };

    ws.current.onclose = () => {
      console.log("WebSocket disconnected");
      
    };

    ws.current.onerror = (error) => {
      console.error("WebSocket error:", error);
      // ... (logic xử lý lỗi)
    };

    // Hàm cleanup: đóng kết nối khi component unmount hoặc dependencies thay đổi
    return () => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        ws.current.close();
      }
    };
  }, [url, selectedChatId, setChats]);

  return ws; // <-- Đảm bảo bạn trả về đối tượng ref (ws)
};

export default useWebSocket;