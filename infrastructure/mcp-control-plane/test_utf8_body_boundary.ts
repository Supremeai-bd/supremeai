/**
 * UTF-8 request-body boundary regression (pure, offline).
 * House style: tsx script, hard asserts, exit code = verdict.
 *
 * লাইভ ঘটনা (2026-11-26): bridge_submit_patch-এ ~৮০ KB JSON পাঠানোর সময়
 * ঠিক 65536-বাইট সীমায় থাকা একটা বাংলা অক্ষর ('ু', 3 বাইট) Tower-এ
 * U+FFFD ×3 হয়ে যায় — কারণ `/mcp` হ্যান্ডলার `body += chunk.toString()`
 * করে, আর chunk-সীমায় ভাঙা বহু-বাইট অক্ষর আলাদা আলাদা decode হয়।
 * কমিট হওয়া প্যাচ ফাইলটা নিঃশব্দে নষ্ট হয়েছিল (supremeai PR #857)।
 * সমাধান: প্রতিটা body-reader-এর আগে `req.setEncoding("utf8")`।
 */
import { readFileSync } from "node:fs";
import { PassThrough } from "node:stream";

let failures = 0;
function check(name: string, cond: boolean, detail?: string): void {
  if (cond) {
    console.log(`  ✓ ${name}`);
  } else {
    failures += 1;
    console.error(`  ✗ ${name}${detail ? ` — ${detail}` : ""}`);
  }
}
function section(title: string): void {
  console.log(`\n=== ${title} ===`);
}

/** chunk-সীমা ঠিক একটা বহু-বাইট অক্ষরের মাঝখানে রেখে body পড়া। */
async function readSplitBody(useSetEncoding: boolean): Promise<string> {
  const payload = JSON.stringify({ text: "a".repeat(65_525) + "নথিভুক্ত" });
  const bytes = Buffer.from(payload, "utf8");
  const charStart = bytes.indexOf(Buffer.from("ু", "utf8"));
  const req = new PassThrough();
  if (useSetEncoding) req.setEncoding("utf8");
  let body = "";
  req.on("data", (chunk: string | Buffer) => {
    body += chunk.toString();
  });
  const done = new Promise<void>((resolve) => req.on("end", () => resolve()));
  req.write(bytes.subarray(0, charStart + 1)); // 'ু'-এর ১ম বাইটে কাটা
  req.write(bytes.subarray(charStart + 1));
  req.end();
  await done;
  return body;
}

async function main(): Promise<void> {
  section("behaviour: split multi-byte char across chunks");
  const broken = await readSplitBody(false);
  check("control: naive Buffer→string concat corrupts the char (bug reproduced)", broken.includes("\uFFFD"));
  const fixed = await readSplitBody(true);
  check("setEncoding('utf8') keeps the char intact", !fixed.includes("\uFFFD"));
  check("setEncoding('utf8') body round-trips as JSON", JSON.parse(fixed).text.endsWith("নথিভুক্ত"));

  section("static guard: every body reader in src/http_server.ts decodes as UTF-8");
  const lines = readFileSync(new URL("./src/http_server.ts", import.meta.url), "utf8").split("\n");
  const readers = lines
    .map((line, i) => ({ line, i }))
    .filter(({ line }) => /\breq\.on\(\s*["']data["']/.test(line));
  check("found body readers to guard", readers.length > 0, `found ${readers.length}`);
  for (const { i } of readers) {
    const window = lines.slice(Math.max(0, i - 3), i).join("\n");
    check(
      `http_server.ts:${i + 1} has req.setEncoding("utf8") right before req.on("data")`,
      /req\.setEncoding\(\s*["']utf-?8["']\s*\)/.test(window)
    );
  }

  console.log(`\n${failures === 0 ? "PASS" : "FAIL"} — ${failures} failure(s)`);
  process.exit(failures === 0 ? 0 : 1);
}

void main();
