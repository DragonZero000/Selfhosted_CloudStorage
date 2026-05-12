import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe } from 'lucide-react';

const LanguageSwitcher = () => {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const changeLanguage = (lng) => {
    i18n.changeLanguage(lng);
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors flex items-center gap-1"
      >
        <Globe size={20} />
        <span className="text-sm uppercase font-medium">{i18n.language}</span>
      </button>

      {isOpen && (
        <div className="absolute right-0 bottom-full mb-2 w-44 bg-white dark:bg-gray-800 rounded-lg shadow-xl py-1 z-50 border border-gray-200 dark:border-gray-700">
          <button
            onClick={() => changeLanguage('ru')}
            className="w-full text-left px-4 py-2.5 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3"
          >
            🇷🇺 Русский
          </button>
          <button
            onClick={() => changeLanguage('en')}
            className="w-full text-left px-4 py-2.5 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3"
          >
            🇬🇧 English
          </button>
        </div>
      )}

      {isOpen && <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />}
    </div>
  );
};

export default LanguageSwitcher;