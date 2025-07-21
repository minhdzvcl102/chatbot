// src/components/PrivateRoute.jsx
import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';

const PrivateRoute = ({ requiredRole = null }) => {
  const authToken = localStorage.getItem('authToken');
  const user = localStorage.getItem('user');

  // console.log('=== PrivateRoute Debug ===');
  // console.log('Auth token exists:', !!authToken);
  // console.log('User data:', user);
  // console.log('Required role:', requiredRole, 'Type:', typeof requiredRole);

  // Nếu không có token, chuyển hướng đến login
  if (!authToken) {
    console.log('No auth token, redirecting to login');
    return <Navigate to="/login" replace />;
  }

  // Nếu yêu cầu role cụ thể
  if (requiredRole !== null) {
    try {
      const userData = JSON.parse(user);
      console.log('Parsed user data:', userData);
      
      const userRole = userData?.role || localStorage.getItem('userRole');
      console.log('User role:', userRole, 'Type:', typeof userRole);
      
      // Log comparison
      // console.log('Role comparison:', userRole, '===', requiredRole, '=', userRole === requiredRole);
      // console.log('String comparison:', String(userRole), '===', String(requiredRole), '=', String(userRole) === String(requiredRole));
      
      // Nếu không có role hoặc role không khớp, chuyển hướng
      if (!userRole || String(userRole) !== String(requiredRole)) {
        console.log('Role check failed, redirecting to home');
        return <Navigate to="/" replace />;
      }
      
      console.log('Role check passed, allowing access');
    } catch (error) {
      console.error('Error parsing user data:', error);
      return <Navigate to="/login" replace />;
    }
  }

  console.log('Access granted');
  return <Outlet />;
};

export default PrivateRoute;