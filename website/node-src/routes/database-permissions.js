// database-permissions.js - API routes for managing database permissions

import express from 'express';
import { 
    getUserDatabasePermissions,
    grantDatabasePermission,
    revokeDatabasePermission,
    checkDatabaseAccess,
    logDatabaseAccess,
    getAvailableDatabases,
    getDb
} from '../utilities/database.js';
import { logMessage } from '../utilities/logger.js';

const router = express.Router();

// Middleware to check if user is authenticated and get user info
async function requireAuth(req, res, next) {
    try {
        const userId = req.session?.userId || req.headers['x-user-id'];
        if (!userId) {
            return res.status(401).json({ error: 'Authentication required' });
        }
        
        const db = await getDb();
        const user = await db.get('SELECT * FROM users WHERE id = ? AND is_active = 1', [userId]);
        if (!user) {
            return res.status(401).json({ error: 'User not found or inactive' });
        }
        
        req.user = user;
        next();
    } catch (error) {
        logMessage("ERR", `Auth middleware error: ${error.message}`);
        res.status(500).json({ error: 'Internal server error' });
    }
}

// Middleware to check if user is admin
function requireAdmin(req, res, next) {
    if (req.user.role !== 'admin') {
        return res.status(403).json({ error: 'Admin privileges required' });
    }
    next();
}

// GET /api/database-permissions/my-databases
// Get databases that current user has access to
router.get('/my-databases', requireAuth, async (req, res) => {
    try {
        const databases = await getAvailableDatabases(req.user.id);
        res.json({ databases });
    } catch (error) {
        logMessage("ERR", `Error getting user databases: ${error.message}`);
        res.status(500).json({ error: 'Failed to retrieve databases' });
    }
});

// GET /api/database-permissions/my-permissions
// Get detailed permissions for current user
router.get('/my-permissions', requireAuth, async (req, res) => {
    try {
        const permissions = await getUserDatabasePermissions(req.user.id);
        res.json({ permissions });
    } catch (error) {
        logMessage("ERR", `Error getting user permissions: ${error.message}`);
        res.status(500).json({ error: 'Failed to retrieve permissions' });
    }
});

// POST /api/database-permissions/check-access
// Check if user has access to specific database
router.post('/check-access', requireAuth, async (req, res) => {
    try {
        const { databaseName, requiredPermission = 'read' } = req.body;
        
        if (!databaseName) {
            return res.status(400).json({ error: 'Database name is required' });
        }
        
        const hasAccess = await checkDatabaseAccess(req.user.id, databaseName, requiredPermission);
        
        // Log the access check
        await logDatabaseAccess(
            req.user.id,
            databaseName,
            'access_check',
            null,
            hasAccess,
            hasAccess ? null : 'Access denied',
            req.ip,
            req.get('User-Agent')
        );
        
        res.json({ hasAccess, databaseName, requiredPermission });
    } catch (error) {
        logMessage("ERR", `Error checking database access: ${error.message}`);
        res.status(500).json({ error: 'Failed to check access' });
    }
});

// Admin-only routes
// GET /api/database-permissions/all-databases
// Get all available databases (admin only)
router.get('/all-databases', requireAuth, requireAdmin, async (req, res) => {
    try {
        const db = await getDb();
        const databases = await db.all(`
            SELECT 
                id,
                database_name,
                display_name,
                description,
                is_active,
                created_at,
                (SELECT COUNT(*) FROM user_database_permissions WHERE database_id = mysql_databases.id AND is_active = 1) as user_count
            FROM mysql_databases
            ORDER BY display_name
        `);
        
        res.json({ databases });
    } catch (error) {
        logMessage("ERR", `Error getting all databases: ${error.message}`);
        res.status(500).json({ error: 'Failed to retrieve databases' });
    }
});

// GET /api/database-permissions/users
// Get all users with their database permissions (admin only)
router.get('/users', requireAuth, requireAdmin, async (req, res) => {
    try {
        const db = await getDb();
        const users = await db.all(`
            SELECT 
                u.id,
                u.username,
                u.email,
                u.role,
                u.is_active,
                u.created_at,
                COUNT(udp.id) as permission_count
            FROM users u
            LEFT JOIN user_database_permissions udp ON u.id = udp.user_id AND udp.is_active = 1
            GROUP BY u.id
            ORDER BY u.username
        `);
        
        res.json({ users });
    } catch (error) {
        logMessage("ERR", `Error getting users: ${error.message}`);
        res.status(500).json({ error: 'Failed to retrieve users' });
    }
});

// GET /api/database-permissions/user/:userId
// Get specific user's database permissions (admin only)
router.get('/user/:userId', requireAuth, requireAdmin, async (req, res) => {
    try {
        const { userId } = req.params;
        const permissions = await getUserDatabasePermissions(userId);
        
        const db = await getDb();
        const user = await db.get(
            'SELECT id, username, email, role, is_active FROM users WHERE id = ?',
            [userId]
        );
        
        if (!user) {
            return res.status(404).json({ error: 'User not found' });
        }
        
        res.json({ user, permissions });
    } catch (error) {
        logMessage("ERR", `Error getting user permissions: ${error.message}`);
        res.status(500).json({ error: 'Failed to retrieve user permissions' });
    }
});

