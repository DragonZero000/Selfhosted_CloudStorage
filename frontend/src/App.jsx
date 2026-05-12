import './App.css'
import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/login'
import Main  from './pages/main'
import ThemeSwitcher from './components/themeswitcher'
import LanguageSwitcher from './components/languageswitcher'

function App() {
  return (
    <>
      {/* Переключатели */}
      <div className="fixed bottom-4 right-4 flex items-center gap-2 z-50">
        <ThemeSwitcher />
        <LanguageSwitcher />
      </div>

      <Routes>
        <Route path="/" element={
          <main className="auth-layout">
            <Login />
          </main>
        } />
        <Route path="/main" element={<Main />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

export default App