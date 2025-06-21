import React, { useState } from "react";
import { Menu } from "lucide-react";
import axios from "axios";
import { useNavigate } from "react-router-dom";

const LoginPage = () => {
  const navigate = useNavigate();
  // Sử dụng state để quản lý giá trị của các ô input
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({}); // State để quản lý lỗi

  const handleLogin = async (e) => {
    e.preventDefault();

    setErrors({}); // Đặt lại tất cả lỗi về rỗng trước mỗi lần submit

    let newErrors = {}; // Tạo một đối tượng tạm thời để thu thập lỗi client-side

    if (!email.trim()) {
      newErrors.email = "Email is required";
    } else if (!/\S+@\S+\.\S+/.test(email)) {
      newErrors.email = "Email format is invalid";
    }

    if (!password.trim()) {
      newErrors.password = "Password is required";
    } else if (password.length < 6) {
      newErrors.password = "Password must be at least 6 characters";
    }

    setErrors(newErrors);

    if (Object.keys(newErrors).length > 0) {
      return;
    }

    try {
      const response = await axios.post('http://localhost:3000/account/login', {
        email: email,
        password: password,
      });

      if (response.status === 200) {
        console.log("Đăng nhập thành công:", response.data);
        localStorage.setItem('authToken', response.data.token);
        navigate('/'); // Chuyển hướng đến trang chủ
      }

    } catch (error) {
      // Cập nhật state `errors` với thông báo lỗi từ server
      setErrors(prevErrors => ({
        ...prevErrors, // Giữ lại các lỗi client-side nếu có (tùy thuộc vào UX mong muốn)
        server: error.response?.data?.message || "Đăng nhập thất bại. Vui lòng thử lại.",
      }));

      navigate('/login');
    }
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
              htmlFor="email"
              className="font-semibold text-base text-black mb-1"
            >
              Email
            </label>
            <input
              id="email"
              type="text"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email"
              className={`w-full px-5 py-3 rounded-xl bg-[#eef2f6] text-base text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400 border-none ${errors.email ? 'border border-red-500' : ''
                }`}
            />
            {errors.email && (
              <span className="text-red-500 text-sm">
                {errors.email}
              </span>
            )}
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
              className={`w-full px-5 py-3 rounded-xl bg-[#eef2f6] text-base text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400 border-none ${errors.password ? 'border border-red-500' : ''
                }`}
            />
            {errors.password && (
              <span className="text-red-500 text-sm">
                {errors.password}
              </span>
            )}
          </div>

          {errors.server && (
            <p className="text-red-500 text-center text-sm mt-2">{errors.server}</p>
          )}

          <button
            type="submit"
            className="w-full bg-[#1884f7] hover:bg-[#166cd8] text-white font-semibold text-lg py-3 rounded-xl transition-colors mt-2 mb-1"
          >
            Sign in
          </button>
          <div className="flex flex-col items-center gap-2 mt-1">
            <a href="#" className="text-sm text-gray-500 hover:underline">
              Forgot your email or password?
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