// POST /api/database-permissions/grant
// Grant database permission to user (admin only)
router.post('/grant', requireAuth, requireAdmin, async (req, res) => {
    try {
        const { userId, databaseName, permissionLevel = 'read', expiresAt } = req.body;
        
        if (!userId || !databaseName) {
            return res.status(400).json({ error: 'User ID and database name are required' });
        }
        
        const validPermissions = ['read', 'write', 'admin'];
        if (!validPermissions.includes(permissionLevel)) {
            return res.status(400).json({ error: 'Invalid permission level' });
        }
        
        await grantDatabasePermission(userId, databaseName, permissionLevel, req.user.id, expiresAt);
        
        // Log the permission grant
        await logDatabaseAccess(
            req.user.id,
            databaseName,
            'grant_permission',
            `Granted ${permissionLevel} to user ${userId}`,
            true,
            null,
            req.ip,
            req.get('User-Agent')
        );
        
        res.json({ 
            success: true, 
            message: `${permissionLevel} permission granted to user ${userId} for database ${databaseName}` 
        });
    } catch (error) {
        logMessage("ERR", `Error granting permission: ${error.message}`);
        res.status(500).json({ error: error.message });
    }
});

// POST /api/database-permissions/revoke
// Revoke database permission from user (admin only)
router.post('/revoke', requireAuth, requireAdmin, async (req, res) => {
    try {
        const { userId, databaseName } = req.body;
        
        if (!userId || !databaseName) {
            return res.status(400).json({ error: 'User ID and database name are required' });
        }
        
        await revokeDatabasePermission(userId, databaseName);
        
        // Log the permission revocation
        await logDatabaseAccess(
            req.user.id,
            databaseName,
            'revoke_permission',
            `Revoked permission from user ${userId}`,
            true,
            null,
            req.ip,
            req.get('User-Agent')
        );
        
        res.json({ 
            success: true, 
            message: `Permission revoked from user ${userId} for database ${databaseName}` 
        });
    } catch (error) {
        logMessage("ERR", `Error revoking permission: ${error.message}`);
        res.status(500).json({ error: error.message });
    }
});

// POST /api/database-permissions/add-database
// Add new MySQL database to the system (admin only)
router.post('/add-database', requireAuth, requireAdmin, async (req, res) => {
    try {
        const { databaseName, displayName, description } = req.body;
        
        if (!databaseName || !displayName) {
            return res.status(400).json({ error: 'Database name and display name are required' });
        }
        
        const db = await getDb();
        
        // Check if database already exists
        const existing = await db.get(
            'SELECT id FROM mysql_databases WHERE database_name = ?',
            [databaseName]
        );
        
        if (existing) {
            return res.status(409).json({ error: 'Database already exists' });
        }
        
        await db.run(
            'INSERT INTO mysql_databases (database_name, display_name, description) VALUES (?, ?, ?)',
            [databaseName, displayName, description || '']
        );
        
        logMessage("INF", `Admin ${req.user.username} added new database: ${databaseName}`);
        res.json({ success: true, message: 'Database added successfully' });
    } catch (error) {
        logMessage("ERR", `Error adding database: ${error.message}`);
        res.status(500).json({ error: 'Failed to add database' });
    }
});

// GET /api/database-permissions/audit-logs
// Get audit logs for database access (admin only)
router.get('/audit-logs', requireAuth, requireAdmin, async (req, res) => {
    try {
        const { page = 1, limit = 50, userId, databaseName, action } = req.query;
        const offset = (page - 1) * limit;
        
        let whereClause = 'WHERE 1=1';
        let params = [];
        
        if (userId) {
            whereClause += ' AND al.user_id = ?';
            params.push(userId);
        }
        
        if (databaseName) {
            whereClause += ' AND al.database_name = ?';
            params.push(databaseName);
        }
        
        if (action) {
            whereClause += ' AND al.action = ?';
            params.push(action);
        }
        
        const db = await getDb();
        const logs = await db.all(`
            SELECT 
                al.*,
                u.username
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            ${whereClause}
            ORDER BY al.created_at DESC
            LIMIT ? OFFSET ?
        `, [...params, limit, offset]);
        
        const totalCount = await db.get(`
            SELECT COUNT(*) as count
            FROM audit_logs al
            ${whereClause}
        `, params);
        
        res.json({ 
            logs, 
            pagination: {
                page: parseInt(page),
                limit: parseInt(limit),
                total: totalCount.count,
                pages: Math.ceil(totalCount.count / limit)
            }
        });
    } catch (error) {
        logMessage("ERR", `Error getting audit logs: ${error.message}`);
        res.status(500).json({ error: 'Failed to retrieve audit logs' });
    }
});

export default router;