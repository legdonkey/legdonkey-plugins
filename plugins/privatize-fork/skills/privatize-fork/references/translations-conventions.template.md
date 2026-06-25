# 官方文档中文翻译（私有参考）

upstream 官方文档的中文译文，仅作团队参考，**不回推 upstream**。

## 翻译范围（白名单）

本清单由 privatize-fork 阶段2「翻译范围选择框」扫描本项目文档后确认，是增量翻译的**唯一依据**。
增删翻译范围改这里即可（不要改 skill 流程文件），重跑 skill 会照此刷新。

**翻译（白名单）**：

{{WHITELIST}}

**显式排除（黑名单，不翻）**：

{{BLACKLIST}}

## 命名约定

- 译文文件名：源相对路径去扩展、`/` 换成 `-`，再加 `.zh.md`——顶层 `README.md` → `README.zh.md`；子目录 `docs/api.md` → `docs-api.zh.md`（避免不同目录同名文件撞车）。译文仍平铺在 `private/translations/` 顶层。
- 译文头部加 frontmatter，标注译自哪个源文件、哪个 upstream 版本：

```yaml
---
source: README.md
source_version: {{BASE_VERSION}}
translated_at: 2026-01-01
---
```

## 防过期

译文会随 upstream 原文更新而过时。升级 upstream 后：

1. 对比每个译文的 `source_version` 与新基线版本。
2. 若源文件在新版本有改动（下面命令输出非空），重译并更新 frontmatter：

```bash
git diff --stat <旧版本>..<新版本> -- <source 路径>
```
