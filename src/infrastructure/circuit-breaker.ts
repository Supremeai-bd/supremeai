import Redis from 'ioredis';
import { config } from '../config';

const redis = new Redis(config.REDIS_URL);

export type CircuitState = 'CLOSED' | 'OPEN' | 'HALF_OPEN';

export interface CircuitOptions {
  failureThreshold: number;
  resetTimeout: number;
}

/**
 * সার্কিট ব্রেকার — বারবার ব্যর্থ হওয়া সার্ভিসে কল পাঠানো সাময়িকভাবে বন্ধ করে,
 * যাতে ইতিমধ্যেই সমস্যাগ্রস্ত সার্ভিসের ওপর বাড়তি চাপ না পড়ে।
 *
 * স্টেট Redis-এ রাখা হয়, ফলে একাধিক সার্ভার ইনস্ট্যান্স একই সার্কিট স্টেট
 * ভাগ করে নিতে পারে (ডিস্ট্রিবিউটেড সার্কিট ব্রেকার)।
 */
export class CircuitBreaker {
  private readonly key: string;
  private readonly options: CircuitOptions;

  constructor(serviceName: string, options?: Partial<CircuitOptions>) {
    this.key = `circuit:${serviceName}`;
    this.options = {
      failureThreshold: options?.failureThreshold || 5, // ৫ বার ব্যর্থ হলে সার্কিট খুলে যায়
      resetTimeout: options?.resetTimeout || 30000, // ৩০ সেকেন্ড পর পুনরায় চেষ্টার সুযোগ
    };
  }

  /**
   * সার্কিট ব্রেকারের বর্তমান স্টেট নির্ণয় করে।
   *
   * ডিস্ট্রিবিউটেড Redis কী ব্যবহার করে CLOSED, OPEN বা HALF_OPEN স্টেট নির্ধারিত হয়:
   *   CLOSED    — ব্যর্থতা সীমার নিচে, সব কল স্বাভাবিকভাবে যেতে দেওয়া হয়।
   *   OPEN      — সীমা অতিক্রান্ত এবং রিসেট সময় এখনো শেষ হয়নি, তাই কল ব্লক।
   *   HALF_OPEN — রিসেট সময় পার হয়েছে; সার্ভিস সেরে উঠেছে কি না তা যাচাই করতে
   *               পরীক্ষামূলকভাবে কল যেতে দেওয়া হয়।
   */
  private async getState(): Promise<{ state: CircuitState; failures: number }> {
    const failures = parseInt(await redis.get(this.key) || '0', 10);
    const lastFailureTime = parseInt(await redis.get(`${this.key}:time`) || '0', 10);

    if (failures >= this.options.failureThreshold) {
      const timeSinceLastFailure = Date.now() - lastFailureTime;
      if (timeSinceLastFailure > this.options.resetTimeout) {
        return { state: 'HALF_OPEN', failures };
      }
      return { state: 'OPEN', failures };
    }
    return { state: 'CLOSED', failures };
  }

  /**
   * একটি ব্যর্থতা নথিভুক্ত করে।
   * MULTI ব্যবহার করা হয়েছে যাতে কাউন্টার বৃদ্ধি ও সময় সংরক্ষণ একসাথে (atomically)
   * সম্পন্ন হয় — নাহলে একাধিক সার্ভার একসাথে লিখলে স্টেট অসামঞ্জস্যপূর্ণ হতে পারে।
   */
  public async recordFailure(): Promise<void> {
    const multi = redis.multi();
    multi.incr(this.key);
    multi.set(`${this.key}:time`, Date.now().toString());
    // ৩০০ সেকেন্ড পর কী স্বয়ংক্রিয়ভাবে মুছে যায়, ফলে পুরোনো ব্যর্থতা
    // অনির্দিষ্টকাল ধরে সার্কিট খোলা রাখতে পারে না
    multi.expire(this.key, 300);
    await multi.exec();
  }

  /**
   * সফল কলের পর সব ব্যর্থতার হিসাব মুছে ফেলে, অর্থাৎ সার্কিট আবার CLOSED হয়।
   */
  public async recordSuccess(): Promise<void> {
    await redis.del(this.key);
    await redis.del(`${this.key}:time`);
  }

  /**
   * এই মুহূর্তে সার্ভিসে কল পাঠানো যাবে কি না তা জানায়।
   * HALF_OPEN অবস্থায়ও অনুমতি দেওয়া হয়, কারণ সার্ভিস সেরে উঠেছে কি না
   * তা পরীক্ষা করার জন্য অন্তত একটি কল পাঠানো প্রয়োজন।
   */
  public async canExecute(): Promise<boolean> {
    const { state } = await this.getState();
    return state === 'CLOSED' || state === 'HALF_OPEN';
  }
}
