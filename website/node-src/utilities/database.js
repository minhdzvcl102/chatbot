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
        // Ensure the data directory exists
        const dataDir = path.dirname(DB_PATH);
        if (!fs.existsSync(dataDir)) {
            fs.mkdirSync(dataDir, { recursive: true });
            logMessage("INF", `Created data directory: ${dataDir}`);
        }

        db = await open({
            filename: DB_PATH,
            driver: sqlite3.Database // Use sqlite3 driver
        });

        // Create users table
        await db.exec(`
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        `);

        // Create conversations table
        await db.exec(`
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userId INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE
            );
        `);

        // Create messages table
        await db.exec(`
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversationId INTEGER NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversationId) REFERENCES conversations(id) ON DELETE CASCADE
            );
        `);

        // Create uploaded_files table with hash column
        await db.exec(`
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversationId INTEGER NOT NULL,
                fileName TEXT NOT NULL,
                originalName TEXT NOT NULL,
                fileSize INTEGER NOT NULL,
                mimeType TEXT NOT NULL,
                hash TEXT,
                uploadedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversationId) REFERENCES conversations(id) ON DELETE CASCADE
            );
        `);

        // Migration: Add hash column if it doesn't exist (for existing databases)
        await migrateDatabase();

        // Create index for hash column for better performance
        await db.exec('CREATE INDEX IF NOT EXISTS idx_uploaded_files_hash ON uploaded_files(hash)');

        logMessage("INF", "Database tables 'users', 'conversations', 'messages', and 'uploaded_files' ensured.");
        return db;
    } catch (error) {
        logMessage("ERR", `Error initializing database: ${error.message}`, error.stack);
        throw error; // Throw error to be caught by app.js
    }
}

async function migrateDatabase() {
    try {
        // Check if hash column exists
        const columns = await db.all("PRAGMA table_info(uploaded_files)");
        const hasHashColumn = columns.some(col => col.name === 'hash');
        
        if (!hasHashColumn) {
            // Add hash column to existing table
            await db.exec('ALTER TABLE uploaded_files ADD COLUMN hash TEXT');
            logMessage("INF", "Added hash column to existing uploaded_files table");
            
            // Optionally: Calculate hash for existing files if needed
            await backfillHashForExistingFiles();
        } else {
            logMessage("INF", "Hash column already exists in uploaded_files table");
        }
        
    } catch (error) {
        logMessage("ERR", `Error during database migration: ${error.message}`, error.stack);
        // Don't throw error here, let the app continue
    }
}

async function backfillHashForExistingFiles() {
    try {
        // Get all files without hash
        const filesWithoutHash = await db.all('SELECT * FROM uploaded_files WHERE hash IS NULL');
        
        if (filesWithoutHash.length === 0) {
            logMessage("INF", "No files need hash backfill");
            return;
        }

        logMessage("INF", `Found ${filesWithoutHash.length} existing files without hash - keeping them as NULL`);
        
    } catch (error) {
        logMessage("ERR", `Error during hash backfill: ${error.message}`, error.stack);
    }
}

async function getDb() {
    if (!db) {
        throw new Error("Database not initialized. Call initDb() first.");
    }
    return db;
}

export { initDb, getDb };