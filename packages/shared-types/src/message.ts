import { z } from 'zod';

/**
 * টুল কল স্কিমা — এজেন্ট কোনো টুল চালালে সেই কলের পরিচয়, ইনপুট আর্গুমেন্ট,
 * ফলাফল এবং বর্তমান অবস্থা এখানে ধারণ করা হয়।
 */
export const ToolCallSchema = z.object({
  id: z.string(),
  name: z.string(),
  arguments: z.record(z.string(), z.unknown()),
  result: z.string().optional(),
  // status: টুলটি এখনো চলছে (pending), সফল হয়েছে (success) নাকি ব্যর্থ (error)
  status: z.enum(['pending', 'success', 'error']),
});

export type ToolCall = z.infer<typeof ToolCallSchema>;

/**
 * মেসেজ স্কিমা — কথোপকথনের একটি একক বার্তা।
 * role দিয়ে বোঝা যায় বার্তাটি ইউজার, অ্যাসিস্ট্যান্ট নাকি সিস্টেমের পক্ষ থেকে এসেছে।
 * অ্যাসিস্ট্যান্ট টুল ব্যবহার করলে সেগুলো toolCalls-এ সংযুক্ত থাকে।
 */
export const MessageSchema = z.object({
  id: z.string(),
  role: z.enum(['user', 'assistant', 'system']),
  content: z.string(),
  timestamp: z.date(),
  toolCalls: z.array(ToolCallSchema).optional(),
});

export type Message = z.infer<typeof MessageSchema>;
