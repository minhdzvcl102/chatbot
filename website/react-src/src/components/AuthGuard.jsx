// src/components/AuthGuard.jsx
import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const AuthGuard = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const checkAuth = () => {
    //   console.log('=== AuthGuard Debug ===');
    //   console.log('Current path:', location.pathname);
      
      const authToken = localStorage.getItem('authToken');
      const user = localStorage.getItem('user');
      const publicRoutes = ['/login', '/register'];
      const isPublicRoute = publicRoutes.includes(location.pathname);

    //   console.log('Auth token exists:', !!authToken);
    //   console.log('Is public route:', isPublicRoute);
    //   console.log('User data:', user);

      // Nếu không có token và không phải là public route
      if (!authToken && !isPublicRoute) {
        console.log('No token and not public route, redirecting to login');
        navigate('/login', { replace: true });
        return;
      }

      // Nếu có token và đang ở trang login/register, chuyển hướng
      if (authToken && isPublicRoute) {
        console.log('Has token and on public route, redirecting...');
        if (user) {
          try {
            const userData = JSON.parse(user);
            console.log('Parsed user data:', userData);
            console.log('User role:', userData.role, 'Type:', typeof userData.role);
            
            if (String(userData.role) === '0') {
              console.log('Admin role detected, redirecting to admin');
              navigate('/admin', { replace: true });
            } else {
              console.log('Regular user role, redirecting to home');
              navigate('/', { replace: true });
            }
          } catch (error) {
            console.error('Error parsing user data:', error);
            localStorage.removeItem('authToken');
            localStorage.removeItem('user');
            navigate('/login', { replace: true });
          }
        } else {
          console.log('No user data, redirecting to home');
          navigate('/', { replace: true });
        }
      }
    };

    checkAuth();
  }, [navigate, location.pathname]);

  return children;
};

export default AuthGuard;