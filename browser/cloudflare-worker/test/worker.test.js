import { test } from "node:test";
import assert from "node:assert/strict";
import puppeteer from "@cloudflare/puppeteer";
import worker from "../src/index.js";

const env = { SUPREMEAI_WORKER_TOKEN: "test-token", MYBROWSER: { binding: true } };
const request = (url, token = "test-token") => new Request(url, {
  headers: token ? { authorization: `Bearer ${token}` } : {},
});

test("health and authentication do not start a browser", async () => {
  const original = puppeteer.launch;
  puppeteer.launch = () => { throw new Error("unexpected browser launch"); };
  try {
    assert.equal((await worker.fetch(request("https://worker.test/health", ""), {})).status, 200);
    assert.equal((await worker.fetch(request("https://worker.test/?url=https://example.com", ""), env)).status, 401);
    assert.equal((await worker.fetch(request("https://worker.test/?url=https://example.com"), {})).status, 503);
    assert.equal((await worker.fetch(request("https://worker.test/?url=http://127.0.0.1"), env)).status, 403);
  } finally {
    puppeteer.launch = original;
  }
});

test("successful request uses Browser Run binding and closes the browser", async () => {
  const original = puppeteer.launch;
  const calls = [];
  const page = {
    async setRequestInterception(enabled) { calls.push(["interception", enabled]); },
    on(event, handler) { calls.push([event, handler]); },
    async goto(url, options) { calls.push(["goto", url, options]); },
    async title() { return "Example"; },
    async evaluate() { return "Example text"; },
  };
  puppeteer.launch = async (binding) => {
    calls.push(["launch", binding]);
    return { async newPage() { return page; }, async close() { calls.push(["close"]); } };
  };
  try {
    const response = await worker.fetch(request("https://worker.test/?url=https%3A%2F%2Fexample.com%2F"), env);
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { success: true, url: "https://example.com/", title: "Example", content: "Example text" });
    assert.equal(calls[0][1], env.MYBROWSER);
    assert.deepEqual(calls.find((c) => c[0] === "interception"), ["interception", true]);
    assert.deepEqual(calls.find((c) => c[0] === "goto"), ["goto", "https://example.com/", { waitUntil: "domcontentloaded", timeout: 15000 }]);
    const handler = calls.find((c) => c[0] === "request")[1];
    let action;
    handler({ resourceType: () => "image", abort: () => { action = "abort"; } });
    assert.equal(action, "abort");
    handler({ resourceType: () => "document", continue: () => { action = "continue"; } });
    assert.equal(action, "continue");
    assert.equal(calls.filter((c) => c[0] === "close").length, 1);
  } finally {
    puppeteer.launch = original;
  }
});

test("browser errors close the session without disclosing exception details", async () => {
  const original = puppeteer.launch;
  let closed = false;
  puppeteer.launch = async () => ({
    async newPage() { throw new Error("sensitive detail"); },
    async close() { closed = true; },
  });
  try {
    const response = await worker.fetch(request("https://worker.test/?url=https://example.com"), env);
    assert.equal(response.status, 500);
    assert.equal((await response.json()).error, "browser operation failed");
    assert.equal(closed, true);
  } finally {
    puppeteer.launch = original;
  }
});

test("cleanup failure is reported without leaking browser exception data", async () => {
  const originalLaunch = puppeteer.launch;
  const originalError = console.error;
  const messages = [];
  console.error = (...args) => messages.push(args.join(" "));
  puppeteer.launch = async () => ({
    async newPage() { throw new Error("private operation detail"); },
    async close() { throw new Error("private cleanup detail"); },
  });
  try {
    const response = await worker.fetch(request("https://worker.test/?url=https://example.com"), env);
    assert.equal(response.status, 500);
    assert.equal((await response.json()).error, "browser operation failed");
    assert.deepEqual(messages, ["Browser operation failed", "Browser cleanup failed"]);
    assert.ok(!messages.join(" ").includes("private"));
  } finally {
    puppeteer.launch = originalLaunch;
    console.error = originalError;
  }
});
