// nodejs-backend/src/routes/chat.js
const express = require('express');
const router = express.Router();
const { logMessage } = require('../utilities/logger');
const multer = require('multer'); // Để xử lý file upload
const { initDb, getDb } = require('../utilities/database');

router.post('/login', async (req, res) => {
    try {
        const { email, password } = req.body;
        logMessage("INF", `Login attempt for user: ${email}`);
        // Giả lập kiểm tra đăng nhập
        if (username === 'admin' && password === 'password') {
            logMessage("INF", `User ${username} logged in successfully`);
            res.status(200).json({ message: 'Login successful' });
        } else {
            logMessage("WRN", `Failed login attempt for user: ${email}`);
            res.status(401).json({ message: 'Invalid credentials' });
        }
    } catch (error) {
        logMessage("ERR", `Error during login: ${error.message}`, error.stack);
        res.status(500).json({ message: 'Internal server error' });
    }
});