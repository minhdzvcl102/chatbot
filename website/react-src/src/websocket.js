import { useEffect, useRef } from "react";

const useWebSocket = (url, selectedChatId, setChats) => {
  const ws = useRef(null);

  useEffect(() => {
    // Khởi tạo kết nối WebSocket
    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      console.log("WebSocket connected!");
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("Received from server:", data);

        // Cập nhật messages cho chat hiện tại
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
        setChats((prevChats) =>
          prevChats.map((chat) =>
            chat.id === selectedChatId
              ? {
                  ...chat,
                  messages: [
                    ...chat.messages,
                    {
                      id: Date.now(),
                      type: "system",
                      text: `Received unparseable message: ${event.data}`,
                      sender: "system",
                      time: new Date().toLocaleTimeString(),
                    },
                  ],
                }
              : chat
          )
        );
      }
    };

    ws.current.onclose = () => {
      console.log("WebSocket disconnected");
      setChats((prevChats) =>
        prevChats.map((chat) =>
          chat.id === selectedChatId
            ? {
                ...chat,
                messages: [
                  ...chat.messages,
                  {
                    id: Date.now(),
                    type: "system",
                    text: "Disconnected from chatbot.",
                    sender: "system",
                    time: new Date().toLocaleTimeString(),
                  },
                ],
              }
            : chat
        )
      );
    };

    ws.current.onerror = (error) => {
      console.error("WebSocket error:", error);
      setChats((prevChats) =>
        prevChats.map((chat) =>
          chat.id === selectedChatId
            ? {
                ...chat,
                messages: [
                  ...chat.messages,
                  {
                    id: Date.now(),
                    type: "system",
                    text: "WebSocket error occurred.",
                    sender: "system",
                    time: new Date().toLocaleTimeString(),
                  },
                ],
              }
            : chat
        )
      );
    };

    // Hàm cleanup: đóng kết nối khi component unmount hoặc dependencies thay đổi
    return () => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        ws.current.close();
      }
    };
  }, [url, selectedChatId, setChats]); // Dependencies: reconnect nếu url hoặc chat được chọn thay đổi

  // Trả về instance của WebSocket để component cha có thể sử dụng
};

export default useWebSocket;