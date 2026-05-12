import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

const resources = {
  en: {
    translation: {
      Login: 'Login',
      Register: 'Register',
      Username: 'Username',
      Password: 'Password',
      'Confirm Password': 'Confirm Password',
      Enter: 'Enter',
      'Create account': 'Create account',
      // добавляй сюда все ключи по мере необходимости
    }
  },
  ru: {
    translation: {
      Login: 'Вход',
      Register: 'Регистрация',
      Username: 'Логин',
      Password: 'Пароль',
      'Confirm Password': 'Подтверждение пароля',
      Enter: 'Войти',
      'Create account': 'Создать аккаунт',
    }
  }
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'en',
    supportedLngs: ['en', 'ru'],

    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18nextLng',
    },

    interpolation: {
      escapeValue: false,
    },

    react: {
      useSuspense: false,   // ← важно для стабильности
    }
  });

export default i18n;