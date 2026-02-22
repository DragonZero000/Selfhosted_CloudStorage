import { useState } from 'react';
//import { useTranslation } from 'react-i18next';
import axios from "axios"
import { useNavigate } from 'react-router-dom'

const api = axios.create({
    baseURL: 'http://127.0.0.1:8000',
    timeout: 10000
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
        setError(null)
        setIsLoading(true)
        try {
            const result = await api.post('/token', new URLSearchParams({ username: formData.login, password: formData.password, grant_type: "password" }),
                {
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                })
            sessionStorage.setItem('access_token', result.data.access_token)
            navigate('/main', {replace: true})
        }
        catch (err) {
            if (axios.isAxiosError(err)) {
              const status = err.response?.status;
              if (status === 401) {
                setError('Incorrect login or password');
              }
              else if (status === 0 || !err.response) {
                setError('No connection to the server');
              }
              else {
                setError('An error occurred. Please try again later.');
              }
            }
            else {
              setError('Unknown error');
              console.error(err);
            }
        }
        finally {
            setIsLoading(false)
        }
    }

    return (
        <div className='w-1/4'>
            <h1 className='text-center mb-4 text-3xl'>Cloud</h1>
            <form onSubmit={handleSubmit} className="p-2 flex flex-col gap-1 border border-white-500 rounded-xl bg-gray-800">
                <div className='flex gap-1'>
                    <label>Login:</label>
                    <input type="text" name="login" value={formData.login} onChange={handleChange} placeholder="admin" required className='basis-full' disabled={isLoading}></input>
                </div>
                <div className='flex gap-1'>
                    <label>Password:</label>
                    <input type="password" name="password" value={formData.password} onChange={handleChange} placeholder="qwerty" required className='basis-full' disabled={isLoading}></input>
                </div>
                {error && (<div className="rounded-xl bg-red-900/50 text-sm text-red-200 text-center">{error}</div>)}
                <div className="flex items-center justify-center">
                <button type="submit" className='w-full flex items-center justify-center border border-white-500 rounded-xl' disabled={isLoading}>{isLoading ? (<>
                  <svg className="mr-2 h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>Entering...</>) : ('Enter')
                }</button>
                </div>
            </form>
        </div>
    )
}

export default Login
