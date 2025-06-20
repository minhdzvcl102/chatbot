import express from 'express';
import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';
import { getDb } from '../utilities/database.js'; // Lấy instance DB đã khởi tạo từ SQLite
import { logMessage } from '../utilities/logger.js';
import { configDotenv } from 'dotenv';
configDotenv(); // Tải biến môi trường từ file .env
import authenticateToken from '../middleware/auth.js';
import { log } from 'console';
const router = express.Router();

const JWT_SECRET = process.env.JWT_SECRET;
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '1h';

router.post('/register', async (req, res) => {
    try {
        const { email, password, confirmPass, username } = req.body;
        if (!email || !password || !confirmPass || password !== confirmPass) {
            logMessage("WRN", `Failed registration attempt for user: ${email || 'unknown'} - Invalid data`);
            return res.status(400).json({ message: 'Invalid registration data. Please provide email, password, and ensure passwords match.' });
        }
        const db = await getDb(); // Lấy database instance
        const existingUser = await db.get('SELECT * FROM users WHERE email = ?', [email]);
        if (existingUser) {
            logMessage("WRN", `User ${email} already exists`);
            return res.status(400).json({ message: 'User already exists' });
        }
        const hashedPassword = await bcrypt.hash(password, 10);
        const result = await db.run('INSERT INTO users (email,username, password) VALUES (?, ?,?)', [email, username, hashedPassword]);
        if (result.lastID) {
            logMessage("INF", `User ${email} registered successfully with ID: ${result.lastID}`);
            return res.status(201).json({ message: 'User registered successfully', userId: result.lastID });
        } else {
            logMessage("ERR", `Failed to insert user ${email} into database`);
            return res.status(500).json({ message: 'Failed to register user' });
        }

    } catch (error) {
        logMessage("ERR", `Error during registration: ${error.message}`, error.stack);
        res.status(500).json({ message: 'Internal server error' });
    }
});

router.post('/login', async (req, res) => {
    try {
        const { email, password } = req.body;
        const db = await getDb(); // Lấy database instance
        const user = await db.get('SELECT * FROM users WHERE email = ?', [email]);
        if (!user) {
            logMessage("WRN", `Login failed for non-existent user: ${email}`);
            return res.status(401).json({ message: 'Invalid email or password' });
        }
        const isPasswordValid = await bcrypt.compare(password, user.password);
        if (!isPasswordValid) {
            logMessage("WRN", `Login failed for user ${email} - Incorrect password`);
            return res.status(401).json({ message: 'Invalid email or password' });
        }
        const token = jwt.sign({ userId: user.id }, JWT_SECRET, { expiresIn: JWT_EXPIRES_IN });
        logMessage("INF", `User ${email} logged in successfully`);
        return res.status(200).json({ token, userId: user.id, message: 'Login successful' });
    } catch (error) {
        logMessage("ERR", `Error during login: ${error.message}`, error.stack);
        res.status(500).json({ message: 'Internal server error' });
    }
});
router.post('/logout', (req, res) => {
    // Xóa token khỏi client (thực tế không thể xóa token server-side)
    try {
        logMessage("INF", `User  logged out successfully`);
        res.status(200).json({ message: 'Logged out successfully' });
    }
    catch (error) {
        logMessage("ERR", `Error during logout: ${error.message}`, error.stack);
        res.status(500).json({ message: 'Internal server error' });
    }
});


export default router;