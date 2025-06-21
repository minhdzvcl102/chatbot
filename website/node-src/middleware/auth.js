import jwt from 'jsonwebtoken';
import { logMessage } from '../utilities/logger.js';
import { configDotenv } from 'dotenv';

configDotenv();

const JWT_SECRET = process.env.JWT_SECRET;
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '1h';

const authenticateToken = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) {
        return res.status(401).json({ message: 'Access token required' });
    }

    jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err) {
            console.log('JWT Verify Error:', err.message);
            return res.status(403).json({ 
                message: 'Invalid or expired token',
                error: err.message 
            });
        }
        req.user = user;
        next();
    });
};

export default authenticateToken;