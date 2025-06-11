import React, { useState } from 'react';
// Cài đặt thư viện icon nếu cần: npm install lucide-react
import { ShieldCheck } from 'lucide-react';

const LoginPage = () => {
  // Sử dụng state để quản lý giá trị của các ô input
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // Hàm xử lý khi người dùng nhấn nút đăng nhập
  const handleLogin = (e) => {
    e.preventDefault(); // Ngăn trình duyệt tải lại trang
    // Tại đây, bạn có thể thêm logic xác thực người dùng
    console.log('Đăng nhập với:', { username, password });
    alert(`Đăng nhập với\nUsername: ${username}\nPassword: ${password}`);
  };

  return (
    // Nền xám cho toàn bộ trang
    <div className="flex items-center justify-center min-h-screen bg-gray-100 font-sans">
      
      {/* Khung chứa form đăng nhập */}
      <div className="w-full max-w-md bg-white rounded-lg shadow-md overflow-hidden">
        
        {/* Phần Header của form */}
        <header className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center">
            <ShieldCheck className="text-blue-600 mr-2" size={24} />
            <h1 className="text-xl font-bold text-gray-800">SecureChat</h1>
          </div>
        </header>

        {/* Phần thân của form */}
        <main className="p-8">
          <h2 className="text-2xl font-semibold text-center text-gray-700 mb-6">
            Welcome back to SecureChat
          </h2>

          <form onSubmit={handleLogin}>
            {/* Ô nhập Username */}
            <div className="mb-4">
              <label 
                htmlFor="username" 
                className="block text-sm font-medium text-gray-600 mb-1"
              >
                Username
              </label>
              <input
                type="text"
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Username"
                className="w-full px-4 py-2 bg-gray-50 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                required
              />
            </div>

            {/* Ô nhập Password */}
            <div className="mb-6">
              <label 
                htmlFor="password" 
                className="block text-sm font-medium text-gray-600 mb-1"
              >
                Password
              </label>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full px-4 py-2 bg-gray-50 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                required
              />
            </div>

            {/* Nút Đăng nhập */}
            <button
              type="submit"
              className="w-full bg-blue-600 text-white font-bold py-2.5 px-4 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-transform transform active:scale-95"
            >
              Sign In
            </button>
          </form>

          {/* Các liên kết phụ */}
          <div className="text-center mt-6">
            <a
              href="#"
              className="text-sm text-blue-600 hover:underline"
            >
              Forgot your username or password?
            </a>
          </div>

          <div className="text-center mt-4">
            <p className="text-sm text-gray-600">
              New to SecureChat?{' '}
              <a href="#" className="font-semibold text-blue-600 hover:underline">
                Sign up
              </a>
            </p>
          </div>
        </main>
      </div>
    </div>
  );
};

export default LoginPage;
