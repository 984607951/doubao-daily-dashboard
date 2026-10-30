# 小白上手指南：在你自己的豆包上复现仪表盘

这份指南面向完全不懂命令行的新手。照着做，你也能生成和在线 Demo 一样的每日数据仪表盘。

- 在线 Demo：https://984607951.github.io/doubao-daily-dashboard/
- 源码仓库：https://github.com/984607951/doubao-daily-dashboard

## 先懂一个前提（很重要）

这个工具要读取**本地会话文件**（`trajectory.jsonl`）才能统计你的使用数据，所以它不是在普通网页版或手机 App 里点一下就能安装的插件。

最省事的办法，是在带「工作空间 / 代码执行」能力的豆包环境里，把代码放进去，**让豆包照着这份指南帮你跑**。你只需要会发指令，命令行的事交给 AI。

整体流程：

```text
拿到代码 → 让豆包装依赖 → 跑示例验证 → 生成自己的报告 → 打开 HTML
```

## 推荐路径：让豆包帮你跑

### 第一步：把代码放进工作空间（二选一）

- 方式一（最简单）：直接对豆包说——

  > 帮我从 GitHub 克隆这个仓库：https://github.com/984607951/doubao-daily-dashboard

- 方式二：在仓库页面点 **Code → Download ZIP**，下载后上传到工作空间，让豆包解压。

### 第二步：让豆包装依赖并跑示例

把下面这段话直接发给豆包：

> 这是一个开源的豆包数据仪表盘项目。请先帮我安装依赖：wordcloud、qrcode、pillow、playwright；然后运行 `python3 scripts/make_sample.py` 和 `python3 scripts/render_report.py 2026-10-15`，确认示例报告能正常渲染、截图无误。过程中遇到浏览器或字体路径问题，请用脚本里的自动查找功能解决。

### 第三步：生成你自己的报告

示例跑通后，再发这句：

> 环境没问题了，现在运行 `bash scripts/run_daily.sh`，按昨日 19:00 至今日 18:50 的窗口，生成我自己的仪表盘和桌面、手机截图。

### 第四步：打开报告

豆包会交付一个 HTML 文件和桌面、手机两张预览图。点开 HTML 就是和 Demo 一样的效果。之后每天想更新，重复第三步即可。

## 进阶路径：在自己电脑上跑

适合愿意用命令行、且电脑上能拿到会话数据目录的用户。注意：普通网页版 / 手机版的数据在云端，本地拿不到，这是最大的坎。

```bash
# 1. 安装依赖
pip install wordcloud qrcode pillow playwright
playwright install chromium

# 2. 若会话目录不在默认位置，先指定路径
export DOUBAO_SESSIONS_ROOT="/你的/.sessions 路径"

# 3. 一键生成
bash scripts/run_daily.sh
```

默认会话目录为 `~/.doubao/agent_mode/workspace/.sessions`，可用环境变量 `DOUBAO_SESSIONS_ROOT` 覆盖。

## 常见问题

- **示例能跑，自己的数据跑不出来？** 多半是会话目录路径不对，或当前环境拿不到会话文件。确认 `DOUBAO_SESSIONS_ROOT` 指向的目录里确实有各个会话的 `trajectory.jsonl`。
- **截图报错、找不到浏览器？** 脚本会自动探测系统 Chromium/Chrome；若仍失败，可在 `data/config.json`（从 `config.example.json` 复制）里手动指定 `chromium` 路径。
- **二维码指向哪里？** 二维码链接由 `config.json` 的 `qr_url` 或渲染参数决定，部署后改成你自己的报告入口。
- **Token 数字是精确计费值吗？** 不是。中文等 CJK 约 1 字 ≈ 1.3 token，其余约 4 字符/token，是本地估算口径，用于观察趋势。

## 下一步

- 想了解完整功能和脚本说明，见 [README.md](README.md)。
- 想直接看长什么样，打开 [reports/demo.html](reports/demo.html)。
- 代码使用 MIT 协议，可自由修改和二次发布。
