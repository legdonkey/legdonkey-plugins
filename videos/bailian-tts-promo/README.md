# bailian-tts 宣传片 · 重制版

**约64.1秒 / 1920×1080 / 30fps / H.264 + AAC**。不是旧版补一条音乐，而是按产品亮点重构叙事。

## 交付

- `out/bailian-tts-promo-remake.mp4`：有 BGM，保留全部真实试听、旁白及音效。
- `out/bailian-tts-promo-remake-nobgm.mp4`：无 BGM，其余音轨和画面时间线不变。
- `out/bailian-tts-promo-remake.srt`：独立字幕。**两版均不烧录第二层旁白字幕**，只保留画面主文案、必要的来源和边界说明。
- `out/remake-review.md`、`out/remake-fix-review.md`：独立初检与定点修复复核。不是主观听音合格证明。
- `out/verification-remake.json`：当前成片哈希、全帧双版比较、音乐切点与13个音效钉点实测。
- `out/loudness-remake.log`：当前带音乐版的响度和真峰值。
- `out/parity-remake.log`：工作台与原片关键帧逐像素校验。
- `REMAKE-SPEC.md`：当前创作基准。旧 `DESIGN-SPEC.md` 仅为首版记录。
- `archive/first-cut/`：首版源代码和视频备份；旧45秒输出不是本次推荐成片。

## 这版怎么讲亮点

| 大致时间 | 画面与声音 |
|---|---|
| 0–2秒 | “先听，再说。”：先吸引耳朵，不先念产品名 |
| 2–11秒 | 许南川、于小云、许玉远的同句真实试听快切；真实工作台随音色切换；Flash 内置68音色 |
| 11–23秒 | 四模型由整体亮相变为轮流进入大主位，其余重排右列；说明各自用途 |
| 23–29秒 | 明确口播“Eleven v4 Turbo 和 Eleven v4，位列 AA 原生音色榜前二”；真实页面证据保留日期与统计边界 |
| 29–40秒 | 录音→质检→提交→收藏；真实关键控件放大，明确演示状态和等待压缩 |
| 40–50秒 | 长文→选中→快捷键→准备声音→女声「于小云」读出画面那句话，与男声「许南川」旁白区分 |
| 50–58秒 | 刚听过的三个音频，变成分段文件、完整音轨和 SRT |
| 58–64秒 | 品牌、Claude Code / Codex / Pi 与安装入口 |

## 复现与编辑

```bash
cd videos/bailian-tts-promo  # 从插件仓库根目录进入
npm test
npx tsc
npm run render
npm run render:nobgm
```

工作台：<http://localhost:5208/?import=project>。5198 已有其他服务，本项目未停止它。
镜头、人声、BGM、音效分轨；部分主文案有属性编辑，所有镜头可调整时间、位置、缩放和速度。需要无障碍字幕时可另用交付的 SRT，不必把重复字幕重新烧进视频。

```bash
cd /Users/yangguandao/.agents/skills/video-shotcraft
node workbench/scripts/open.mjs /Users/yangguandao/Projects/legdonkey-plugins/videos/bailian-tts-promo --port 5208
```

`src/timeline.ts` 是唯一时间线。`scripts/prepare-remake.py` 处理真实配音，`scripts/build-sound.py` 生成原创音效与按人声窗口闪避的音乐。`scripts/verify-remake.py` 可复算终版技术数据。
Remotion 4.0.484 / React 19.2.7 依赖从 npmmirror 安装；一次性音乐分析环境的 librosa/scipy 从阿里云 PyPI 镜像取得。视频工程现位于插件仓库的 `videos/bailian-tts-promo/`，插件开始页折叠展示最新版成片。

更新 UI 素材：在本工程运行 `npm run publish:ui`，会同步 MP4、WebP 封面、WebVTT 和来源说明到 `plugins/bailian-tts/skills/bailian-tts/assets/`。播放器不依赖 `out/` 或原工程目录。

`node_modules/`、`out/`、`archive/` 和 `public/audio/bgm/` 保留在本机但不纳入 Git。换机器渲染时按音乐来源与许可自行取得 `house-vibez.mp3`，放入 `public/audio/bgm/` 后运行 `python3 scripts/build-sound.py`。UI 已打包视频，不需要安装视频工程依赖。

## 事实与安全边界

- 三个音色都是真实 Flash 生成，不是 ElevenLabs 样音，也不是用户真人复刻。凭据只由原插件内部读取，没有复制到工程。
- “68”仅指仓库 Flash 内置音色清单。四个模型不共用同一音色库。
- AA 官方页面于2026-11-02核查：Eleven v4 Turbo / Eleven v4 在 Provider Voice Arena 当日排序前二，排名区间均为1–2；不宣称中文专项第一、声音克隆第一或显著领先。榜单会变化。原始快照见 `reference/aa-snapshot.json`。
- 录音、质检和收藏是隔离演示状态，等待经过压缩；10–20秒是推荐参考录音长度，不是克隆生成耗时。
- 朗读仅展示macOS；先配置按键/权限，完整合成后播放。画面选中句与真实播放文案相同。
- 字幕分句按文案长度分配时间，不是逐字ASR对时。不要用该SRT宣称逐字精准字幕。

## 声音许可与验收边界

音乐为 **House Vibez — Lily J / Mixkit**，来源与哈希见 `public/audio/sound-manifest.json`。已核对 Mixkit Stock Music Free License：允许社交平台、YouTube、在线营销视频等；不用于电视/广播、游戏、CD/DVD，也不能单独发布处理后的音乐或登记为自己的作品。素材只为本片及其后续视频编辑使用。

13个动作音效由固定种子的原创短声和已有 Freesound CC0 木质扫声组成。用户已同意在Freesound限流后使用原创音效；没有继续请求该受限来源。派生处理和作者记录均在 manifest，原文件许可记录仍在 `public/audio/sfx/`。

两版由同一Remotion时间线分别渲染。H.264有损编码存在末位像素差，因此报告使用全帧SSIM验证画面等价，不声称编码后逐像素完全相同。音频相关性、峰值和响度检查不能代替主观听音；未取得人工听感验收。自动视频听音工具因缺少Gemini访问未能执行，未读取浏览器Cookie或改动登录配置。
