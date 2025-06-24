import express from 'express';
import { logMessage, setLogMode } from './utilities/logger.js';
import bodyParserErrorHandler from 'express-body-parser-error-handler';
import http from 'http';
import cookieParser from 'cookie-parser';
import cors from 'cors';
import dotenv from 'dotenv';
import WebSocketHandler from './socket/webSocket.js';
import { initDb } from './utilities/database.js';
import accountRoutes from './routes/account.js';
import chatRoutes from './routes/chat.js';

dotenv.config();
setLogMode('CONSOLE+FILE');

const app = express();
const server = http.createServer(app);
const wsHandler = new WebSocketHandler(server);

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(cors());
app.use(bodyParserErrorHandler());

// Khởi tạo cơ sở dữ liệu SQLite
initDb().then(() => {
    logMessage('INF', 'SQLite database initialized successfully.');
}).catch(err => {
    logMessage('FTL', `Failed to initialize SQLite database: ${err.message}`);
    process.exit(1);
});

// Routes
app.get('/', (req, res) => {
    res.send('Welcome to the Node.js backend!');
});
app.use('/account', accountRoutes);
app.use('/chat', chatRoutes);

server.listen(process.env.PORT || 3000, () => {
    logMessage('INF', `Node.js Server is running on port ${process.env.PORT || 3000}`, `http://localhost:${process.env.PORT || 3000}`);
});

process.on('unhandledRejection', (reason, promise) => {
    logMessage('ERR', `Unhandled Rejection at: ${promise}, reason: ${reason}`);
});

process.on('uncaughtException', (error) => {
    logMessage('ERR', `Uncaught Exception: ${error.message}`, error.stack);
    process.exit(1);
});