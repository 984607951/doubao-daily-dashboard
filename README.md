# 豆包每日仪表盘（Doubao Daily Dashboard）

把你每天和 AI 的对话，自动浓缩成一份好看的数据报告：Token、图片、文字、问题数，以及一个匹配当天风格的"动物身份"。

纯本地运行，数据不出你的电脑，无需服务器即可生成单份报告。

- 在线 Demo：https://984607951.github.io/doubao-daily-dashboard/
- 源码仓库：https://github.com/984607951/doubao-daily-dashboard
- 小白上手指南：[QUICKSTART.md](QUICKSTART.md)（不懂命令行照做即可）
- 开源协议：MIT

## 功能特性

- **核心指标**：Token（估算）、图片生成/修改张数、文字处理字数、解决问题数、工具调用次数
- **今日活跃流**：按小时展示一天的工作节奏，自动识别睡眠间隔
- **任务类型分析**：5 大类任务占比，一眼看清当天在做什么
- **每日身份**：根据当天的任务结构，匹配 8 个动物身份之一
- **关键词词云**：透明背景，自动融入页面
- **社媒分享卡片**：9:16 竖版卡片，含二维码，一键生成
- **响应式**：电脑、手机自适应，整页截图自动产出

## 8 个每日身份

| 代号 | 动物 | 身份 | 触发条件（主导任务） |
|---|---|---|---|
| SVA-01 | 猫头鹰 | 自我量化架构师 | 工程与读写 |
| PCV-02 | 孔雀 | 像素指挥官 | 任务统筹 |
| DRS-03 | 蜜蜂 | 深度研究员 | 检索研究 |
| WRT-04 | 鹦鹉 | 文字工匠 | 工程与读写 |
| DBG-05 | 啄木鸟 | 调试工程师 | 工程与读写 |
| CDR-06 | 狐狸 | 创意总监 | 视觉创作 |
| LFC-07 | 金毛犬 | 生活顾问 | 检索研究 |
| MIX-08 | 浣熊 | 全能多面手 | 无单一主导（占比均 < 42% 或覆盖 ≥ 4 类） |

## 工作原理

```
本地会话数据（trajectory.jsonl + assignment.md）
        ↓ collect_stats.py 按时间窗口采集
build_report.py 分类、判定身份、提取关键词
        ↓
render_report.py 词云 + 二维码 + 注入模板 + 截图
        ↓
reports/<date>.html + previews/ 预览图
```

## 目录结构

```
.
├── README.md
├── LICENSE
├── scripts/
│   ├── collect_stats.py      # 采集底层
│   ├── build_report.py       # 分析：分类/身份/关键词
│   ├── render_report.py      # 渲染：词云/二维码/注入/截图
│   ├── make_sample.py        # 生成编造的示例数据
│   └── run_daily.sh          # 一键入口
├── reports/
│   ├── template_v3.html      # 权威 HTML 模板
│   └── demo.html             # 自包含示例 Demo（可直接打开）
├── data/
│   ├── config.example.json   # 配置模板（复制为 config.json）
│   ├── sample_data.json      # 示例数据
│   └── hero_*.webp           # 8 个透明动物立绘
├── docs/                     # 示例预览图（桌面/手机）
└── identity_avatars/         # 8 个动物原图
```

## 环境要求

- Python 3.9+
- 依赖：`pip install wordcloud qrcode pillow playwright`
- 截图用 Chromium：`playwright install chromium`，或在 config 中指定系统 Chromium 路径
- 中文字体（词云用）：脚本会自动查找；找不到可设环境变量 `DOUBAO_FONT_PATH`

## 快速开始

### 方式零：查看示例 Demo（无需真实数据）

```bash
python3 scripts/make_sample.py                          # 生成编造的示例数据
python3 scripts/render_report.py 2026-10-15             # 渲染示例
# 打开生成的 reports/2026-10-15.html 即可看到完整效果（仓库内也附了 reports/demo.html）
```

### 方式一：一键生成（推荐）

```bash
bash scripts/run_daily.sh
```

自动按"昨日 19:00 — 今日 18:50"窗口生成报告、渲染并截图。

### 方式二：分步执行

```bash
# 1. 分析（自动窗口）
python3 scripts/build_report.py

# 2. 渲染（<date> 为报告日期，如 2026-10-30）
python3 scripts/render_report.py <date>
```

### 方式三：自定义时间窗口

```bash
python3 scripts/build_report.py <start_utc> <end_utc> <date>
python3 scripts/render_report.py <date>
# 例如:
python3 scripts/build_report.py 2026-10-28T11:00:00 2026-10-29T10:50:00 2026-10-29
```

## 配置说明

复制 `data/config.example.json` 为 `data/config.json` 后按需修改：

- `qr_url`：分享卡片二维码指向的报告链接
- `chromium`：Chromium 可执行路径；留空则用 Playwright 自带浏览器

环境变量：

| 变量 | 作用 |
|---|---|
| `DOUBAO_SESSIONS_ROOT` | 会话数据根目录（默认指向标准安装路径） |
| `DOUBAO_FONT_PATH` | 词云中文字体文件路径 |

## 统计口径

- **周期**：昨日 19:00 — 今日 18:50（Asia/Shanghai），报告归属"今日"
- **范围**：本机账号下所有会话
- **Token 估算**：中文等 CJK 约 1 字 ≈ 1.3 token，其余约 4 字符/token；非平台精确计费值
- 问题数、身份判定、一句话总结由规则 + AI 生成

## 常见问题

**在线 Demo 能直接统计我的数据吗？**
不能。浏览器无法读取你本地的会话数据，Demo 只展示固定示例和样式。要统计自己的数据，请按上文在本地运行。

**报告数据存在哪里？**
全部在本地 `data/` 目录，不上传、不外发。

**需要一直开着电脑吗？**
生成单份报告不需要常驻，运行脚本即可。若要每天自动定时生成，需要自行配置系统定时任务。

## 免责声明

本项目为第三方个人开源工具，与豆包官方无关。Token 为本地估算值，不代表平台实际计费。请仅在遵守相关平台条款的前提下使用。

## 开源协议

[MIT License](LICENSE)
