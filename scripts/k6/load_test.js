import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 },
    { duration: '1m', target: 50 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: __ENV.CI ? [] : ['p(95)<500'],
    http_req_failed: __ENV.CI ? [] : ['rate<0.05'],
  },
};

const BASE_URL = __ENV.SUPREMEAI_URL || 'http://127.0.0.1:8000';

// বাংলা মন্তব্য: অথেনটিকেটেড এন্ডপয়েন্টের জন্য Bearer টোকেন (locustfile-এর
// LOAD_TEST_TOKEN কনভেনশনের সাথে সঙ্গতিপূর্ণ)। /task/execute পাবলিক পাথ নয়।
const AUTH_HEADERS = {
  'Content-Type': 'application/json',
  ...( __ENV.LOAD_TEST_TOKEN
    ? { Authorization: `Bearer ${__ENV.LOAD_TEST_TOKEN}` }
    : {} ),
};

export default function () {
  let res = http.get(`${BASE_URL}/health`);
  check(res, {
    'health is 200': (r) => r.status === 200,
    'health p95 < 500ms': (r) => r.timings.duration < 500,
  });
  sleep(1);

  // বাংলা মন্তব্য: আগের `/actuator/health` কোনো রেজিস্টার্ড রুট নয় (openapi.json-এ
  // নেই) — সবসময় 404 দিত। পাবলিক লাইভনেস প্রোব `/health/live` দিয়ে বদলানো হলো।
  res = http.get(`${BASE_URL}/health/live`);
  check(res, {
    'liveness is 200': (r) => r.status === 200,
  });
  sleep(1);

  // বাংলা মন্তব্য: POST /task/execute বৈধ alias রুট (task.py:318-319), কিন্তু
  // Bearer ছাড়া 401 আসে — তাই AUTH_HEADERS পাঠানো হচ্ছে।
  res = http.post(`${BASE_URL}/task/execute`, JSON.stringify({
    task: 'health-check ping',
    task_type: 'general',
  }), { headers: AUTH_HEADERS });
  check(res, {
    'task status != 500': (r) => r.status !== 500,
  });
  sleep(2);
}
