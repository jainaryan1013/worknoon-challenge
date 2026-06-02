import { Link, Navigate, Route, Routes } from "react-router-dom";

import { AdminPage } from "./features/admin/AdminPage";
import { ChatPage } from "./features/chat/ChatPage";

export default function App() {
  return (
    <div>
      <nav className="flex gap-4 border-b bg-gray-50 px-4 py-2 text-sm">
        <Link to="/chat" className="text-blue-600 hover:underline">
          Chat
        </Link>
        <Link to="/admin" className="text-blue-600 hover:underline">
          Admin
        </Link>
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </div>
  );
}
