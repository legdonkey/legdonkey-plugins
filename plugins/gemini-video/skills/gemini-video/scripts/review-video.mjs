#!/usr/bin/env node
// 把本地视频上传到 Gemini API，按给定问题返回模型的分析。
// 只依赖 Node 标准库（Node 20 及以上）。API key 只从环境变量读取，不写入任何输出。

import { openAsBlob } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { basename, extname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

const DEFAULT_BASE = "https://generativelanguage.googleapis.com";
const DEFAULT_MODEL = "gemini-4-carbon";
const MAX_BYTES = 2 * 1024 ** 3; // Files API 免费层的单文件上限。
const MIME_BY_EXT = {
  ".mp4": "video/mp4", ".mov": "video/mov", ".webm": "video/webm", ".mpeg": "video/mpeg",
  ".mpg": "video/mpg", ".avi": "video/avi", ".wmv": "video/wmv", ".flv": "video/x-flv", ".3gp": "video/3gpp",
};
const RESOLUTIONS = ["low", "medium", "high", "ultra_high"];

export class UsageError extends Error {}

const HELP = `用法：review-video.mjs <视频路径> (--question <文字> | --question-file <路径>) [选项]

选项：
  --model <id>          模型，默认 ${DEFAULT_MODEL}（也可用环境变量 GEMINI_VIDEO_MODEL）
  --mode <static|agentic>  处理模式，默认 static
  --fps <数字>          采样帧率，只在 static 模式可用；不设时为每秒 1 帧
  --start <秒>          片段起点，只在 static 模式可用
  --end <秒>            片段终点，只在 static 模式可用
  --resolution <档位>   每帧的画面分辨率：${RESOLUTIONS.join(" | ")}
  --timeout <秒>        整个流程的超时，默认 600
  --keep-file           分析后不删除已上传的文件（文件 48 小时后自动删除）
  --json                以 JSON 输出结果
  --help                显示本说明

API key：环境变量 GEMINI_API_KEY；没有设置时读取 ~/.config/gemini/api-key.env（可用 GEMINI_API_KEY_FILE 改路径）。`;

function toNumber(value, name, { min, exclusiveMin = false }) {
  const n = Number(value);
  if (!Number.isFinite(n) || (exclusiveMin ? n <= min : n < min)) {
    throw new UsageError(`${name} 必须是${exclusiveMin ? "大于" : "不小于"} ${min} 的数字，收到：${value}`);
  }
  return n;
}

export function parseCli(argv, env = process.env) {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      allowPositionals: true,
      options: {
        question: { type: "string" }, "question-file": { type: "string" },
        model: { type: "string" }, mode: { type: "string" }, fps: { type: "string" },
        start: { type: "string" }, end: { type: "string" }, resolution: { type: "string" },
        timeout: { type: "string" }, "keep-file": { type: "boolean" }, json: { type: "boolean" },
        help: { type: "boolean" },
      },
    });
  } catch (error) {
    throw new UsageError(error.message);
  }
  const { values, positionals } = parsed;
  if (values.help) return { help: true };
  if (positionals.length !== 1) throw new UsageError("需要且只需要一个视频路径。");
  if (Boolean(values.question) === Boolean(values["question-file"])) {
    throw new UsageError("--question 和 --question-file 必须提供其中一个。");
  }
  const mode = values.mode ?? "static";
  if (mode !== "static" && mode !== "agentic") throw new UsageError(`--mode 只能是 static 或 agentic，收到：${mode}`);
  const options = {
    videoPath: resolve(positionals[0]),
    question: values.question,
    questionFile: values["question-file"],
    model: values.model ?? env.GEMINI_VIDEO_MODEL ?? DEFAULT_MODEL,
    mode,
    keepFile: Boolean(values["keep-file"]),
    json: Boolean(values.json),
    timeoutMs: toNumber(values.timeout ?? "600", "--timeout", { min: 0, exclusiveMin: true }) * 1000,
  };
  if (values.fps !== undefined) options.fps = toNumber(values.fps, "--fps", { min: 0, exclusiveMin: true });
  if (values.start !== undefined) options.start = toNumber(values.start, "--start", { min: 0 });
  if (values.end !== undefined) options.end = toNumber(values.end, "--end", { min: 0, exclusiveMin: true });
  if (options.start !== undefined && options.end !== undefined && options.end <= options.start) {
    throw new UsageError("--end 必须大于 --start。");
  }
  if (mode === "agentic" && (options.fps !== undefined || options.start !== undefined || options.end !== undefined)) {
    throw new UsageError("--fps、--start、--end 只在 static 模式可用。");
  }
  if (values.resolution !== undefined) {
    if (!RESOLUTIONS.includes(values.resolution)) throw new UsageError(`--resolution 只能是 ${RESOLUTIONS.join("、")}。`);
    options.resolution = values.resolution;
  }
  return options;
}

