// ============================================================================
// file >> load_test.js
// project >> SupremeAI 2.0
// purpose >> Unit testing and QC
// module >> scripts
// ============================================================================
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 },
    { duration: '1m', target: 50 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.05'],
  },
};

const BASE_URL = __ENV.SUPREMEAI_URL || 'http://127.0.0.1:8000';

export default function () {
  let res = http.get(`${BASE_URL}/health`);
  check(res, {
    'health is 200': (r) => r.status === 200,
    'health p95 < 500ms': (r) => r.timings.duration < 500,
  });
  sleep(1);

  res = http.get(`${BASE_URL}/actuator/health`);
  check(res, {
    'actuator is 200': (r) => r.status === 200,
  });
  sleep(1);

  res = http.post(`${BASE_URL}/task/execute`, JSON.stringify({
    task: 'health-check ping',
    task_type: 'general',
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
  check(res, {
    'task status != 500': (r) => r.status !== 500,
  });
  sleep(2);
}
