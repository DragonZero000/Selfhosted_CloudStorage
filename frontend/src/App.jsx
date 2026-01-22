import './App.css'
import {Routes, Route } from 'react-router-dom'
import Login from './pages/login'

function App() {
    return (
        <main className='min-h-screen flex items-center justify-center'>
            <Routes>
                <Route path="/" element={<Login />} />
                <Route path="/main" element={<h1>fwaeeeeeeeeeeeeeeeeeeee</h1> } />
            </Routes>
        </main>   
  )
}

export default App
