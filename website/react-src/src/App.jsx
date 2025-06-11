// src/App.jsx
import LoginPage from './components/loginPage';
import Chatbox from './components/chatbox';
// 1. Import Routes và Route từ 'react-router-dom'
import { Routes, Route } from 'react-router-dom';

function App() {
  return (
    // 2. Bọc tất cả các Route của bạn trong một component <Routes> duy nhất
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Chatbox />} />
      {/* Bạn có thể thêm các Route khác ở đây */}
    </Routes>
  );
}

export default App;