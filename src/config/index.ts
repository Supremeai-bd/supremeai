import * as dotenv from 'dotenv';
dotenv.config();

// বাংলা মন্তব্য: অ্যাপ্লিকেশনের কোর কনফিগারেশন ইন্টারফেস
export interface AppConfig {
  PORT: number;
  DB_URI: string;
  REDIS_URL: string;
  JIT_OTP_SECRET: string;
}

/**
 * অ্যাপ্লিকেশনের কনফিগারেশন লোড করে এবং বৈধতা যাচাই করে।
 *
 * "Anti-Silent Failure" নীতি: প্রয়োজনীয় কোনো এনভায়রনমেন্ট ভেরিয়েবল অনুপস্থিত
 * থাকলে অ্যাপ চালু হওয়ার সময়েই এরর ছুঁড়ে বন্ধ হয়ে যায়। এতে ভুল কনফিগ নিয়ে
 * সার্ভিস চালু হয়ে পরে রানটাইমে রহস্যজনকভাবে ব্যর্থ হওয়ার ঝুঁকি এড়ানো যায়।
 */
const loadConfig = (): AppConfig => {
  const requiredVars = ['DB_URI', 'REDIS_URL', 'JIT_OTP_SECRET'];
  const missing = requiredVars.filter((v) => !process.env[v]);

  // একসাথে সব অনুপস্থিত ভেরিয়েবলের নাম জানানো হয়, যাতে ডেভেলপারকে
  // একটি একটি করে ঠিক করে বারবার রিস্টার্ট করতে না হয়
  if (missing.length > 0) {
    throw new Error(`[FATAL] Missing critical environment variables: ${missing.join(', ')}`);
  }

  return {
    // PORT ঐচ্ছিক — না দিলে ডিফল্ট ৩০০০ ব্যবহৃত হয়
    PORT: parseInt(process.env.PORT || '3000', 10),
    // নিচের মানগুলোতে non-null assertion (!) নিরাপদ, কারণ উপরে
    // এগুলোর উপস্থিতি ইতিমধ্যেই যাচাই করা হয়েছে
    DB_URI: process.env.DB_URI!,
    REDIS_URL: process.env.REDIS_URL!,
    JIT_OTP_SECRET: process.env.JIT_OTP_SECRET!,
  };
};

export const config = loadConfig();
