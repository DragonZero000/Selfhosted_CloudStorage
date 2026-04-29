/*import { useState } from "react";
//import { useTranslation } from 'react-i18next';
import axios from "axios";
import { useNavigate } from "react-router-dom";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
  timeout: 10000,
});
function Login() {
  const [formData, setFormData] = useState({ login: "", password: "" });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };
  const handleSubmit = async function (e) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      const result = await api.post(
        "/token",
        new URLSearchParams({
          username: formData.login,
          password: formData.password,
          grant_type: "password",
        }),
        {
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        },
      );
      sessionStorage.setItem("access_token", result.data.access_token);
      navigate("/main", { replace: true });
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        if (status === 401) {
          setError("Incorrect login or password");
        } else if (status === 0 || !err.response) {
          setError("No connection to the server");
        } else {
          setError("An error occurred. Please try again later.");
        }
      } else {
        setError("Unknown error");
        console.error(err);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-1/4">
      <h1 className="text-center mb-4 text-3xl">Cloud</h1>
      <form
        onSubmit={handleSubmit}
        className="p-2 flex flex-col gap-1 border border-white-500 rounded-xl bg-gray-800"
      >
        <div className="flex gap-1">
          <label>Login:</label>
          <input
            type="text"
            name="login"
            value={formData.login}
            onChange={handleChange}
            placeholder="admin"
            required
            className="basis-full"
            disabled={isLoading}
          ></input>
        </div>
        <div className="flex gap-1">
          <label>Password:</label>
          <input
            type="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            placeholder="qwerty"
            required
            className="basis-full"
            disabled={isLoading}
          ></input>
        </div>
        {error && (
          <div className="rounded-xl bg-red-900/50 text-sm text-red-200 text-center">
            {error}
          </div>
        )}
        <div className="flex items-center justify-center">
          <button
            type="submit"
            className="w-full flex items-center justify-center border border-white-500 rounded-xl"
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <svg
                  className="mr-2 h-5 w-5 animate-spin"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    class="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    stroke-width="4"
                  ></circle>
                  <path
                    class="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Entering...
              </>
            ) : (
              "Enter"
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

export default Login;
*/
import { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
  timeout: 10000,
});

function Login() {
  const [mode, setMode]         = useState("login");   // "login" | "register"
  const [formData, setFormData] = useState({ login: "", password: "", confirm: "" });
  const [error, setError]       = useState("");
  const [success, setSuccess]   = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError("");
    setSuccess("");
  };

  const switchMode = (m) => {
    setMode(m);
    setError("");
    setSuccess("");
    setFormData({ login: "", password: "", confirm: "" });
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const res = await api.post(
        "/token",
        new URLSearchParams({
          username:   formData.login,
          password:   formData.password,
          grant_type: "password",
        }),
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
      );
      sessionStorage.setItem("access_token", res.data.access_token);
      sessionStorage.setItem("username", formData.login);
      navigate("/main", { replace: true });
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        if (status === 401)        setError("Неверный логин или пароль");
        else if (!err.response)    setError("Нет подключения к серверу");
        else                       setError("Ошибка сервера. Попробуйте позже.");
      } else {
        setError("Неизвестная ошибка");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError("");
    if (formData.password !== formData.confirm) {
      setError("Пароли не совпадают");
      return;
    }
    if (formData.password.length < 6) {
      setError("Пароль должен быть не менее 6 символов");
      return;
    }
    setIsLoading(true);
    try {
      await api.post("/register", {
        login:    formData.login,
        password: formData.password,
      });
      setSuccess("Аккаунт создан! Теперь войдите.");
      setFormData({ login: formData.login, password: "", confirm: "" });
      setTimeout(() => switchMode("login"), 1500);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        if (status === 400) setError(err.response.data?.detail || "Логин уже занят");
        else if (!err.response) setError("Нет подключения к серверу");
        else setError("Ошибка сервера. Попробуйте позже.");
      } else {
        setError("Неизвестная ошибка");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-sm px-4">
      {/* Title */}
      <div className="text-center mb-6">
        <span className="text-4xl">☁️</span>
        <h1 className="text-2xl font-bold mt-1 tracking-wide">CloudStorage</h1>
      </div>

      {/* Tab switcher */}
      <div className="flex rounded-xl overflow-hidden mb-4 border border-gray-700">
        {["login", "register"].map((m) => (
          <button
            key={m}
            onClick={() => switchMode(m)}
            className={`flex-1 py-2 text-sm font-medium transition-colors ${
              mode === m
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {m === "login" ? "Вход" : "Регистрация"}
          </button>
        ))}
      </div>

      {/* Form */}
      <form
        onSubmit={mode === "login" ? handleLogin : handleRegister}
        className="flex flex-col gap-3 p-4 bg-gray-800 rounded-xl border border-gray-700"
      >
        <div className="flex flex-col gap-1">
          <label className="text-sm text-gray-400">Логин</label>
          <input
            type="text"
            name="login"
            value={formData.login}
            onChange={handleChange}
            placeholder="username"
            required
            disabled={isLoading}
            className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-sm text-gray-400">Пароль</label>
          <input
            type="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            placeholder="••••••"
            required
            disabled={isLoading}
            className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>

        {mode === "register" && (
          <div className="flex flex-col gap-1">
            <label className="text-sm text-gray-400">Подтверждение пароля</label>
            <input
              type="password"
              name="confirm"
              value={formData.confirm}
              onChange={handleChange}
              placeholder="••••••"
              required
              disabled={isLoading}
              className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
        )}

        {error && (
          <div className="bg-red-900/50 border border-red-700 text-red-200 text-sm rounded-lg px-3 py-2 text-center">
            {error}
          </div>
        )}
        {success && (
          <div className="bg-green-900/50 border border-green-700 text-green-200 text-sm rounded-lg px-3 py-2 text-center">
            {success}
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg py-2 transition-colors mt-1"
        >
          {isLoading ? (
            <>
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {mode === "login" ? "Вхожу..." : "Создаю..."}
            </>
          ) : mode === "login" ? "Войти" : "Создать аккаунт"}
        </button>
      </form>
    </div>
  );
}

export default Login;