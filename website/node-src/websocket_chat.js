// websocket_chat.js
import { WebSocketServer } from 'ws';
import axios from 'axios';
import 'dotenv/config'; // <-- Đảm bảo tải biến môi trường nếu dùng file .env cho Node.js

const setupWebSocketChat = () => {
    const wss = new WebSocketServer({ port: 8080 });
    console.log('WebSocket server started on port 8080');

    wss.on('connection', function connection(ws) {
        console.log('A new client connected!');

        // Hàm xử lý tin nhắn đến từ client
        ws.on('message', async function incoming(message) { // <-- Đảm bảo có 'async' ở đây
            const receivedMessage = message.toString();
            console.log('Received from client: %s', receivedMessage);

            let aiResponseContent = "Đã xảy ra lỗi không xác định khi xử lý tin nhắn."; // Giá trị mặc định

            try {
                const parsedMessage = JSON.parse(receivedMessage);

                // Giả định tin nhắn từ client có dạng { type: 'user_message', content: '...' }
                if (parsedMessage.type === 'user_message' && parsedMessage.content) {
                    console.log(`Đang gửi yêu cầu đến Python AI: ${parsedMessage.content}`);

                    // Gọi API Python và chờ phản hồi
                    const pythonServiceURL = `${process.env.PYTHON_SERVICE_URL}/data/process`; // Hoặc /process/data tùy thuộc vào Flask

                    const pythonResponse = await axios.post(pythonServiceURL, {
                        user_query: parsedMessage.content // Đảm bảo key là 'user_query'
                    });

                    // Xử lý phản hồi từ Python
                    if (pythonResponse.data && pythonResponse.data.ai_response) {
                        aiResponseContent = pythonResponse.data.ai_response;
                    } else {
                        aiResponseContent = `Dịch vụ AI trả về định dạng không mong muốn: ${JSON.stringify(pythonResponse.data)}`;
                    }
                } else {
                    aiResponseContent = "Đã nhận được tin nhắn không đúng định dạng hoặc thiếu nội dung.";
                }

            } catch (error) {
                console.error('LỖI XỬ LÝ TRÊN WEBSOCKET SERVER:', error);
                if (error.response) {
                    // Lỗi từ server Python (status code 4xx, 5xx)
                    aiResponseContent = `Lỗi từ AI Service (HTTP Status: ${error.response.status}): ${JSON.stringify(error.response.data)}`;
                } else if (error.request) {
                    // Không có phản hồi từ server (ví dụ: server Flask chưa chạy, lỗi mạng, CORS)
                    aiResponseContent = "Không nhận được phản hồi từ AI Service. Có thể server Python chưa chạy hoặc lỗi mạng/CORS.";
                } else {
                    // Lỗi khác trong quá trình chuẩn bị request
                    aiResponseContent = `Lỗi khi gửi yêu cầu đến AI Service: ${error.message}`;
                }
            } finally {
                // Dù có lỗi hay không, luôn cố gắng gửi phản hồi về client
                // để client biết điều gì đã xảy ra thay vì bị ngắt kết nối đột ngột.
                try {
                    ws.send(JSON.stringify({ type: 'ai_response', content: aiResponseContent }));
                } catch (sendError) {
                    console.error("Lỗi khi gửi phản hồi về client:", sendError);
                }
            }
        });

        ws.on('close', () => console.log('Client disconnected'));
        ws.on('error', (err) => console.error('WebSocket error:', err));
        ws.send(JSON.stringify({ type: 'system_message', content: 'Chào mừng bạn đến với chatbot!' }));
    });
};

export default setupWebSocketChat;