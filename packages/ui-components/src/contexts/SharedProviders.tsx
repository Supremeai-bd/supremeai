import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// QueryClient ইচ্ছাকৃতভাবে কম্পোনেন্টের বাইরে (মডিউল স্কোপে) তৈরি করা হয়েছে।
// কম্পোনেন্টের ভেতরে তৈরি করলে প্রতিবার রি-রেন্ডারে নতুন ক্লায়েন্ট তৈরি হতো
// এবং পুরো ক্যাশ মুছে গিয়ে অপ্রয়োজনীয় রি-ফেচ হতো।
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1, // ব্যর্থ হলে একবারই পুনরায় চেষ্টা — বেশি রিট্রাই ব্যাকএন্ডে চাপ বাড়ায়
      refetchOnWindowFocus: false, // ট্যাব বদলালেই যেন অকারণে ডেটা রি-ফেচ না হয়
    },
  },
});

/**
 * SharedProviders — একাধিক অ্যাপে (স্টুডিও, ডেস্কটপ) ব্যবহারের জন্য
 * সাধারণ কনটেক্সট প্রোভাইডারগুলোকে একত্রে মোড়ানো হয়েছে।
 * নতুন গ্লোবাল প্রোভাইডার যুক্ত করতে হলে এখানেই যোগ করতে হবে।
 */
export const SharedProviders: React.FC<{children: React.ReactNode}> = ({ children }) => {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

export default SharedProviders;
