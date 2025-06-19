
import express from 'express';
import cors from 'cors';
import jwt from 'jsonwebtoken';
const app = express();
const JWT_SECRET = process.env.JWT_SECRET || 'your_super_secret_key'; // Lấy từ biến môi trường

// Middleware để parse JSON body
app.use(express.json());

// Middleware CORS để cho phép frontend truy cập
app.use(cors());

// Custom Middleware để xác thực JWT
const authenticateToken = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1]; // Lấy token từ 'Bearer TOKEN'

    if (token == null) {
        return res.sendStatus(401); // Nếu không có token, trả về 401 Unauthorized
    }

    jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err) {
            return res.sendStatus(403); // Nếu token không hợp lệ (hết hạn, sai chữ ký), trả về 403 Forbidden
        }
        req.user = user; // Lưu thông tin người dùng đã giải mã vào req để các route tiếp theo sử dụng
        next(); // Chuyển sang middleware hoặc route handler tiếp theo
    });
};

export default authenticateToken;