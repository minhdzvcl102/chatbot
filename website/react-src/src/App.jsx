// src/App.jsx
import LoginPage from './pages/loginPage';
import Chatbox from './pages/chatbox';
// 1. Import Routes và Route từ 'react-router-dom'
import { Routes, Route } from 'react-router-dom';
import PrivateRoute from './components/PrivateRoute';
function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* Routes được bảo vệ */}
      <Route element={<PrivateRoute />}>
        <Route path="/" element={<Chatbox />} />
        <Route path="/chat" element={<Chatbox />} />
        {/* ... các route được bảo vệ khác */}
      </Route>
    </Routes>
  );
}


export default App;