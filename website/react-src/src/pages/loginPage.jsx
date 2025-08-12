import React, { useState, useEffect } from "react";
import { Menu } from "lucide-react";
import axios from "axios";
import { useNavigate } from "react-router-dom";

const LoginPage = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({});

  // Kiểm tra nếu đã đăng nhập, tự động chuyển hướng
  useEffect(() => {
    const authToken = localStorage.getItem('authToken');
    if (authToken) {
      const user = localStorage.getItem('user');
      if (user) {
        try {
          const userData = JSON.parse(user);
          console.log('Login page check - User role:', userData.role, 'Type:', typeof userData.role);
          
          // Đảm bảo so sánh chính xác
          if (String(userData.role) === '0') {
            console.log('Redirecting to admin from login page');
            navigate('/admin');
          } else {
            console.log('Redirecting to home from login page');
            navigate('/');
          }
        } catch (error) {
          console.error('Error parsing user data:', error);
          // Nếu có lỗi, xóa token và ở lại trang login
          localStorage.removeItem('authToken');
          localStorage.removeItem('user');
        }
      }
    }
  }, [navigate]);

  const handleLogin = async (e) => {
    e.preventDefault();

    setErrors({});

    let newErrors = {};

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
        console.log("Full server response:", response.data);
        console.log("User role from server:", response.data.userRole, "Type:", typeof response.data.userRole);
        
        // Lưu token
        localStorage.setItem('authToken', response.data.token);

        // Lưu thông tin user với role - đảm bảo role là string
        const userData = {
          id: response.data.userId,
          username: response.data.username,
          role: String(response.data.userRole) // Đảm bảo chuyển thành string
        };
        localStorage.setItem('user', JSON.stringify(userData));
        localStorage.setItem('user.id', response.data.userId);

        console.log('Saved user data:', userData);
        console.log('Role after save:', userData.role, 'Type:', typeof userData.role);

        // Điều hướng dựa trên role - sử dụng cùng logic với AuthGuard
        if (String(response.data.userRole) === '0') {
          console.log('Admin detected, redirecting to admin');
          navigate('/admin');
        } else {
          console.log('Regular user, redirecting to home');
          navigate('/');
        }
      }

    } catch (error) {
      console.error('Login error:', error);

      // Xử lý lỗi từ server
      let errorMessage = "Đăng nhập thất bại. Vui lòng thử lại.";

      if (error.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else if (error.message) {
        errorMessage = error.message;
      }

      setErrors(prevErrors => ({
        ...prevErrors,
        server: errorMessage,
      }));
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
              <a href="/register" className="text-blue-600 hover:underline font-medium">
                Register
              </a>
            </span>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;