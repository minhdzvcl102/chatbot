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
            driver: sqlite3.Database
        });

        // Create users table with role field
        await db.exec(`
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user' CHECK (role IN ('admin', 'user', 'viewer')),
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        `);

        // Create mysql_databases table to store available MySQL databases
        await db.exec(`
            CREATE TABLE IF NOT EXISTS mysql_databases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                database_name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        `);

        // Create user_database_permissions table for user-database access control
        await db.exec(`
            CREATE TABLE IF NOT EXISTS user_database_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                database_id INTEGER NOT NULL,
                permission_level TEXT DEFAULT 'read' CHECK (permission_level IN ('read', 'write', 'admin')),
                granted_by INTEGER,
                granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (database_id) REFERENCES mysql_databases(id) ON DELETE CASCADE,
                FOREIGN KEY (granted_by) REFERENCES users(id),
                UNIQUE(user_id, database_id)
            );
        `);

        // Create conversations table
        await db.exec(`
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userId INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                database_context TEXT, -- Store which MySQL database this conversation is about
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

        // Create uploaded_files table
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

        // Create audit_logs table for tracking database access
        await db.exec(`
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                database_name TEXT,
                action TEXT NOT NULL, -- 'query', 'schema_access', 'list_tables', etc.
                query_text TEXT,
                success INTEGER DEFAULT 1,
                error_message TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        `);

        // Run migrations
        // await migrateDatabase();

        // Create indexes for better performance
        // await createIndexes();

        // Insert default databases and admin user if not exists
        // await seedDefaultData();

        logMessage("INF", "Database tables initialized with user permission system.");
        return db;
    } catch (error) {
        logMessage("ERR", `Error initializing database: ${error.message}`, error.stack);
        throw error;
    }
}

// async function migrateDatabase() {
//     try {
//         // Check and add new columns to existing tables
        
//         // Add role column to users table if it doesn't exist
//         const userColumns = await db.all("PRAGMA table_info(users)");
//         if (!userColumns.some(col => col.name === 'role')) {
//             await db.exec('ALTER TABLE users ADD COLUMN role TEXT DEFAULT "user"');
//             logMessage("INF", "Added role column to users table");
//         }
        
//         if (!userColumns.some(col => col.name === 'is_active')) {
//             await db.exec('ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1');
//             logMessage("INF", "Added is_active column to users table");
//         }
        
//         if (!userColumns.some(col => col.name === 'updated_at')) {
//             await db.exec('ALTER TABLE users ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP');
//             logMessage("INF", "Added updated_at column to users table");
//         }

//         // Add database_context to conversations table if it doesn't exist
//         const conversationColumns = await db.all("PRAGMA table_info(conversations)");
//         if (!conversationColumns.some(col => col.name === 'database_context')) {
//             await db.exec('ALTER TABLE conversations ADD COLUMN database_context TEXT');
//             logMessage("INF", "Added database_context column to conversations table");
//         }

//         // Add hash column to uploaded_files if it doesn't exist
//         const fileColumns = await db.all("PRAGMA table_info(uploaded_files)");
//         if (!fileColumns.some(col => col.name === 'hash')) {
//             await db.exec('ALTER TABLE uploaded_files ADD COLUMN hash TEXT');
//             logMessage("INF", "Added hash column to uploaded_files table");
//         }

//     } catch (error) {
//         logMessage("ERR", `Error during database migration: ${error.message}`, error.stack);
//     }
// }

// async function createIndexes() {
//     try {
//         // Create indexes for better query performance
//         await db.exec('CREATE INDEX IF NOT EXISTS idx_user_database_permissions_user_id ON user_database_permissions(user_id)');
//         await db.exec('CREATE INDEX IF NOT EXISTS idx_user_database_permissions_database_id ON user_database_permissions(database_id)');
//         await db.exec('CREATE INDEX IF NOT EXISTS idx_user_database_permissions_active ON user_database_permissions(is_active)');
//         await db.exec('CREATE INDEX IF NOT EXISTS idx_conversations_database_context ON conversations(database_context)');
//         await db.exec('CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)');
//         await db.exec('CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)');
//         await db.exec('CREATE INDEX IF NOT EXISTS idx_uploaded_files_hash ON uploaded_files(hash)');
        
//         logMessage("INF", "Database indexes created successfully");
//     } catch (error) {
//         logMessage("ERR", `Error creating indexes: ${error.message}`, error.stack);
//     }
// }

// async function seedDefaultData() {
//     try {
//         // Insert default MySQL databases if not exists
//         const defaultDatabases = [
//             {
//                 database_name: 'example_db',
//                 display_name: 'Example Database',
//                 description: 'Sample database for testing and development'
//             },
//             {
//                 database_name: 'analytics_db',
//                 display_name: 'Analytics Database',
//                 description: 'Database containing analytics and reporting data'
//             },
//             {
//                 database_name: 'inventory_db',
//                 display_name: 'Inventory Management',
//                 description: 'Product inventory and warehouse management database'
//             }
//         ];

//         for (const dbInfo of defaultDatabases) {
//             const existing = await db.get(
//                 'SELECT id FROM mysql_databases WHERE database_name = ?',
//                 [dbInfo.database_name]
//             );
            
//             if (!existing) {
//                 await db.run(
//                     'INSERT INTO mysql_databases (database_name, display_name, description) VALUES (?, ?, ?)',
//                     [dbInfo.database_name, dbInfo.display_name, dbInfo.description]
//                 );
//                 logMessage("INF", `Added default database: ${dbInfo.database_name}`);
//             }
//         }

//         // Create default admin user if not exists
//         const adminUser = await db.get('SELECT id FROM users WHERE username = ?', ['admin']);
//         if (!adminUser) {
//             await db.run(
//                 'INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
//                 ['admin', 'admin@example.com', 'hashed_password_here', 'admin']
//             );
//             logMessage("INF", "Created default admin user");
//         }

//     } catch (error) {
//         logMessage("ERR", `Error seeding default data: ${error.message}`, error.stack);
//     }
// }

// User permission management functions
async function getUserDatabasePermissions(userId) {
    try {
        const permissions = await db.all(`
            SELECT 
                udp.id,
                udp.permission_level,
                udp.granted_at,
                udp.expires_at,
                md.database_name,
                md.display_name,
                md.description,
                grantor.username as granted_by_username
            FROM user_database_permissions udp
            JOIN mysql_databases md ON udp.database_id = md.id
            LEFT JOIN users grantor ON udp.granted_by = grantor.id
            WHERE udp.user_id = ? AND udp.is_active = 1 AND md.is_active = 1
            AND (udp.expires_at IS NULL OR udp.expires_at > datetime('now'))
        `, [userId]);
        
        return permissions;
    } catch (error) {
        logMessage("ERR", `Error getting user database permissions: ${error.message}`);
        throw error;
    }
}

async function grantDatabasePermission(userId, databaseName, permissionLevel = 'read', grantedBy = null, expiresAt = null) {
    try {
        // Get database ID
        const database = await db.get('SELECT id FROM mysql_databases WHERE database_name = ? AND is_active = 1', [databaseName]);
        if (!database) {
            throw new Error(`Database ${databaseName} not found`);
        }

        // Check if permission already exists
        const existing = await db.get(
            'SELECT id FROM user_database_permissions WHERE user_id = ? AND database_id = ?',
            [userId, database.id]
        );

        if (existing) {
            // Update existing permission
            await db.run(`
                UPDATE user_database_permissions 
                SET permission_level = ?, granted_by = ?, granted_at = datetime('now'), 
                    expires_at = ?, is_active = 1
                WHERE user_id = ? AND database_id = ?
            `, [permissionLevel, grantedBy, expiresAt, userId, database.id]);
        } else {
            // Insert new permission
            await db.run(`
                INSERT INTO user_database_permissions 
                (user_id, database_id, permission_level, granted_by, expires_at) 
                VALUES (?, ?, ?, ?, ?)
            `, [userId, database.id, permissionLevel, grantedBy, expiresAt]);
        }

        logMessage("INF", `Granted ${permissionLevel} permission to user ${userId} for database ${databaseName}`);
        return true;
    } catch (error) {
        logMessage("ERR", `Error granting database permission: ${error.message}`);
        throw error;
    }
}

async function revokeDatabasePermission(userId, databaseName) {
    try {
        const database = await db.get('SELECT id FROM mysql_databases WHERE database_name = ?', [databaseName]);
        if (!database) {
            throw new Error(`Database ${databaseName} not found`);
        }

        await db.run(
            'UPDATE user_database_permissions SET is_active = 0 WHERE user_id = ? AND database_id = ?',
            [userId, database.id]
        );

        logMessage("INF", `Revoked database permission for user ${userId} on database ${databaseName}`);
        return true;
    } catch (error) {
        logMessage("ERR", `Error revoking database permission: ${error.message}`);
        throw error;
    }
}

async function checkDatabaseAccess(userId, databaseName, requiredPermission = 'read') {
    try {
        const user = await db.get('SELECT role FROM users WHERE id = ? AND is_active = 1', [userId]);
        if (!user) {
            return false;
        }

        // Admin users have access to all databases
        if (user.role === 'admin') {
            return true;
        }

        const permission = await db.get(`
            SELECT permission_level 
            FROM user_database_permissions udp
            JOIN mysql_databases md ON udp.database_id = md.id
            WHERE udp.user_id = ? AND md.database_name = ? 
            AND udp.is_active = 1 AND md.is_active = 1
            AND (udp.expires_at IS NULL OR udp.expires_at > datetime('now'))
        `, [userId, databaseName]);

        if (!permission) {
            return false;
        }

        // Check permission level hierarchy: admin > write > read
        const permissionHierarchy = { 'read': 1, 'write': 2, 'admin': 3 };
        const userPermLevel = permissionHierarchy[permission.permission_level] || 0;
        const requiredLevel = permissionHierarchy[requiredPermission] || 0;

        return userPermLevel >= requiredLevel;
    } catch (error) {
        logMessage("ERR", `Error checking database access: ${error.message}`);
        return false;
    }
}

async function logDatabaseAccess(userId, databaseName, action, queryText = null, success = true, errorMessage = null, ipAddress = null, userAgent = null) {
    try {
        await db.run(`
            INSERT INTO audit_logs 
            (user_id, database_name, action, query_text, success, error_message, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        `, [userId, databaseName, action, queryText, success ? 1 : 0, errorMessage, ipAddress, userAgent]);
    } catch (error) {
        logMessage("ERR", `Error logging database access: ${error.message}`);
    }
}

async function getAvailableDatabases(userId) {
    try {
        const user = await db.get('SELECT role FROM users WHERE id = ? AND is_active = 1', [userId]);
        if (!user) {
            return [];
        }

        // Admin users see all active databases
        if (user.role === 'admin') {
            return await db.all(`
                SELECT database_name, display_name, description, 'admin' as permission_level
                FROM mysql_databases 
                WHERE is_active = 1
                ORDER BY display_name
            `);
        }

        // Regular users see only databases they have permission to access
        return await db.all(`
            SELECT 
                md.database_name, 
                md.display_name, 
                md.description,
                udp.permission_level
            FROM mysql_databases md
            JOIN user_database_permissions udp ON md.id = udp.database_id
            WHERE udp.user_id = ? AND udp.is_active = 1 AND md.is_active = 1
            AND (udp.expires_at IS NULL OR udp.expires_at > datetime('now'))
            ORDER BY md.display_name
        `, [userId]);
    } catch (error) {
        logMessage("ERR", `Error getting available databases: ${error.message}`);
        throw error;
    }
}

async function getDb() {
    if (!db) {
        throw new Error("Database not initialized. Call initDb() first.");
    }
    return db;
}

export { 
    initDb, 
    getDb,
    getUserDatabasePermissions,
    grantDatabasePermission,
    revokeDatabasePermission,
    checkDatabaseAccess,
    logDatabaseAccess,
    getAvailableDatabases
};