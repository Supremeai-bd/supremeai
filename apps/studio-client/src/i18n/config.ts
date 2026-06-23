// ============================================================================
// file >> config.ts
// project >> SupremeAI 2.0
// purpose >> Configuration loading
// module >> src
// ============================================================================
export type Locale = (typeof locales)[number];

export const localeNames: Record<Locale, string> = {
  en: 'English',
  bn: 'Bengali',
  es: 'Spanish',
  zh: 'Chinese',
};
