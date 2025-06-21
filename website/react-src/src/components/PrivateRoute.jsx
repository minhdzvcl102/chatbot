// src/components/PrivateRoute.js
import React from 'react';
import { Navigate, Outlet  } from 'react-router-dom'; // Cần React Router DOM

const PrivateRoute = () => {
  const authToken = localStorage.getItem('authToken');

  if (authToken) {
    return <Outlet/>;
  }
  return <Navigate to="/login" replace />;
};

export default PrivateRoute;