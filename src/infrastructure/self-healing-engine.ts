import { errorBus } from './error-bus';
import Redis from 'ioredis';
import { config } from '../config';

const redis = new Redis(config.REDIS_URL);

export interface HealableOperation {
  module: string;
  method: string;
  operation: () => Promise<any>;
}

/**
 * সেলফ-হিলিং ইঞ্জিন — সিস্টেমে কোনো এরর ঘটলে স্বয়ংক্রিয়ভাবে সেটি
 * পুনরায় চালানোর (retry) চেষ্টা করে, মানুষের হস্তক্ষেপ ছাড়াই।
 */
class SelfHealingEngine {
  // সর্বোচ্চ কতবার একটি অপারেশন পুনরায় চেষ্টা করা হবে
  private maxRetries: number = 3;

  constructor() {
    this.listenForErrors();
  }

  /**
   * errorBus-এর ইভেন্ট শোনে এবং এক্সপোনেনশিয়াল ব্যাকঅফ দিয়ে অটো-রিট্রাই চালায়।
   *
   * ব্যর্থতার সংখ্যা Redis-এ রাখা হয়, তাই একাধিক সার্ভার ইনস্ট্যান্স থাকলেও
   * একই অপারেশন মিলিতভাবে সর্বোচ্চ maxRetries বার চেষ্টা করা হয়।
   */
  private listenForErrors(): void {
    errorBus.on('system_error', async (context) => {
      const failureKey = `failure:${context.module}:${context.method}`;
      const failureCount = await this.incrementFailureHistory(failureKey);

      if (failureCount < this.maxRetries) {
        // এক্সপোনেনশিয়াল ব্যাকঅফ (১ সে., ২ সে., ৪ সে. ...) — প্রতিবার অপেক্ষার সময়
        // দ্বিগুণ হয়, ফলে সমস্যাগ্রস্ত সার্ভিসকে সেরে ওঠার অবকাশ দেওয়া হয়
        const delay = Math.pow(2, failureCount - 1) * 1000;
        setTimeout(() => this.executeHealableOperation({
          module: context.module,
          method: context.method,
          operation: context.payload?.retryLogic,
        }), delay);
      } else {
        // সর্বোচ্চ চেষ্টা শেষ — কাউন্টার রিসেট করে সমস্যাটি মানুষের কাছে পাঠানো হয়
        await redis.del(failureKey);
        // এস্কেলেশন: অ্যাডমিনকে JIT নোটিফিকেশন পাঠানোর ধাপ
        console.error(`[Self-Healing] Max retries reached for ${context.method}. Escalating.`);
      }
    });
  }

  /**
   * নির্দিষ্ট অপারেশনের ব্যর্থতার সংখ্যা এক ধাপ বাড়িয়ে নতুন মান ফেরত দেয়।
   */
  private async incrementFailureHistory(key: string): Promise<number> {
    const count = await redis.incr(key);
    // কেবল প্রথমবার মেয়াদ নির্ধারণ করা হয়; প্রতিবার করলে কী কখনো মেয়াদোত্তীর্ণ হতো না।
    // ১০ মিনিট পর হিসাব মুছে যায়, যাতে অনেক আগের ব্যর্থতা নতুন চেষ্টাকে বাধা না দেয়।
    if (count === 1) await redis.expire(key, 600);
    return count;
  }

  /**
   * কোনো অপারেশন চালায় এবং ব্যর্থ হলে সেটিকে errorBus-এ পাঠিয়ে দেয়,
   * যাতে উপরের রিট্রাই প্রক্রিয়া স্বয়ংক্রিয়ভাবে শুরু হতে পারে।
   */
  public async executeHealableOperation(op: HealableOperation): Promise<any> {
    try {
      const result = await op.operation();
      // সফল হলে পূর্বের ব্যর্থতার হিসাব মুছে ফেলা হয়
      await redis.del(`failure:${op.module}:${op.method}`);
      return result;
    } catch (error) {
      // মূল অপারেশনটি payload-এ পাঠানো হয়, যাতে রিট্রাইয়ের সময় সেটি পুনরায় চালানো যায়
      errorBus.emitError({
        module: op.module,
        method: op.method,
        error,
        payload: { retryLogic: op.operation },
        timestamp: Date.now()
      });
      return null;
    }
  }
}

export const selfHealingEngine = new SelfHealingEngine();
