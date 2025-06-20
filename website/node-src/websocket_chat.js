// websocket_chat.js
import { WebSocketServer } from 'ws'; // Đảm bảo bạn đã import WebSocketServer đúng cách

// Bọc logic khởi tạo server trong một hàm và export nó
const setupWebSocketChat = () => {
    const wss = new WebSocketServer({ port: 8080 }); // Khởi tạo server trên cổng 8080

    console.log('WebSocket server started on port 8080');

    wss.on('connection', function connection(ws) {
        console.log('A new client connected!');
        ws.on('message', function incoming(message) {
            const receivedMessage = message.toString();
            console.log('Received from client: %s', receivedMessage);

            // Giả lập phản hồi từ AI
            setTimeout(() => {
                let aiResponse = `AI says: You said "${receivedMessage}". Thinking...`;
                try {
                    const parsedMessage = JSON.parse(receivedMessage);
                    if (parsedMessage.type === 'user_message' && parsedMessage.content) {
                        aiResponse = `AI received: "${parsedMessage.content}". This is a simulated AI response.`;
                    }
                } catch (e) {
                    // Not JSON
                }
                ws.send(JSON.stringify({ type: 'ai_response', content: aiResponse }));
            }, 1000);
        });
        ws.on('close', () => console.log('Client disconnected'));
        ws.on('error', (err) => console.error('WebSocket error:', err));
        ws.send(JSON.stringify({ type: 'system_message', content: 'Welcome to the chatbot!' }));
    });
};

// Export hàm này dưới dạng default export
export default setupWebSocketChat; // <-- Thêm dòng này