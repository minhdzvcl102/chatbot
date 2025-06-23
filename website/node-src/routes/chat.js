import express from 'express';
import multer from 'multer';
import * as Minio from 'minio';
import { getDb } from '../utilities/database.js';
import { logMessage } from '../utilities/logger.js';
import authenticateToken from '../middleware/auth.js';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { promises as fs } from 'fs';
import crypto from "crypto";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const router = express.Router();

// Initialize MinIO client
const minioClient = new Minio.Client({
    endPoint: process.env.MINIO_ENDPOINT || 'localhost',
    port: parseInt(process.env.MINIO_PORT) || 9000,
    useSSL: process.env.MINIO_USE_SSL === 'true',
    accessKey: process.env.MINIO_ACCESS_KEY || 'minioadmin',
    secretKey: process.env.MINIO_SECRET_KEY || 'minioadmin'
});

const bucketName = process.env.MINIO_BUCKET || 'chat-files';

// Ensure bucket exists
(async () => {
    try {
        logMessage("INF", `🔍 Checking if MinIO bucket "${bucketName}" exists...`);
        const bucketExists = await minioClient.bucketExists(bucketName);

        if (!bucketExists) {
            await minioClient.makeBucket(bucketName);
            logMessage("INF", `✅ Created MinIO bucket: ${bucketName}`);
        } else {
            logMessage("INF", `✅ MinIO bucket "${bucketName}" already exists.`);
        }
    } catch (error) {
        logMessage("ERR", `❌ MinIO bucket setup error: ${error.message}`);
    }
})();

// Configure multer for file upload
const upload = multer({
    storage: multer.memoryStorage(),
    limits: {
        fileSize: 20 * 1024 * 1024, // 20MB limit
    },
    fileFilter: (req, file, cb) => {
        // Allow only PDF files
        if (file.mimetype === 'application/pdf') {
            cb(null, true);
        } else {
            cb(new Error('Only PDF files are allowed'), false);
        }
    }
});

// Serve file from MinIO
router.get('/files/:fileName', async (req, res) => {
    try {
        const fileName = req.params.fileName;

        // Get file from MinIO
        const fileStream = await minioClient.getObject(bucketName, fileName);

        // Get file metadata
        const stat = await minioClient.statObject(bucketName, fileName);

        // Set headers
        res.setHeader('Content-Type', stat.metaData['content-type'] || 'application/octet-stream');
        res.setHeader('Content-Length', stat.size);
        res.setHeader('Content-Disposition', `inline; filename="${stat.metaData['original-name'] || fileName}"`);

        // Pipe file stream to response
        fileStream.pipe(res);

    } catch (error) {
        logMessage("ERR", `Error serving file ${req.params.fileName}: ${error.message}`);
        return res.status(404).json({ message: 'File not found' });
    }
});

// Load all conversations for a user
router.get('/conversations', authenticateToken, async (req, res) => {
    try {
        const userId = req.user.userId;
        const db = await getDb();
        const conversations = await db.all('SELECT * FROM conversations WHERE userId = ? ORDER BY createdAt DESC', [userId]);

        logMessage("INF", `Loaded ${conversations.length} conversations for user ${userId}`);
        return res.status(200).json({ conversations });
    } catch (error) {
        logMessage("ERR", `Error loading conversations for user ${userId}: ${error.message}`, error.stack);
        return res.status(500).json({ message: 'Internal server error' });
    }
});

// Create a new conversation
router.post('/conversations', authenticateToken, async (req, res) => {
    try {
        const userId = req.user.userId;
        const { title, content } = req.body;

        // Chỉ kiểm tra title, content có thể trống
        if (!title) {
            logMessage("WRN", `Invalid conversation data for user ${userId}`);
            return res.status(400).json({ message: 'Title is required' });
        }

        // Đặt content mặc định nếu không có
        const conversationContent = content || "[]";

        const db = await getDb();
        const result = await db.run(
            'INSERT INTO conversations (userId, title, content, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?)',
            [userId, title, conversationContent, new Date().toISOString(), new Date().toISOString()]
        );

        if (result.lastID) {
            logMessage("INF", `Conversation ${result.lastID} created for user ${userId}`);
            return res.status(201).json({ message: 'Conversation created successfully', conversationId: result.lastID });
        } else {
            logMessage("ERR", `Failed to create conversation for user ${userId}`);
            return res.status(500).json({ message: 'Failed to create conversation' });
        }
    } catch (error) {
        logMessage("ERR", `Error creating conversation for user ${userId}: ${error.message}`, error.stack);
        return res.status(500).json({ message: 'Internal server error' });
    }
});

