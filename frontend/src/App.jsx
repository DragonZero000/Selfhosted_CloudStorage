import './App.css'
import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/login'
import Main  from './pages/main'

function App() {
  return (
    <Routes>
      <Route path="/"     element={
        <main className="auth-layout">
          <Login />
        </main>
      } />
      <Route path="/main" element={<Main />} />
      <Route path="*"     element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App