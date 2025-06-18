import sqlite3 from 'sqlite3';
import { open } from 'sqlite';
import path from 'path';
import { fileURLToPath } from 'url';
import { logMessage } from './logger.js';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DB_NAME = 'users';
const DB_PATH = path.join(__dirname, '../database/', DB_NAME + '.db');
let db = null;
async function initDb() {
    if (db) {
        logMessage("INF", "Database already initialized.");
        return db;
    }

    try {
        // Đảm bảo thư mục data tồn tại
        const dataDir = path.dirname(DB_PATH);
        if (!fs.existsSync(dataDir)) {
            fs.mkdirSync(dataDir, { recursive: true });
            logMessage("INF", `Created data directory: ${dataDir}`);
        }

        db = await open({
            filename: DB_PATH,
            driver: sqlite3.Database // Sử dụng driver sqlite3
        });

        await db.exec(`
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        `);
        // logMessage("INF", "Database 'users' table ensured.");
        return db;
    } catch (error) {
        logMessage("ERR", `Error initializing database: ${error.message}`, error.stack);
        throw error; // Ném lỗi để app.js có thể bắt
    }
}

async function getDb() {
    if (!db) {
        throw new Error("Database not initialized. Call initDb() first.");
    }
    return db;
}

export { initDb, getDb };