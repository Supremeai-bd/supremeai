// ============================================================================
// file >> useTranslation.ts
// project >> SupremeAI 2.0
// purpose >> General utility
// module >> src
// ============================================================================
import { translations } from '../i18n/translations';

export function useTranslation(locale: Locale = 'en') {
  const t = (key: keyof typeof translations.en) => {
    const current = locales.includes(locale) ? locale : 'en';
    return translations[current][key] ?? translations.en[key] ?? key;
  };

  return { t, locale, setLocale: (_next: Locale) => {} };
}
