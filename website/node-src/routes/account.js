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
        return res.json({ token, userId: user.id, username: user.username, userRole: user.role });
    } catch (error) {
        logMessage("ERR", `Error during login: ${error.message}`, error.stack);
        res.status(500).json({ message: 'Internal server error' });
    }
});

router.post('/logout', (req, res) => {
    // Xóa token khỏi client (thực tế không thể xóa token server-side)
    try {
        logMessage("INF", `User logged out successfully`);
        res.status(200).json({ message: 'Logged out successfully' });
    }
    catch (error) {
        logMessage("ERR", `Error during logout: ${error.message}`, error.stack);
        res.status(500).json({ message: 'Internal server error' });
    }
});

router.post('/createUser', authenticateToken, async (req, res) => {
    try {
        const { email, password, username, role } = req.body;
        if (!email || !password || !username) {
            logMessage("WRN", `Failed user creation attempt - Invalid data`);
            return res.status(400).json({ message: 'Invalid user data. Please provide email, password, and username.' });
        }

        const db = await getDb(); // Lấy database instance

        // FIX: Sử dụng req.user.userId thay vì localStorage
        const currentUser = await db.get('SELECT * FROM users WHERE id = ?', [req.user.userId]);

        if (!currentUser) {
            logMessage("WRN", `User creation failed - Current user not found`);
            return res.status(401).json({ message: 'Current user not found' });
        }

        const existingUser = await db.get('SELECT * FROM users WHERE email = ?', [email]);
        if (existingUser) {
            logMessage("WRN", `User ${email} already exists`);
            return res.status(400).json({ message: 'User already exists' });
        }

        // FIX: Sửa logic kiểm tra role (giả sử role = 0 là admin)
        if (currentUser.role === 0) { // Admin có thể tạo user
            const hashedPassword = await bcrypt.hash(password, 10);
            // FIX: Thêm hashedPassword vào parameters
            const result = await db.run('INSERT INTO users (email, username, password, role) VALUES (?, ?, ?, ?)', [email, username, hashedPassword, role]);

            if (result.lastID) {
                logMessage("INF", `User ${email} created successfully with ID: ${result.lastID}`);
                return res.status(201).json({ message: 'User created successfully', userId: result.lastID });
            } else {
                logMessage("ERR", `Failed to insert user ${email} into database`);
                return res.status(500).json({ message: 'Failed to create user' });
            }
        } else {
            logMessage("WRN", `User creation failed - Insufficient permissions for user ID: ${req.user.userId}`);
            return res.status(403).json({ message: 'Insufficient permissions to create user' });
        }

    } catch (error) {
        logMessage("ERR", `Error during user creation: ${error.message}`, error.stack);
        res.status(500).json({ message: 'Internal server error' });
    }
});

router.get('/getAllUsers/:id', authenticateToken, async (req, res) => {
    try {
        const db = await getDb(); // Lấy database instance
        const users = await db.all('SELECT id, email, username, role FROM users WHERE id != ?', [req.params.id]);
        logMessage("INF", `Retrieved ${users.length} users from the database`);
        return res.json(users);
    } catch (error) {
        logMessage("ERR", `Error retrieving users: ${error.message}`, error.stack);
        res.status(500).json({ message: 'Internal server error' });
    }
});

router.delete('/deleteUser/:id', authenticateToken, async (req, res) => {
    try {
        const userId = req.params.id;
        const db = await getDb(); // Lấy database instance
        const result = await db.run('DELETE FROM users WHERE id = ?', [userId]);
        if (result.changes > 0) {
            logMessage("INF", `User with ID ${userId} deleted successfully`);
            res.status(204).send();
        } else {
            logMessage("WRN", `Failed to delete user with ID ${userId} - User not found`);
            res.status(404).json({ message: 'User not found' });
        }
    } catch (error) {
        logMessage("ERR", `Error deleting user: ${error.message}`, error.stack);
        res.status(500).json({ message: 'Internal server error' });
    }
});

router.put('/updateUser/:id', authenticateToken, async (req, res) => {
    try {
        const userId = req.params.id;
        const { email, username, role } = req.body;
        if (!email || !username || role === undefined) {
            logMessage("WRN", `Failed to update user ${userId} - Invalid data`);
            return res.status(400).json({ message: 'Invalid user data. Please provide email, username, and role.' });
        }
        const db = await getDb(); // Lấy database instance
        const result = await db.run('UPDATE users SET email = ?, username = ?, role = ? WHERE id = ?', [email, username, role, userId]);
        if (result.changes > 0) {
            logMessage("INF", `User with ID ${userId} updated successfully`);
            res.status(200).json({ message: 'User updated successfully' });
        } else {
            logMessage("WRN", `Failed to update user with ID ${userId} - User not found`);
            res.status(404).json({ message: 'User not found' });
        }
    } catch (error) {
        logMessage("ERR", `Error updating user: ${error.message}`, error.stack);
        res.status(500).json({ message: 'Internal server error' });
    }
});

export default router;