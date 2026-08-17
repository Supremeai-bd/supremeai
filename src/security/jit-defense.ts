import * as crypto from 'crypto';
import Redis from 'ioredis';
import { config } from '../config';

// Redis ক্লায়েন্ট ইনিশিয়ালাইজেশন — JIT OTP-এর স্টেট ট্র্যাক করার জন্য ব্যবহৃত হয়
const redis = new Redis(config.REDIS_URL);

/**
 * JITDefense — সংবেদনশীল বা ধ্বংসাত্মক অ্যাকশনের আগে অতিরিক্ত সুরক্ষাস্তর
 * হিসেবে এককালীন পাসওয়ার্ড (OTP) যাচাই করে।
 */
export class JITDefense {
  /**
   * সংবেদনশীল অ্যাকশনের জন্য ৬-ডিজিটের এককালীন OTP তৈরি করে (মেয়াদ ৫ মিনিট)।
   *
   * OTP নিজেই Redis কী-এর অংশ, তাই আলাদা করে মান তুলনা করার প্রয়োজন হয় না —
   * ভুল OTP দিলে কী-টি কেবল পাওয়াই যাবে না।
   */
  static async generateOTP(userId: string, action: string): Promise<string> {
    // crypto.randomInt ব্যবহার করা হয়েছে (Math.random নয়), কারণ নিরাপত্তার
    // ক্ষেত্রে অনুমানযোগ্য এলোমেলো সংখ্যা ব্যবহার করা বিপজ্জনক
    const otp = crypto.randomInt(100000, 999999).toString();
    const key = `jit:${userId}:${action}:${otp}`;
    // ৩০০ সেকেন্ড (৫ মিনিট) পর OTP স্বয়ংক্রিয়ভাবে মেয়াদোত্তীর্ণ হয়
    await redis.set(key, 'valid', 'EX', 300);
    return otp;
  }

  /**
   * OTP যাচাই করে। প্রতিটি OTP কেবল একবারই ব্যবহারযোগ্য,
   * ফলে রিপ্লে অ্যাটাক (একই OTP পুনরায় ব্যবহার) প্রতিরোধ করা যায়।
   */
  static async verifyOTP(userId: string, action: string, otp: string): Promise<boolean> {
    const key = `jit:${userId}:${action}:${otp}`;
    const result = await redis.get(key);

    if (result === 'valid') {
      // যাচাইয়ের সাথে সাথেই কী মুছে ফেলা হয়, যাতে একই OTP দ্বিতীয়বার কাজ না করে
      await redis.del(key);
      return true;
    }
    return false;
  }
}
