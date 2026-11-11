// 运行：node --test plugins/gemini-video/skills/gemini-video/scripts/review-video.test.mjs
// 全部测试只访问本机的模拟服务，不调用真实的 Gemini API，文件只写临时目录。

import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import { buildInteractionBody, extractText, parseCli, reviewVideo, UsageError } from "./review-video.mjs";

const dir = mkdtempSync(join(tmpdir(), "gemini-video-test-"));
const video = join(dir, "clip.mp4");
writeFileSync(video, Buffer.alloc(64, 1));

let server;
let base;
let calls;
let failInteraction = false;

before(async () => {
  server = createServer((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      const body = Buffer.concat(chunks);
      calls.push({ method: req.method, url: req.url, headers: req.headers, body });
      const json = (status, data, headers = {}) => { res.writeHead(status, { "content-type": "application/json", ...headers }); res.end(JSON.stringify(data)); };
      if (req.method === "POST" && req.url === "/upload/v1beta/files") return json(200, {}, { "x-goog-upload-url": `${base}/upload-session` });
      if (req.method === "POST" && req.url === "/upload-session") return json(200, { file: { name: "files/abc", uri: `${base}/v1beta/files/abc`, mimeType: "video/mp4", state: "PROCESSING" } });
      if (req.method === "GET" && req.url === "/v1beta/files/abc") return json(200, { name: "files/abc", uri: `${base}/v1beta/files/abc`, mimeType: "video/mp4", state: "ACTIVE" });
      if (req.method === "POST" && req.url === "/v1beta/interactions") {
        if (failInteraction) return json(429, { error: { message: "quota exceeded" } });
        return json(200, { status: "completed", steps: [{ type: "thought" }, { type: "model_output", content: [{ type: "text", text: "00:03 转场生硬" }] }], usage: { total_tokens: 1234 } });
      }
      if (req.method === "DELETE" && req.url === "/v1beta/files/abc") return json(200, {});
      return json(404, { error: { message: "not found" } });
    });
  });
  await new Promise((done) => server.listen(0, "127.0.0.1", done));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(() => {
  server.close();
  rmSync(dir, { recursive: true, force: true });
});

const env = () => ({ GEMINI_API_KEY: "test-key", GEMINI_API_BASE: base, GEMINI_VIDEO_POLL_MS: "1" });

test("完整流程：上传、等待、分析、删除", async () => {
  calls = []; failInteraction = false;
  const result = await reviewVideo(parseCli([video, "--question", "转场是否自然？", "--fps", "5", "--start", "2", "--end", "8", "--resolution", "high"], {}), env());
  assert.equal(result.text, "00:03 转场生硬");
  assert.equal(result.cleanup, "已删除上传的文件");
  assert.deepEqual(result.usage, { total_tokens: 1234 });
  assert.deepEqual(calls.map((c) => `${c.method} ${c.url}`), [
    "POST /upload/v1beta/files", "POST /upload-session", "GET /v1beta/files/abc", "POST /v1beta/interactions", "DELETE /v1beta/files/abc",
  ]);
  assert.equal(calls[1].body.length, 64);
  assert.equal(calls[0].headers["x-goog-api-key"], "test-key");
  assert.deepEqual(JSON.parse(calls[3].body.toString()), {
    model: "gemini-4-carbon",
    input: [
      { type: "video", uri: `${base}/v1beta/files/abc`, mime_type: "video/mp4", processing: { type: "static", fps: 5, start_offset: "2s", end_offset: "8s" }, resolution: "high" },
      { type: "text", text: "转场是否自然？" },
    ],
    store: false,
  });
});

test("分析失败时仍删除已上传的文件，错误信息不含 key", async () => {
  calls = []; failInteraction = true;
  await assert.rejects(reviewVideo(parseCli([video, "--question", "q"], {}), env()), (error) => {
    assert.match(error.message, /HTTP 429/);
    assert.match(error.message, /quota exceeded/);
    assert.doesNotMatch(error.message, /test-key/);
    return true;
  });
  assert.equal(calls.at(-1).method, "DELETE");
});

test("--keep-file 不删除文件", async () => {
  calls = []; failInteraction = false;
  const result = await reviewVideo(parseCli([video, "--question", "q", "--keep-file"], {}), env());
  assert.match(result.cleanup, /已保留 files\/abc/);
  assert.ok(!calls.some((c) => c.method === "DELETE"));
});

test("没有环境变量时从 key 文件读取", async () => {
  calls = []; failInteraction = false;
  const keyFile = join(dir, "api-key.env");
  writeFileSync(keyFile, "# 注释\nexport GEMINI_API_KEY='file-key'\n");
  await reviewVideo(parseCli([video, "--question", "q"], {}), { GEMINI_API_KEY_FILE: keyFile, GEMINI_API_BASE: base, GEMINI_VIDEO_POLL_MS: "1" });
  assert.equal(calls[0].headers["x-goog-api-key"], "file-key");
});

test("没有 key、文件不存在、扩展名不支持时在上传前报错", async () => {
  calls = [];
  await assert.rejects(reviewVideo(parseCli([video, "--question", "q"], {}), {}), UsageError);
  await assert.rejects(reviewVideo(parseCli([join(dir, "missing.mp4"), "--question", "q"], {}), env()), UsageError);
  await assert.rejects(reviewVideo(parseCli([join(dir, "clip.txt"), "--question", "q"], {}), env()), UsageError);
  assert.equal(calls.length, 0);
});

test("参数校验", () => {
  assert.throws(() => parseCli([video], {}), UsageError);
  assert.throws(() => parseCli([video, "--question", "q", "--question-file", "f"], {}), UsageError);
  assert.throws(() => parseCli([video, "--question", "q", "--fps", "0"], {}), UsageError);
  assert.throws(() => parseCli([video, "--question", "q", "--start", "5", "--end", "5"], {}), UsageError);
  assert.throws(() => parseCli([video, "--question", "q", "--mode", "agentic", "--fps", "2"], {}), UsageError);
  assert.throws(() => parseCli([video, "--question", "q", "--resolution", "4k"], {}), UsageError);
  assert.equal(parseCli([video, "--question", "q"], { GEMINI_VIDEO_MODEL: "gemini-4-argon" }).model, "gemini-4-argon");
  assert.equal(parseCli([video, "--question", "q", "--model", "m"], { GEMINI_VIDEO_MODEL: "gemini-4-argon" }).model, "m");
});

test("请求体：默认不带 processing；agentic 用字符串", () => {
  const file = { uri: "u", mimeType: "video/mp4" };
  assert.equal(buildInteractionBody(parseCli([video, "--question", "q"], {}), file, "q").input[0].processing, undefined);
  assert.equal(buildInteractionBody(parseCli([video, "--question", "q", "--mode", "agentic"], {}), file, "q").input[0].processing, "agentic");
});

test("提取文字：兼容 output_text 和 steps", () => {
  assert.equal(extractText({ output_text: "a" }), "a");
  assert.equal(extractText({ steps: [{ type: "model_output", content: [{ type: "text", text: "b" }, { type: "text", text: "c" }] }] }), "b\nc");
  assert.equal(extractText({ steps: [{ type: "thought" }] }), "");
});
