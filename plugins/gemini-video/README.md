# gemini-video：用 Gemini 审查本地视频

Claude、GPT 等模型不能直接看视频。这个插件提供一个技能和一个脚本，把本地视频交给 Gemini，按你的问题返回分析。跨 Claude Code、Codex 与 Pi。

## 能做什么

- 检查画面与旁白稿或字幕是否一致。
- 检查字幕是否清晰、有没有遮挡或错漏。
- 检查操作步骤和界面反馈是否完整对应。
- 检查转场和动效节奏。这一项需要提高采样帧率。
- 总结视频内容，或者在长视频里定位某个片段。

## 准备

1. 在 [Google AI Studio](https://aistudio.google.com/) 创建一个 API key。
2. 把它设为环境变量 `GEMINI_API_KEY`，或者写进 `~/.config/gemini/api-key.env`（一行 `GEMINI_API_KEY=...`，文件权限设为仅本人可读）。脚本先读环境变量，再读这个文件。
3. 确认 Node 版本不低于 20。脚本只用 Node 标准库，不需要安装依赖。

调用按量计费。Gemini API 使用预付款：项目要先在 AI Studio 充值（最低 5 美元）才能调用，余额为零时接口返回 HTTP 402。

## 直接运行脚本

```bash
node plugins/gemini-video/skills/gemini-video/scripts/review-video.mjs out/final.mp4 \
  --question "对照下面的旁白稿，列出画面与旁白不一致的地方，每条带 MM:SS 时间戳。旁白稿：……"

# 高帧率复查 12 秒到 20 秒之间的转场
node plugins/gemini-video/skills/gemini-video/scripts/review-video.mjs out/final.mp4 \
  --start 12 --end 20 --fps 10 --question "逐个描述这一段里的转场，指出生硬或闪烁的地方。"
```

全部选项见 `--help`，按审查目的选参数的方法见 [SKILL.md](skills/gemini-video/SKILL.md)。

## 工作过程

1. 脚本用 Files API 上传视频，等待 Gemini 处理完成。
2. 脚本调用 Interactions API，带上视频和你的问题。请求设置了 `store: false`，服务端不保存这次交互。
3. 脚本输出回答，第一行写明模型、处理模式、帧率和片段范围。
4. 脚本删除已上传的文件。删除失败时会说明，文件 48 小时后自动删除。

## 限制

- 默认每秒采样 1 帧，短于 1 秒的转场和闪帧看不到。检查这类问题要截取片段并提高帧率。
- 单个文件不超过 2 GiB。
- Gemini 给出的时间戳可能有一两秒偏差。
- 音轨会被 Gemini 处理，但这个插件没有实测过音轨审查的准确度。
- 视频会发送到 Google。不要上传你无权外发的内容。

## 测试

```bash
node --test plugins/gemini-video/skills/gemini-video/scripts/review-video.test.mjs
```

测试只访问本机的模拟服务，不调用真实的 Gemini API。
