const express = require('express');
const { logMessage, setLogMode } = require("./utilities/logger"); // Bỏ .js ở đây nếu utilities/logger là CommonJS
const bodyParserErrorHandler = require('express-body-parser-error-handler');
const http = require("http");
const cookieParser = require('cookie-parser');
const cors = require('cors');
const WebSocket = require('ws');
require("dotenv").config();
const {initDb, getDb} = require("./utilities/database");

const { chatRoutes } = require("./routes/chat");
const { accountRoutes } = require('./routes/account');
const setupWebSocketChat = require('./websocket_chat');

setLogMode("CONSOLE+FILE");

const app = express();
const server = http.createServer(app);

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(cors());
app.use(bodyParserErrorHandler());

// Khởi tạo cơ sở dữ liệu SQLite
initDb().then(() => {
    logMessage("INF", "SQLite database initialized successfully.");
}).catch(err => {
    logMessage("FTL", "Failed to initialize SQLite database:", err.message);
    process.exit(1); // Thoát nếu không thể kết nối DB
});

// // Routes
// app.use("/account", accountRoutes);
// app.use("/chat", chatRoutes);

// Setup WebSocket server
// const wss = setupWebSocketChat(server);

server.listen(process.env.PORT || 3000, () => {
    logMessage("INF", `Node.js Server is running on port ${process.env.PORT || 3000}`);
});

process.on('unhandledRejection', (reason, promise) => {
    logMessage("ERR", `Unhandled Rejection at: ${promise}, reason: ${reason}`);
});

process.on('uncaughtException', (error) => {
    logMessage("ERR", `Uncaught Exception: ${error.message}`, error.stack);
    process.exit(1);
});