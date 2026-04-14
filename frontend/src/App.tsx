import { Navigate, Route, Routes } from 'react-router-dom'
import HomePage from './pages/HomePage.tsx'
import LoginPage from './pages/LoginPage.tsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/home" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/home" element={<HomePage />} />
    </Routes>
  )
}
