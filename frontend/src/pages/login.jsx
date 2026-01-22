import { useState } from 'react';
//import { useTranslation } from 'react-i18next';
import axios from "axios"
import { useNavigate } from 'react-router-dom'

const api = axios.create({
    baseURL: 'http://127.0.0.1:8000'
})
function Login() {
    const [formData, setFormData] = useState({ login: '', password: '' });
    const [error, setError] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const navigate = useNavigate()
    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };
    const handleSubmit = async function (e) {
        e.preventDefault()
        console.log(formData.login, formData.password)
        setError(null)
        setIsLoading(true)
        try {
            console.log(formData.login, "yugfv1")
            const result = await api.post('/token', new URLSearchParams({ username: formData.login, password: formData.password }),
                {
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                })
            console.log(formData.login, "yugfv")
            sessionStorage.setItem('access_token', result.data.access_token)
            navigate('/main')
        }
        catch (err) {
            console.log(err)
            const errorStatus = err?.response?.status
            setError(errorStatus === 401 ? 'Incorrect login or password' : 'Error connection')            
        }
        finally {
            setIsLoading(false)
            console.log(error, isLoading)
        }
    }

    return (
        <div className='w-1/4'>
            <h1 className='text-center mb-4 text-3xl'>Cloud</h1>
            <form onSubmit={handleSubmit} className="p-2 flex flex-col gap-1 border border-white-500 rounded-xl bg-gray-800">
                <div className='flex gap-1'>
                    <label>Login:</label>
                    <input type="text" name="login" value={formData.login} onChange={handleChange} placeholder="admin" required className='basis-full'></input>
                </div>
                <div className='flex gap-1'>
                    <label>Password:</label>
                    <input type="password" name="password" value={formData.password} onChange={handleChange} placeholder="qwerty" required className='basis-full'></input>
                </div>
                <button type="submit" className='border border-white-500 rounded-xl'>Enter</button>
            </form>
        </div>
    )
}

export default Login