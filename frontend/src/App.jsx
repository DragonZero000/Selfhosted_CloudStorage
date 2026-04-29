import './App.css'
import {Routes, Route } from 'react-router-dom'
import Login from './pages/login'
import Main from "./pages/main"

function App() {
    return (
        <main className='min-h-screen flex items-center justify-center'>
            <Routes>
                <Route path="/" element={<Login />} />
                <Route path="/main" element={<Main/>} />
            </Routes>
        </main>   
  )
}

export default App