router.put('/conversations/:id', authenticateToken, async (req, res) => {
    try {
        const userId = req.user.userId;
        const conversationId = req.params.id;
        const { title } = req.body;

        if (!title) {
            logMessage("WRN", `Invalid title for conversation ${conversationId} update by user ${userId}`);
            return res.status(400).json({ message: 'Title is required' });
        }

        const db = await getDb();
        const conversation = await db.get('SELECT * FROM conversations WHERE id = ? AND userId = ?', [conversationId, userId]);

        if (!conversation) {
            logMessage("WRN", `Conversation ${conversationId} not found or not owned by user ${userId}`);
            return res.status(404).json({ message: 'Conversation not found or unauthorized' });
        }

        const result = await db.run(
            'UPDATE conversations SET title = ?, updatedAt = ? WHERE id = ? AND userId = ?',
            [title, new Date().toISOString(), conversationId, userId]
        );

        if (result.changes > 0) {
            logMessage("INF", `Conversation ${conversationId} title updated by user ${userId}`);
            return res.status(200).json({ message: 'Conversation title updated successfully' });
        } else {
            logMessage("ERR", `Failed to update conversation ${conversationId} for user ${userId}`);
            return res.status(500).json({ message: 'Failed to update conversation' });
        }
    } catch (error) {
        logMessage("ERR", `Error updating conversation ${req.params.id} for user ${userId}: ${error.message}`, error.stack);
        return res.status(500).json({ message: 'Internal server error' });
    }
});

// Delete a conversation
router.delete('/conversations/:id', authenticateToken, async (req, res) => {
    try {
        const userId = req.user.userId;
        const conversationId = req.params.id;

        const db = await getDb();
        const conversation = await db.get('SELECT * FROM conversations WHERE id = ? AND userId = ?', [conversationId, userId]);

        if (!conversation) {
            logMessage("WRN", `Conversation ${conversationId} not found or not owned by user ${userId}`);
            return res.status(404).json({ message: 'Conversation not found or unauthorized' });
        }

        const result = await db.run('DELETE FROM conversations WHERE id = ? AND userId = ?', [conversationId, userId]);

        if (result.changes > 0) {
            logMessage("INF", `Conversation ${conversationId} deleted by user ${userId}`);
            return res.status(200).json({ message: 'Conversation deleted successfully' });
        } else {
            logMessage("ERR", `Failed to delete conversation ${conversationId} for user ${userId}`);
            return res.status(500).json({ message: 'Failed to delete conversation' });
        }
    } catch (error) {
        logMessage("ERR", `Error deleting conversation ${req.params.id} for user ${userId}: ${error.message}`, error.stack);
        return res.status(500).json({ message: 'Internal server error' });
    }
});

// ================== MESSAGE ROUTES ==================

// Get all messages for a conversation
router.get('/conversations/:id/messages', authenticateToken, async (req, res) => {
    try {
        const userId = req.user.userId;
        const conversationId = req.params.id;

        const db = await getDb();

        // Verify conversation ownership
        const conversation = await db.get('SELECT * FROM conversations WHERE id = ? AND userId = ?', [conversationId, userId]);
        if (!conversation) {
            logMessage("WRN", `Conversation ${conversationId} not found or not owned by user ${userId}`);
            return res.status(404).json({ message: 'Conversation not found or unauthorized' });
        }

        // Get all messages for this conversation
        const messages = await db.all(
            'SELECT * FROM messages WHERE conversationId = ? ORDER BY createdAt ASC',
            [conversationId]
        );

        logMessage("INF", `Loaded ${messages.length} messages for conversation ${conversationId} by user ${userId}`);
        return res.status(200).json({ messages });
    } catch (error) {
        logMessage("ERR", `Error loading messages for conversation ${req.params.id}: ${error.message}`, error.stack);
        return res.status(500).json({ message: 'Internal server error' });
    }
});

