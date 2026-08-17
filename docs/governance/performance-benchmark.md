# SupremeAI 2.0 — Performance Benchmark Config
## Load testing, latency targets, and resource limits

_Status: ACTIVE_
_Last Updated: 2026-06-22_

---

## Targets

| Metric | Target | Current |
|--------|--------|---------|
| API P95 latency | < 500 ms | TBD |
| Backend throughput | > 100 RPS | TBD |
| DB query P95 | < 50 ms | TBD |
| LLM provider failover | < 2s | TBD |
| Frontend LCP | < 2.5s | TBD |
| Frontend FID | < 100 ms | TBD |

## Tooling

| Tool | Use |
|------|-----|
| `scripts/benchmark/perf_benchmark.py` | Simple API latency benchmark |
| `k6` | Load testing (recommended for CI) |
| `prometheus_client` | In-process metrics |
| `Sentry` | APM / latency tracking |
| `Helicone` | LLM latency tracking |

## k6 Load Test Config (recommended)
```js
// scripts/benchmark/k6-load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 },
    { duration: '1m', target: 50 },
    { duration: '30s', target: 0 },
  ],
};

export default function () {
  const res = http.get('http://127.0.0.1:8000/health');
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(1);
}
```

## Runner Setup

```bash
# Install k6
# Windows: choco install k6
# Mac: brew install k6
# Linux: sudo apt-get install k6

k6 run scripts/benchmark/k6-load-test.js
k6 run --out json=scripts/benchmark/k6-results.json scripts/benchmark/k6-load-test.js
```

---

_Next Review: 2026-07-22_
