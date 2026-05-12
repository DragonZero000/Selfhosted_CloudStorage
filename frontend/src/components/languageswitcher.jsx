import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe } from 'lucide-react';
import '../styles/languageswitcher.css';

const LanguageSwitcher = () => {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const changeLanguage = (lng) => {
    i18n.changeLanguage(lng);
    setIsOpen(false);
  };

  return (
    <div className="languageSwitcher">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="btn"
      >
        <Globe size={20} />
        <span className="text-sm uppercase font-medium">{i18n.language}</span>
      </button>

      {isOpen && (
        <div className="dropdown">
          <button
            onClick={() => changeLanguage('ru')}
            className="dropdownItem"
          >
            🇷🇺 Русский
          </button>
          <button
            onClick={() => changeLanguage('en')}
            className="dropdownItem"
          >
            🇬🇧 English
          </button>
        </div>
      )}

      {isOpen && <div className="overlay" onClick={() => setIsOpen(false)} />}
    </div>
  );
};

export default LanguageSwitcher;