// Send a new message to a conversation
router.post('/conversations/:id/messages', authenticateToken, async (req, res) => {
    try {
        const userId = req.user.userId;
        const conversationId = req.params.id;
        const { content, role = 'user' } = req.body;

        if (!content || content.trim() === '') {
            logMessage("WRN", `Empty message content for conversation ${conversationId} by user ${userId}`);
            return res.status(400).json({ message: 'Message content is required' });
        }

        if (!['user', 'assistant'].includes(role)) {
            logMessage("WRN", `Invalid role ${role} for conversation ${conversationId} by user ${userId}`);
            return res.status(400).json({ message: 'Role must be either "user" or "assistant"' });
        }

        const db = await getDb();

        // Verify conversation ownership
        const conversation = await db.get('SELECT * FROM conversations WHERE id = ? AND userId = ?', [conversationId, userId]);
        if (!conversation) {
            logMessage("WRN", `Conversation ${conversationId} not found or not owned by user ${userId}`);
            return res.status(404).json({ message: 'Conversation not found or unauthorized' });
        }

        // Insert the message
        const messageResult = await db.run(
            'INSERT INTO messages (conversationId, role, content, createdAt) VALUES (?, ?, ?, ?)',
            [conversationId, role, content.trim(), new Date().toISOString()]
        );

        if (!messageResult.lastID) {
            logMessage("ERR", `Failed to save message for conversation ${conversationId}`);
            return res.status(500).json({ message: 'Failed to save message' });
        }

        // Update conversation's updatedAt timestamp
        await db.run(
            'UPDATE conversations SET updatedAt = ? WHERE id = ?',
            [new Date().toISOString(), conversationId]
        );

        // Get the saved message
        const savedMessage = await db.get('SELECT * FROM messages WHERE id = ?', [messageResult.lastID]);

        logMessage("INF", `Message saved to conversation ${conversationId} by user ${userId}`);

        return res.status(201).json({
            message: 'Message sent successfully',
            savedMessage: savedMessage
        });

    } catch (error) {
        logMessage("ERR", `Error sending message to conversation ${req.params.id}: ${error.message}`, error.stack);
        return res.status(500).json({ message: 'Internal server error' });
    }
});

// ================== FILE UPLOAD ROUTES ==================

// Upload file to conversation
function calculateBufferHash(buffer) {
    return crypto.createHash('sha256').update(buffer).digest('hex');
}

router.post('/conversations/:id/upload', authenticateToken, upload.single('file'), async (req, res) => {
    try {
        const userId = req.user.userId;
        const conversationId = req.params.id;
        const file = req.file;

        if (!file) {
            logMessage("WRN", `No file provided for upload to conversation ${conversationId} by user ${userId}`);
            return res.status(400).json({ message: 'No file provided' });
        }

        const db = await getDb();

        // Verify conversation ownership
        const conversation = await db.get('SELECT * FROM conversations WHERE id = ? AND userId = ?', [conversationId, userId]);
        if (!conversation) {
            logMessage("WRN", `Conversation ${conversationId} not found or not owned by user ${userId}`);
            return res.status(404).json({ message: 'Conversation not found or unauthorized' });
        }

        // Calculate file hash
        const fileHash = calculateBufferHash(file.buffer);
        logMessage("INF", `File hash calculated: ${fileHash.substring(0, 8)}... for ${file.originalname}`);

        // Check if file with same hash already exists in this conversation
        const existingFile = await db.get(
            'SELECT * FROM uploaded_files WHERE conversationId = ? AND hash = ?',
            [conversationId, fileHash]
        );

        if (existingFile) {
            logMessage("INF", `File with same hash already exists in conversation ${conversationId}: ${existingFile.originalName}`);
            return res.status(200).json({
                message: 'File already exists in this conversation',
                file: {
                    id: existingFile.id,
                    fileName: existingFile.fileName,
                    originalName: existingFile.originalName,
                    fileSize: existingFile.fileSize,
                    mimeType: existingFile.mimeType,
                    uploadedAt: existingFile.uploadedAt,
                    fileUrl: `${req.protocol}://${req.get('host')}/files/${existingFile.fileName}`,
                    isDuplicate: true
                }
            });
        }

        // Generate unique filename
        const timestamp = Date.now();
        const originalName = file.originalname;
        const fileExtension = originalName.split('.').pop();
        const fileName = `${userId}_${conversationId}_${timestamp}.${fileExtension}`;

        // Upload to MinIO
        await minioClient.putObject(
            bucketName,
            fileName,
            file.buffer,
            file.size,
            {
                'Content-Type': file.mimetype,
                'Original-Name': originalName,
                'File-Hash': fileHash
            }
        );

        // Save to data folder for RAG processing (only for PDF files)
        if (file.mimetype === 'application/pdf') {
            // Create data directory if it doesn't exist
            const dataDir = join(__dirname, "../", "../", '../chatbot/mcp-server/data');
            try {
                await fs.access(dataDir);
            } catch (error) {
                await fs.mkdir(dataDir, { recursive: true });
                logMessage("INF", `Created data directory: ${dataDir}`);
            }

            // Save PDF file to data directory
            const dataFilePath = join(dataDir, fileName);
            await fs.writeFile(dataFilePath, file.buffer);
            logMessage("INF", `PDF saved to data folder for RAG processing: ${dataFilePath}`);
        }

        // Save file info to database
        const fileResult = await db.run(
            'INSERT INTO uploaded_files (conversationId, fileName, originalName, fileSize, mimeType, hash, uploadedAt) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [conversationId, fileName, originalName, file.size, file.mimetype, fileHash, new Date().toISOString()]
        );

        if (!fileResult.lastID) {
            logMessage("ERR", `Failed to save file info for conversation ${conversationId}`);
            return res.status(500).json({ message: 'Failed to save file info' });
        }

        // Get the saved file info
        const savedFile = await db.get('SELECT * FROM uploaded_files WHERE id = ?', [fileResult.lastID]);

        logMessage("INF", `File uploaded successfully to conversation ${conversationId} by user ${userId}: ${originalName}`);

        return res.status(201).json({
            message: 'File uploaded successfully',
            file: {
                id: savedFile.id,
                fileName: savedFile.fileName,
                originalName: savedFile.originalName,
                fileSize: savedFile.fileSize,
                mimeType: savedFile.mimeType,
                uploadedAt: savedFile.uploadedAt,
                fileUrl: `${req.protocol}://${req.get('host')}/files/${fileName}`
            }
        });

    } catch (error) {
        logMessage("ERR", `Error uploading file to conversation ${req.params.id}: ${error.message}`, error.stack);
        return res.status(500).json({ message: 'Internal server error' });
    }
});