export function buildInteractionBody(options, file, question) {
  const video = { type: "video", uri: file.uri, mime_type: file.mimeType };
  if (options.mode === "agentic") {
    video.processing = "agentic";
  } else if (options.fps !== undefined || options.start !== undefined || options.end !== undefined) {
    video.processing = { type: "static" };
    if (options.fps !== undefined) video.processing.fps = options.fps;
    if (options.start !== undefined) video.processing.start_offset = `${options.start}s`;
    if (options.end !== undefined) video.processing.end_offset = `${options.end}s`;
  }
  if (options.resolution) video.resolution = options.resolution;
  // 文档要求：只有一个视频时，文字放在视频之后。store:false 让服务端不保存这次交互。
  return { model: options.model, input: [video, { type: "text", text: question }], store: false };
}

export function extractText(interaction) {
  if (typeof interaction?.output_text === "string" && interaction.output_text.trim()) return interaction.output_text;
  const parts = [];
  for (const step of interaction?.steps ?? []) {
    if (step?.type !== "model_output") continue;
    for (const item of step.content ?? []) if (item?.type === "text" && typeof item.text === "string") parts.push(item.text);
  }
  return parts.join("\n").trim();
}

async function readJson(response, action) {
  const raw = await response.text();
  let data;
  try { data = raw ? JSON.parse(raw) : {}; } catch { data = undefined; }
  if (!response.ok) {
    const detail = data?.error?.message ?? raw.slice(0, 300);
    throw new Error(`${action}失败：HTTP ${response.status}。${detail}`);
  }
  if (data === undefined) throw new Error(`${action}失败：服务端返回的不是 JSON。`);
  return data;
}

async function uploadVideo({ base, key, path, size, mimeType, signal }) {
  const start = await fetch(`${base}/upload/v1beta/files`, {
    method: "POST",
    signal,
    headers: {
      "x-goog-api-key": key,
      "X-Goog-Upload-Protocol": "resumable",
      "X-Goog-Upload-Command": "start",
      "X-Goog-Upload-Header-Content-Length": String(size),
      "X-Goog-Upload-Header-Content-Type": mimeType,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ file: { display_name: basename(path) } }),
  });
  if (!start.ok) await readJson(start, "创建上传会话");
  const uploadUrl = start.headers.get("x-goog-upload-url");
  if (!uploadUrl) throw new Error("创建上传会话失败：响应里没有上传地址。");
  const finish = await fetch(uploadUrl, {
    method: "POST",
    signal,
    headers: { "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize" },
    body: await openAsBlob(path),
  });
  const data = await readJson(finish, "上传视频");
  if (!data.file?.name || !data.file?.uri) throw new Error("上传视频失败：响应里没有文件信息。");
  return data.file;
}

async function waitUntilActive({ base, key, file, pollMs, signal }) {
  let current = file;
  while (current.state && current.state !== "ACTIVE") {
    if (current.state === "FAILED") throw new Error("Gemini 处理视频失败（文件状态为 FAILED）。");
    await new Promise((done) => setTimeout(done, pollMs));
    signal.throwIfAborted();
    current = await readJson(await fetch(`${base}/v1beta/${file.name}`, { signal, headers: { "x-goog-api-key": key } }), "查询文件状态");
  }
  return current;
}

async function deleteFile({ base, key, name }) {
  const response = await fetch(`${base}/v1beta/${name}`, { method: "DELETE", headers: { "x-goog-api-key": key }, signal: AbortSignal.timeout(30_000) });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
}

// 环境变量优先。没有时读 key 文件：子代理和非交互 shell 不加载 ~/.zshrc，拿不到环境变量。
async function resolveKey(env) {
  if (env.GEMINI_API_KEY) return env.GEMINI_API_KEY;
  const file = env.GEMINI_API_KEY_FILE ?? (env.HOME ? join(env.HOME, ".config/gemini/api-key.env") : undefined);
  const content = file ? await readFile(file, "utf8").catch(() => "") : "";
  return content.match(/^\s*(?:export\s+)?GEMINI_API_KEY=["']?([^"'\s]+)["']?\s*$/m)?.[1];
}

