/// <reference types="vite/client" />

/**
 * ব্যাকএন্ড API-এর বেস URL নির্ধারণ করে।
 *
 * অগ্রাধিকার ক্রম অনুসারে URL বাছাই করা হয়:
 *   ১. সার্ভার-সাইড রেন্ডারিং (window অনুপস্থিত) — এনভায়রনমেন্ট ভেরিয়েবল,
 *      কোনোটিই না থাকলে সর্বশেষ উপায় হিসেবে লোকালহোস্ট।
 *   ২. VITE_API_BASE — স্পষ্টভাবে নির্ধারিত বেস URL।
 *   ৩. VITE_API_URL — পুরোনো নামকরণের সাথে সামঞ্জস্য রক্ষার জন্য।
 *   ৪. window.location.origin — একই ডোমেইন থেকে API সার্ভ হলে প্রযোজ্য।
 *
 * ব্রাউজারে window.origin-কে সর্বশেষে রাখা হয়েছে, কারণ এনভায়রনমেন্ট
 * ভেরিয়েবল থাকলে সেটিই সবসময় অগ্রাধিকার পাওয়া উচিত।
 */
export const getApiBaseUrl = (): string => {
  // SSR বা বিল্ড-টাইমে window থাকে না, তাই কেবল env ভেরিয়েবলের ওপর নির্ভর করতে হয়
  if (typeof window === 'undefined') {
    return import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_URL || 'http://localhost:8000';
  }

  if (import.meta.env.VITE_API_BASE) {
    return import.meta.env.VITE_API_BASE;
  }

  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }

  return window.location.origin;
};
