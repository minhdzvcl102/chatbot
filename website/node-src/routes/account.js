import express from 'express';
import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';
import { getDb } from '../utilities/database.js'; // Lấy instance DB đã khởi tạo từ SQLite
import { logMessage } from '../utilities/logger.js';

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



export default router;