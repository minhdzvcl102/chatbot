// vite.config.js

// 1. Import plugin ở đầu file
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite'; // <-- THÊM DÒNG NÀY


export default defineConfig({
  // 2. Thêm plugin vào mảng `plugins`
  plugins: [
    react(),
    tailwindcss(), // <-- VÀ THÊM DÒNG NÀY
  ],
});