export default {
  // ==========================================
  // কাজ ১: Load Balancer + Health Dashboard
  // ==========================================
  async fetch(request, env, ctx) {
    const services = {
      primary: env.PRIMARY_URL || "https://supremeai-backend.onrender.com",
      admin: env.ADMIN_URL || "https://supremeai-admin.onrender.com",
      backup: env.BACKUP_URL || "https://supremeai-studio-client.onrender.com",
    };

    const results = await Promise.allSettled(
      Object.entries(services).map(async ([name, url]) => {
        const alive = await this.pingWithRetry(url, 2);
        return { name, url, alive };
      })
    );

    const statuses = results.map(r =>
      r.status === "fulfilled" ? r.value : { alive: false, error: r.reason?.message }
    );
    const allAlive = statuses.every(s => s.alive);

    return new Response(JSON.stringify({
      status: allAlive ? "UP" : "DEGRADED",
      timestamp: new Date().toISOString(),
      services: statuses,
    }), {
      status: allAlive ? 200 : 503,
      headers: { "Content-Type": "application/json" },
    });
  },

  // ==========================================
  // কাজ ২: Keep-Alive Ping (প্রতি ৩ মিনিটে একাধিক সার্ভিস - More Aggressive)
  // ==========================================
  async scheduled(event, env, ctx) {
    const targets = [
      env.PRIMARY_URL || "https://supremeai-backend.onrender.com/health",
      env.ADMIN_URL || "https://supremeai-admin.onrender.com/health",
      env.BACKUP_HEALTH || "https://supremeai-studio-client.onrender.com/api/v1/health",
    ];

    // বাংলা মন্তব্য: ঘুমন্ত Render সার্ভার ৩০-৫০ সেকেন্ডে ওয়েক আপ করে। তাই পিংগুলো বুট উইন্ডো জুড়ে ছড়িয়ে দেওয়া হলো:
    // প্রথম পিং → ~২৫ সেকেন্ড অপেক্ষা → দ্বিতীয় পিং, যাতে ওয়েক-আপ সম্পূর্ণ হয় এবং অন্তত একটি পিং সফল হয়।
    const results = [];
    for (const url of targets) {
      const result1 = await this.pingWithRetry(url, 1);
      results.push({ url, attempt: 1, success: result1 });
      await this.sleep(25000);
      const result2 = await this.pingWithRetry(url, 1);
      results.push({ url, attempt: 2, success: result2 });
    }

    const successfulPings = results.filter(r => r.success).length;
    const totalPings = results.length;
    console.log(`✅ KeepAlive: ${successfulPings}/${totalPings} pings successful at ${new Date().toISOString()}`);

    // Log individual service status
    const serviceStats = {};
    results.forEach(r => {
      const serviceName = this.extractServiceName(r.url);
      if (!serviceStats[serviceName]) {
        serviceStats[serviceName] = { total: 0, success: 0 };
      }
      serviceStats[serviceName].total++;
      if (r.success) serviceStats[serviceName].success++;
    });

    Object.entries(serviceStats).forEach(([name, stats]) => {
      console.log(`📊 ${name}: ${stats.success}/${stats.total} pings successful`);
    });
  },

  // Helper to extract service name from URL
  extractServiceName(url) {
    if (url.includes('supremeai-backend')) return 'Primary';
    if (url.includes('supremeai-admin')) return 'Admin';
    if (url.includes('supremeai-studio-client')) return 'Backup';
    return 'Unknown';
  },

  // ==========================================
  // Helper: Sleep function for delays
  // ==========================================
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  },

  // ==========================================
  // Helper: Retry logic with exponential backoff
  // ==========================================
  async pingWithRetry(url, maxRetries = 2) {
    for (let i = 0; i < maxRetries; i++) {
      try {
        const response = await fetch(url, {
          headers: { "User-Agent": "Cloudflare-KeepAlive-Worker/2.0 (Aggressive)" },
          // বাংলা মন্তব্য: Render কোল্ড স্টার্ট ৩০-৫০ সেকেন্ড, তাই ৬০ সেকেন্ড টাইমআউট দিতে হবে
          signal: AbortSignal.timeout(60000),
        });
        if (response.ok) return true;
        console.warn(`⚠️ Ping ${url} returned ${response.status}, retry ${i + 1}/${maxRetries}`);
      } catch (error) {
        console.error(`❌ Ping ${url} failed: ${error.message}, retry ${i + 1}/${maxRetries}`);
      }
      if (i < maxRetries - 1) {
        await this.sleep(1000 * (i + 1));
      }
    }
    return false;
  },
};
