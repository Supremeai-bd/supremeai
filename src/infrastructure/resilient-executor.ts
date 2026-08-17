import { CircuitBreaker } from './circuit-breaker';
import { selfHealingEngine } from './self-healing-engine';

/**
 * ResilientExecutor — সার্কিট ব্রেকার, সেলফ-হিলিং রিট্রাই এবং নিরাপদ ফলব্যাক
 * একত্রে যুক্ত করে বাইরের সার্ভিস কল নিরাপদে চালানোর কেন্দ্রীয় এক্সিকিউটর।
 *
 * তিন স্তরের সুরক্ষা:
 *   ১. সার্কিট খোলা থাকলে কল একেবারেই পাঠানো হয় না (দ্রুত ব্যর্থতা)।
 *   ২. কল ব্যর্থ হলে পটভূমিতে স্বয়ংক্রিয় রিট্রাই শুরু হয়।
 *   ৩. যেকোনো ব্যর্থতায় ফলব্যাক থাকলে সেটি ব্যবহার করা হয়।
 */
export class ResilientExecutor {
  static async run(
    serviceName: string,
    operation: () => Promise<any>,
    fallback?: () => Promise<any>
  ): Promise<any> {
    const circuit = new CircuitBreaker(serviceName);

    // সার্কিট OPEN থাকলে সার্ভিসে কল না পাঠিয়ে সরাসরি ফলব্যাক দেওয়া হয়,
    // এতে ব্যর্থ সার্ভিসের ওপর অতিরিক্ত চাপ পড়ে না
    const isAllowed = await circuit.canExecute();
    if (!isAllowed) {
      if (fallback) return fallback();
      return null;
    }

    try {
      const result = await operation();
      // সফল হলে সার্কিট রিসেট হয়ে আবার স্বাভাবিক (CLOSED) অবস্থায় ফেরে
      await circuit.recordSuccess();
      return result;
    } catch (error) {
      await circuit.recordFailure();

      // পটভূমিতে রিট্রাই শুরু করা হয় — ইচ্ছাকৃতভাবে await করা হয়নি,
      // কারণ কলকারীকে অপেক্ষা না করিয়ে দ্রুত ফলব্যাক ফেরত দেওয়া প্রয়োজন
      selfHealingEngine.executeHealableOperation({
        module: serviceName,
        method: 'auto-retry',
        operation
      });

      if (fallback) return fallback();
      return null;
    }
  }
}
