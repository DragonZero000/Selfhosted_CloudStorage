import { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import "../styles/login.css";
import { useTranslation } from 'react-i18next';

function Login() {
  const { t, i18n } = useTranslation();

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
  timeout: 10000,
});

function Login() {
  const [mode, setMode]           = useState("login"); // "login" | "register"
  const [formData, setFormData]   = useState({ login: "", password: "", confirm: "" });
  const [error, setError]         = useState("");
  const [success, setSuccess]     = useState("");
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
        if (status === 401)     setError("Неверный логин или пароль");
        else if (!err.response) setError("Нет подключения к серверу");
        else                    setError("Ошибка сервера. Попробуйте позже.");
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
        if (status === 400)     setError(err.response.data?.detail || "Логин уже занят");
        else if (!err.response) setError("Нет подключения к серверу");
        else                    setError("Ошибка сервера. Попробуйте позже.");
      } else {
        setError("Неизвестная ошибка");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-page">

      {/* ── Block: auth-logo ── */}
      <div className="auth-logo">
        <span className="auth-logo__icon">☁️</span>
        <h1 className="auth-logo__title">CloudStorage</h1>
      </div>

      {/* ── Block: auth-tabs ── */}
      <div className="auth-tabs">
        {["login", "register"].map((m) => (
          <button
            key={m}
            onClick={() => switchMode(m)}
            className={`auth-tabs__item${mode === m ? " auth-tabs__item--active" : ""}`}
          >
            {m === "login" ? "Вход" : "Регистрация"}
          </button>
        ))}
      </div>

      {/* ── Block: auth-form ── */}
      <form
        onSubmit={mode === "login" ? handleLogin : handleRegister}
        className="auth-form"
      >
        {/* Element: поле логина */}
        <div className="auth-form__field">
          <label className="auth-form__label">Логин</label>
          <input
            type="text"
            name="login"
            value={formData.login}
            onChange={handleChange}
            placeholder="username"
            required
            disabled={isLoading}
            className="auth-form__input"
          />
        </div>

        {/* Element: поле пароля */}
        <div className="auth-form__field">
          <label className="auth-form__label">Пароль</label>
          <input
            type="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            placeholder="••••••"
            required
            disabled={isLoading}
            className="auth-form__input"
          />
        </div>

        {/* Element: подтверждение пароля (только в режиме регистрации) */}
        {mode === "register" && (
          <div className="auth-form__field">
            <label className="auth-form__label">Подтверждение пароля</label>
            <input
              type="password"
              name="confirm"
              value={formData.confirm}
              onChange={handleChange}
              placeholder="••••••"
              required
              disabled={isLoading}
              className="auth-form__input"
            />
          </div>
        )}

        {/* Element: сообщения об ошибке / успехе */}
        {error && (
          <div className="auth-form__alert auth-form__alert--error">{error}</div>
        )}
        {success && (
          <div className="auth-form__alert auth-form__alert--success">{success}</div>
        )}

        {/* Element: кнопка отправки */}
        <button
          type="submit"
          disabled={isLoading}
          className="auth-form__submit"
        >
          {isLoading ? (
            /* Block: auth-spinner */
            <span className="auth-spinner">
              <svg className="auth-spinner__icon" viewBox="0 0 24 24" fill="none">
                <circle
                  className="auth-spinner__arc"
                  cx="12" cy="12" r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="auth-spinner__path"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              {mode === "login" ? "Вхожу..." : "Создаю..."}
            </span>
          ) : (
            mode === "login" ? "Войти" : "Создать аккаунт"
          )}
        </button>
      </form>
    </div>
  );
}

export default Login;