// Get uploaded files for a conversation
router.get('/conversations/:id/files', authenticateToken, async (req, res) => {
    try {
        const userId = req.user.userId;
        const conversationId = req.params.id;

        const db = await getDb();

        // Verify conversation ownership
        const conversation = await db.get('SELECT * FROM conversations WHERE id = ? AND userId = ?', [conversationId, userId]);
        if (!conversation) {
            logMessage("WRN", `Conversation ${conversationId} not found or not owned by user ${userId}`);
            return res.status(404).json({ message: 'Conversation not found or unauthorized' });
        }

        // Get all files for this conversation
        const files = await db.all(
            'SELECT * FROM uploaded_files WHERE conversationId = ? ORDER BY uploadedAt DESC',
            [conversationId]
        );

        // Add file URLs
        const filesWithUrls = files.map(file => ({
            ...file,
            fileUrl: `${req.protocol}://${req.get('host')}/files/${file.fileName}`
        }));

        logMessage("INF", `Loaded ${files.length} files for conversation ${conversationId} by user ${userId}`);
        return res.status(200).json({ files: filesWithUrls });

    } catch (error) {
        logMessage("ERR", `Error loading files for conversation ${req.params.id}: ${error.message}`, error.stack);
        return res.status(500).json({ message: 'Internal server error' });
    }
});

// Delete uploaded file
router.delete('/conversations/:id/files/:fileId', authenticateToken, async (req, res) => {
    try {
        const userId = req.user.userId;
        const conversationId = req.params.id;
        const fileId = req.params.fileId;

        const db = await getDb();

        // Verify conversation ownership
        const conversation = await db.get('SELECT * FROM conversations WHERE id = ? AND userId = ?', [conversationId, userId]);
        if (!conversation) {
            logMessage("WRN", `Conversation ${conversationId} not found or not owned by user ${userId}`);
            return res.status(404).json({ message: 'Conversation not found or unauthorized' });
        }

        // Get file info
        const file = await db.get('SELECT * FROM uploaded_files WHERE id = ? AND conversationId = ?', [fileId, conversationId]);
        if (!file) {
            logMessage("WRN", `File ${fileId} not found in conversation ${conversationId}`);
            return res.status(404).json({ message: 'File not found' });
        }

        // Delete from MinIO
        await minioClient.removeObject(bucketName, file.fileName);

        // Delete from data folder if it's a PDF
        if (file.mimeType === 'application/pdf') {
            try {
                const dataDir = join(__dirname, "../", "../", '../chatbot/mcp-server/data');
                const dataFilePath = join(dataDir, file.fileName);
                await fs.unlink(dataFilePath);
                logMessage("INF", `PDF deleted from data folder: ${dataFilePath}`);
            } catch (error) {
                logMessage("WRN", `Could not delete PDF from data folder: ${error.message}`);
            }
        }

        // Delete from database
        const result = await db.run('DELETE FROM uploaded_files WHERE id = ?', [fileId]);

        if (result.changes > 0) {
            logMessage("INF", `File ${fileId} deleted from conversation ${conversationId} by user ${userId}`);
            return res.status(200).json({ message: 'File deleted successfully' });
        } else {
            logMessage("ERR", `Failed to delete file ${fileId} from conversation ${conversationId}`);
            return res.status(500).json({ message: 'Failed to delete file' });
        }

    } catch (error) {
        logMessage("ERR", `Error deleting file ${req.params.fileId} from conversation ${req.params.id}: ${error.message}`, error.stack);
        return res.status(500).json({ message: 'Internal server error' });
    }
});

export default router;