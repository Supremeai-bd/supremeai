import { ResilientExecutor } from '../infrastructure/resilient-executor';
import { JITDefense } from '../security/jit-defense';

/**
 * ExternalApiService — বাইরের API কল করার সময় রেজিলিয়েন্ট এক্সিকিউটর ও
 * JIT OTP যাচাই কীভাবে ব্যবহার করতে হয় তার বাস্তব উদাহরণ।
 */
export class ExternalApiService {
  /**
   * জরুরি ডেটা আনে। সার্ভিস ব্যর্থ হলে বা সার্কিট খোলা থাকলে
   * এক্সেপশন না ছুঁড়ে 'degraded' অবস্থা ফেরত দেয় (graceful degradation),
   * ফলে একটি সার্ভিসের ব্যর্থতায় পুরো পেজ ভেঙে পড়ে না।
   */
  static async fetchCriticalData(userId: string): Promise<any> {
    return ResilientExecutor.run(
      'ExternalApiService',
      async () => {
        const response = await fetch(`https://free-api.example.com/data/${userId}`);
        // ব্যর্থ HTTP স্ট্যাটাসে ইচ্ছাকৃতভাবে এরর ছোঁড়া হয়, যাতে সার্কিট ব্রেকার
        // এটিকে ব্যর্থতা হিসেবে গণনা করতে পারে
        if (!response.ok) throw new Error(`API failed with status ${response.status}`);
        return response.json();
      },
      // ফলব্যাক: ডেটা না পেলে সিস্টেম আংশিক সচল অবস্থায় চলতে থাকে
      async () => ({ data: null, status: 'degraded' })
    );
  }

  /**
   * ধ্বংসাত্মক (destructive) রুটে JIT ডিফেন্স প্রয়োগের উদাহরণ।
   * OTP যাচাই ব্যর্থ হলে ডিলিট করার কোনো কোড চালানোর আগেই কাজটি বাতিল হয়।
   */
  static async deleteUserData(adminId: string, userId: string, otp: string): Promise<boolean> {
    const isValid = await JITDefense.verifyOTP(adminId, 'DELETE_USER', otp);
    if (!isValid) throw new Error('JIT OTP Verification Failed');

    // এরপর প্রকৃত ডিলিট করার লজিক সম্পন্ন হয়...
    return true;
  }
}