export async function reviewVideo(options, env = process.env) {
  const key = await resolveKey(env);
  if (!key) throw new UsageError("没有找到 Gemini API key。在 Google AI Studio 创建 key 后，设为环境变量 GEMINI_API_KEY，或写进 ~/.config/gemini/api-key.env（一行 GEMINI_API_KEY=...）。");
  const base = (env.GEMINI_API_BASE ?? DEFAULT_BASE).replace(/\/+$/, "");
  const pollMs = Number(env.GEMINI_VIDEO_POLL_MS ?? 2000);

  const mimeType = MIME_BY_EXT[extname(options.videoPath).toLowerCase()];
  if (!mimeType) throw new UsageError(`不支持的视频扩展名：${extname(options.videoPath) || "（无）"}。支持：${Object.keys(MIME_BY_EXT).join(" ")}`);
  const info = await stat(options.videoPath).catch(() => undefined);
  if (!info?.isFile()) throw new UsageError(`找不到视频文件：${options.videoPath}`);
  if (info.size === 0 || info.size > MAX_BYTES) throw new UsageError(`视频大小必须大于 0 且不超过 2 GiB，当前 ${info.size} 字节。`);
  const question = (options.question ?? await readFile(options.questionFile, "utf8")).trim();
  if (!question) throw new UsageError("审查问题不能为空。");

  const signal = AbortSignal.timeout(options.timeoutMs);
  let uploaded;
  let cleanup = "未上传";
  try {
    uploaded = await uploadVideo({ base, key, path: options.videoPath, size: info.size, mimeType, signal });
    const file = await waitUntilActive({ base, key, file: uploaded, pollMs, signal });
    const body = buildInteractionBody(options, { uri: file.uri ?? uploaded.uri, mimeType: file.mimeType ?? mimeType }, question);
    const interaction = await readJson(await fetch(`${base}/v1beta/interactions`, {
      method: "POST", signal,
      headers: { "x-goog-api-key": key, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }), "分析视频");
    const text = extractText(interaction);
    if (!text) throw new Error(`分析视频失败：响应里没有文字结果（状态：${interaction.status ?? "未知"}）。`);
    return {
      ok: true, text, model: options.model, mode: options.mode, fps: options.fps ?? null,
      start: options.start ?? null, end: options.end ?? null, resolution: options.resolution ?? null,
      bytes: info.size, usage: interaction.usage ?? null,
      get cleanup() { return cleanup; },
    };
  } catch (error) {
    if (error?.name === "TimeoutError") throw new Error(`超过 ${options.timeoutMs / 1000} 秒仍未完成，已中止。`);
    throw error;
  } finally {
    if (uploaded?.name) {
      if (options.keepFile) cleanup = `已保留 ${uploaded.name}，48 小时后自动删除`;
      else cleanup = await deleteFile({ base, key, name: uploaded.name }).then(() => "已删除上传的文件", (error) => `删除上传的文件失败（${error.message}），文件 48 小时后自动删除`);
    }
  }
}

function describe(result) {
  const parts = [`模型 ${result.model}`, `模式 ${result.mode}`, `采样 ${result.fps === null ? "默认（static 为每秒 1 帧）" : `每秒 ${result.fps} 帧`}`];
  if (result.start !== null || result.end !== null) parts.push(`片段 ${result.start ?? 0}s–${result.end === null ? "结尾" : `${result.end}s`}`);
  if (result.resolution) parts.push(`分辨率 ${result.resolution}`);
  parts.push(result.cleanup);
  return parts.join("；");
}

async function main() {
  let options;
  try {
    options = parseCli(process.argv.slice(2));
    if (options.help) { console.log(HELP); return 0; }
    const result = await reviewVideo(options);
    if (options.json) console.log(JSON.stringify({ ...result, cleanup: result.cleanup }, null, 2));
    else console.log(`[gemini-video] ${describe(result)}\n\n${result.text}`);
    return 0;
  } catch (error) {
    const usage = error instanceof UsageError;
    if (options?.json) console.log(JSON.stringify({ ok: false, error: error.message }, null, 2));
    else console.error(usage ? `${error.message}\n\n${HELP}` : error.message);
    return usage ? 2 : 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main();
}
