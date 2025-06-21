// config/server.js - Cấu hình server tập trung
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

export const SERVER_CONFIG = {
  // Server settings
  PORT: process.env.PORT || 3000,
  HOST: process.env.HOST || 'localhost',
  NODE_ENV: process.env.NODE_ENV || 'development',
  
  // Frontend settings
  FRONTEND_URL: process.env.FRONTEND_URL || 'http://localhost:3001',
  
  // Request limits
  JSON_LIMIT: '50mb',
  URL_ENCODED_LIMIT: '50mb',
  
  // Timeout settings
  GRACEFUL_SHUTDOWN_TIMEOUT: 10000, // 10 seconds
  
  // File upload settings
  UPLOAD_DIR: process.env.UPLOAD_DIR || 'uploads',
  MAX_FILE_SIZE: process.env.MAX_FILE_SIZE || '10mb',
  
  // Logging settings
  LOG_MODE: process.env.LOG_MODE || 'CONSOLE+FILE',
  LOG_LEVEL: process.env.LOG_LEVEL || 'INFO',
  
  // Security settings
  RATE_LIMIT_WINDOW: 15 * 60 * 1000, // 15 minutes
  RATE_LIMIT_MAX_REQUESTS: 100, // requests per window
  
  // WebSocket settings
  WS_HEARTBEAT_INTERVAL: 30000, // 30 seconds
  WS_MAX_CONNECTIONS_PER_IP: 10,
  
  // Database settings
  DB_PATH: process.env.DB_PATH || './database/chat.db',
  DB_TIMEOUT: 30000,
  
  // JWT settings (if using)
  JWT_SECRET: process.env.JWT_SECRET,
  JWT_EXPIRE: process.env.JWT_EXPIRE || '24h',
  
  // Cookie settings
  COOKIE_SECRET: process.env.COOKIE_SECRET || 'your-secret-key',
  COOKIE_MAX_AGE: 24 * 60 * 60 * 1000, // 24 hours
  
  // Development flags
  isDevelopment: process.env.NODE_ENV === 'development',
  isProduction: process.env.NODE_ENV === 'production',
  isTesting: process.env.NODE_ENV === 'test'
};

export const CORS_OPTIONS = {
  origin: SERVER_CONFIG.FRONTEND_URL,
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'],
  allowedHeaders: [
    'Content-Type', 
    'Authorization', 
    'Cookie',
    'X-Requested-With',
    'Accept',
    'Origin'
  ],
  exposedHeaders: ['set-cookie']
};

export const API_ENDPOINTS = {
  ROOT: '/',
  HEALTH: '/health',
  AUTH: '/auth',
  ACCOUNT: '/account',
  CHAT: '/api',
  WEBSOCKET_STATS: '/websocket/stats',
  WEBSOCKET_BROADCAST: '/websocket/broadcast',
  FILES: '/files'
};

export const ERROR_MESSAGES = {
  SERVER_NOT_INITIALIZED: 'Server not initialized',
  WEBSOCKET_NOT_INITIALIZED: 'WebSocket server not initialized',
  DATABASE_CONNECTION_FAILED: 'Failed to connect to database',
  INVALID_REQUEST: 'Invalid request data',
  INTERNAL_ERROR: 'Internal server error',
  ROUTE_NOT_FOUND: 'Route not found',
  UNAUTHORIZED: 'Unauthorized access',
  FORBIDDEN: 'Forbidden access',
  TOO_MANY_REQUESTS: 'Too many requests'
};

export const SUCCESS_MESSAGES = {
  SERVER_STARTED: 'Server started successfully',
  DATABASE_CONNECTED: 'Database connected successfully',
  WEBSOCKET_INITIALIZED: 'WebSocket server initialized',
  MESSAGE_BROADCASTED: 'Message broadcasted successfully',
  SHUTDOWN_GRACEFUL: 'Server shutdown gracefully'
};

// Validation function for required environment variables
export function validateEnvironment() {
  const required = [];
  const missing = [];
  
  // Add required environment variables here
  if (SERVER_CONFIG.isProduction) {
    required.push('JWT_SECRET', 'COOKIE_SECRET');
  }
  
  for (const envVar of required) {
    if (!process.env[envVar]) {
      missing.push(envVar);
    }
  }
  
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
  }
  
  return true;
}