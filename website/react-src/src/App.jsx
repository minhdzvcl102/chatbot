// src/App.jsx
import LoginPage from './pages/loginPage';
import RegisterPage from './pages/register';
import Chatbox from './pages/chatbox';
import UserManagement from './pages/dashboard';
import { Routes, Route, Navigate } from 'react-router-dom';
import PrivateRoute from './components/PrivateRoute';

function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      
      {/* Admin-only routes */}
      <Route element={<PrivateRoute requiredRole="0" />}>
        <Route path="/admin" element={<UserManagement />} />
      </Route>

      {/* Protected routes for authenticated users */}
      <Route element={<PrivateRoute />}>
        <Route path="/" element={<Chatbox />} />
        <Route path="/chat" element={<Chatbox />} />
      </Route>

      {/* Catch all - redirect to login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default App;