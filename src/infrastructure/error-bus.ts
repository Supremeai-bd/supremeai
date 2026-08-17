import { EventEmitter } from 'events';

export interface ErrorContext {
  module: string;
  method: string;
  error: unknown;
  payload?: any;
  timestamp: number;
}

/**
 * ErrorBus — পুরো অ্যাপ্লিকেশনের এরর ইভেন্ট আদান-প্রদানের কেন্দ্রীয় চ্যানেল।
 *
 * সিঙ্গলটন প্যাটার্ন ব্যবহার করা হয়েছে (constructor প্রাইভেট), যাতে সব মডিউল
 * একই বাস ইনস্ট্যান্স ব্যবহার করে। একাধিক ইনস্ট্যান্স থাকলে কিছু লিসেনার
 * ইভেন্ট পেত না এবং সেলফ-হিলিং প্রক্রিয়া চালু হতো না।
 */
class ErrorBus extends EventEmitter {
  private static instance: ErrorBus;

  private constructor() {
    super();
    // হাই-ট্রাফিকের সময় মেমোরি লিকের ভুল সতর্কবার্তা এড়াতে সর্বোচ্চ লিসেনার সীমা বাড়ানো হয়েছে
    this.setMaxListeners(50);
  }

  /**
   * একমাত্র ErrorBus ইনস্ট্যান্সটি ফেরত দেয়; না থাকলে প্রথমবার তৈরি করে।
   */
  public static getInstance(): ErrorBus {
    if (!ErrorBus.instance) {
      ErrorBus.instance = new ErrorBus();
    }
    return ErrorBus.instance;
  }

  /**
   * এরর ইভেন্ট ছড়িয়ে দেয় — সেলফ-হিলিং এজেন্ট ও মনিটরিং সিস্টেম এটি গ্রহণ করে।
   */
  public emitError(context: ErrorContext): void {
    this.emit('system_error', context);
  }
}

export const errorBus = ErrorBus.getInstance();
