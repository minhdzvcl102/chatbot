
import path from 'path'; 
import { fileURLToPath } from 'url';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const LOG_FILE_PATH = path.join(__dirname, '../../app.log'); // Log file trong thư mục gốc của Node.js backend

let currentLogMode = "CONSOLE"; // Mặc định chỉ log ra console

const LOG_LEVELS = {
    "DBG": "DEBUG",
    "INF": "INFO",
    "WRN": "WARNING",
    "ERR": "ERROR",
    "FTL": "FATAL"
};

function setLogMode(mode) {
    currentLogMode = mode.toUpperCase();
    logMessage("INF", `Log mode set to: ${currentLogMode}`);
}

function logMessage(level, message, stackTrace = null) {
    const timestamp = new Date().toISOString();
    const formattedMessage = `[${timestamp}] [${LOG_LEVELS[level] || level}] ${message}`;

    if (currentLogMode.includes("CONSOLE")) {
        console.log(formattedMessage);
        if (stackTrace) console.error(stackTrace);
    }

    if (currentLogMode.includes("FILE")) {
        fs.appendFile(LOG_FILE_PATH, formattedMessage + '\n', (err) => {
            if (err) console.error('Failed to write to log file:', err);
        });
        if (stackTrace) {
            fs.appendFile(LOG_FILE_PATH, stackTrace + '\n', (err) => {
                if (err) console.error('Failed to write stack trace to log file:', err);
            });
        }
    }
}

export { logMessage, setLogMode };