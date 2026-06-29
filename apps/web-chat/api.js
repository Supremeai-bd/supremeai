// apps/web-chat/api.js

export const api = {
    // টাস্ক এক্সিকিউট এবং হিস্ট্রি পাঠানো
    async executeTask(task, messages, taskType = 'general') {
        try {
            const response = await fetch('/task/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task: task,
                    task_type: taskType,
                    messages: messages // কনটেক্সট ধরে রাখার জন্য হিস্ট্রি পাঠানো হচ্ছে
                })
            });
            
            if (!response.ok) throw new Error('API Response Error');
            return await response.json();
        } catch (error) {
            console.error('Task Execution Failed:', error);
            return { result: null, error: error.message };
        }
    },

    // Redis থেকে রিয়েল-টাইম কোটা ফেচ করা (Mocking for now based on your architecture)
    async fetchQuota() {
        // TODO: Replace with actual endpoint e.g., fetch('/api/quota')
        return new Promise((resolve) => setTimeout(() => resolve({ remaining: 87 }), 500));
    }
};
