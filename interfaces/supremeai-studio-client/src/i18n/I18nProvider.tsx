import { createContext, useContext } from 'react';
import { useTranslation } from '../hooks/useTranslation';

export const I18nContext = createContext({ t: (key: string) => key, locale: 'en', setLocale: (_next: string) => {} } satisfies Record<string, any>);

export const TranslationProvider = ({ locale: _locale, children }: { locale: string; children: React.ReactNode }) => {
  const { t, setLocale } = useTranslation(locale || 'en');
  return (
    <I18nContext.Provider value={{ t: t as any, locale: locale || 'en', setLocale: setLocale as any }}>
      {children}
    </I18nContext.Provider>
  );
};

export const useI18n = () => useContext(I18nContext);
