# Sử dụng image nền Node.js phiên bản 20, loại 'alpine' cho nhẹ
FROM node:20-alpine

# Đặt thư mục làm việc bên trong container là /app
WORKDIR /app

# Sao chép các file package.json và package-lock.json vào trước
# Điều này giúp tận dụng cache của Docker, chỉ cài lại thư viện khi cần
COPY package*.json ./

# Chạy lệnh để cài đặt tất cả thư viện
RUN npm install

# Sao chép toàn bộ mã nguồn còn lại của dự án vào /app
COPY . .

# Mở cổng 5173 để Vite có thể giao tiếp ra ngoài
EXPOSE 5173

# Lệnh mặc định sẽ chạy khi container khởi động
# '-- --host' để có thể truy cập từ máy tính của bạn
CMD ["npm", "run", "dev", "--", "--host"]