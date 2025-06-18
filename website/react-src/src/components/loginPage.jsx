import React, { useState } from "react";
// Cài đặt thư viện icon nếu cần: npm install lucide-react
import { Menu } from "lucide-react";

const LoginPage = () => {
  // Sử dụng state để quản lý giá trị của các ô input
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // Hàm xử lý khi người dùng nhấn nút đăng nhập
  const handleLogin = (e) => {
    e.preventDefault(); // Ngăn trình duyệt tải lại trang
    // Tại đây, bạn có thể thêm logic xác thực người dùng
    console.log("Đăng nhập với:", { username, password });
  };

  return (
    <div className="min-h-screen bg-[#f7f9fb] font-sans">
      {/* Navbar */}
      <nav className="w-full flex items-center h-16 px-8 border-b border-gray-100 bg-white">
        <Menu size={22} className="mr-2 text-black" />
        <span className="text-lg font-bold tracking-tight text-black">
          SecureChat
        </span>
      </nav>
      {/* Main content */}
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)]">
        <form
          onSubmit={handleLogin}
          className="w-full max-w-md flex flex-col gap-6 mt-8"
        >
          <h2 className="text-2xl md:text-3xl font-bold text-center text-black mb-2 mt-2">
            Welcome back to SecureChat
          </h2>
          <div className="flex flex-col gap-1">
            <label
              htmlFor="username"
              className="font-semibold text-base text-black mb-1"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              className="w-full px-5 py-3 rounded-xl bg-[#eef2f6] text-base text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400 border-none"
              required
            />
          </div>
          <div className="flex flex-col gap-1">
            <label
              htmlFor="password"
              className="font-semibold text-base text-black mb-1"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="w-full px-5 py-3 rounded-xl bg-[#eef2f6] text-base text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400 border-none"
              required
            />
          </div>
          <button
            type="submit"
            className="w-full bg-[#1884f7] hover:bg-[#166cd8] text-white font-semibold text-lg py-3 rounded-xl transition-colors mt-2 mb-1"
          >
            Sign in
          </button>
          <div className="flex flex-col items-center gap-2 mt-1">
            <a href="#" className="text-sm text-gray-500 hover:underline">
              Forgot your username or password?
            </a>
            <span className="text-sm text-gray-500">
              New to SecureChat?{" "}
              <a href="#" className="text-blue-600 hover:underline font-medium">
                Sign up
              </a>
            </span>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
