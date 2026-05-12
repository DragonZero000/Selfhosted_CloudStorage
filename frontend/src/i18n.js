import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

const resources = {
  en: {
    translation: {
      'CloudStorage': 'CloudStorage',
      'Login': 'Login',
      'Register': 'Register',
      'Username': 'Username',
      'Password': 'Password',
      'Confirm Password': 'Confirm Password',
      'Enter': 'Enter',
      'Create account': 'Create account'
    }
  },
  ru: {
    translation: {
      'CloudStorage': 'CloudStorage',
      'Login': 'Вход',
      'Register': 'Регистрация',
      'Username': 'Логин',
      'Password': 'Пароль',
      'Confirm Password': 'Подтверждение пароля',
      'Enter': 'Войти',
      'Create account': 'Создать аккаунт'
    }
  }
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'en',
    detection: {
      order: ['navigator', 'htmlTag', 'localStorage'],
      caches: ['localStorage'],
    },
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;