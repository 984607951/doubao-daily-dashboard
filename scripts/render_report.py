#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染报告：built_*.json → 词云 → 二维码 → 注入HTML → 截图。
用法: python3 render_report.py <date> [qr_url]
"""
import json, os, sys, base64, subprocess
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CST = timezone(timedelta(hours=8))
def find_cjk_font():
    """跨平台查找中文字体：优先环境变量，再试常见路径，找不到返回 None。"""
    env = os.environ.get("DOUBAO_FONT_PATH")
    if env and os.path.exists(env):
        return env
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


FONT = find_cjk_font()

WEEK_CN = ["一", "二", "三", "四", "五", "六", "日"]


def b64_file(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def build_activity(d):
    """从hourly数据构造活跃流，自动识别睡眠gap。"""
    hourly = {int(k): v for k, v in d["hourly"].items()}
    ws = datetime.fromisoformat(d["window_start"]).astimezone(CST)
    we = datetime.fromisoformat(d["window_end"]).astimezone(CST)
    # 窗口内小时序列
    hours = []
    cur = ws.replace(minute=0, second=0, microsecond=0)
    while cur <= we:
        hours.append(cur)
        cur += timedelta(hours=1)
    vals = [hourly.get(h.hour, 0) for h in hours]
    # 找首个/末个非零
    nz = [i for i, v in enumerate(vals) if v > 0]
    if not nz:
        return {"labels": [], "vals": [], "coolUntil": 0, "vmax": 1, "gap": None}
    f, l = nz[0], nz[-1]
    labels = [str(hours[i].hour) for i in range(f, l + 1)]
    s_vals = vals[f:l + 1]
    # 找连续>=4个0的gap
    gap = None
    i = 0
    while i < len(s_vals):
        if s_vals[i] == 0:
            j = i
            while j < len(s_vals) and s_vals[j] == 0:
                j += 1
            if j - i >= 4:
                gap = {"from": i, "to": j, "text": f"睡眠 {j-i} 小时"}
                break
            i = j
        else:
            i += 1
    vmax = max(s_vals)
    # coolUntil：gap前的柱子数（跨夜深蓝）
    cool_until = gap["from"] if gap else len(s_vals)
    return {"labels": labels, "vals": s_vals, "coolUntil": cool_until,
            "vmax": vmax, "gap": gap}


def load_history():
    """读取 daily_stats.json，返回 {date: record}。"""
    p = os.path.join(ROOT, "data", "daily_stats.json")
    if not os.path.exists(p):
        return {}
    d = json.load(open(p))
    return {x["date"]: x for x in d.get("days", [])}


def build_week(date, hist):
    """构造报告日期所在周（周一到周日）的真实工具调用数。"""
    dt = datetime.fromisoformat(date)
    monday = dt - timedelta(days=dt.weekday())
    vals = []
    for i in range(7):
        k = (monday + timedelta(days=i)).strftime("%Y-%m-%d")
        rec = hist.get(k)
        vals.append(rec["metrics"]["tool_calls_total"] if rec else 0)
    return {"labels": WEEK_CN, "vals": vals, "vmax": max(200, max(vals) if vals else 1)}


def streak_days(date, hist):
    """从报告日期往前数连续有记录的天数。"""
    n = 0
    cur = datetime.fromisoformat(date)
    while cur.strftime("%Y-%m-%d") in hist:
        n += 1
        cur -= timedelta(days=1)
    return max(n, 1)


def make_wordcloud(d, path):
    from wordcloud import WordCloud
    import random
    kws = d["keywords"]
    # 词频权重
    w = {}
    for i, k in enumerate(kws):
        w[k] = max(6, len(kws) - i)
    colors = ["#4F46E5", "#3B82F6", "#06B6D4", "#D946EF", "#FB7185", "#F59E0B"]
    if not FONT:
        print("警告: 未找到中文字体，词云中文可能乱码；可设置环境变量 DOUBAO_FONT_PATH 指定字体文件")
    wc = WordCloud(font_path=FONT, width=1120, height=420, background_color=None,
                   mode="RGBA", prefer_horizontal=1, max_words=40, margin=8,
                   color_func=lambda *a, **k: random.choice(colors),
                   collocations=False).generate_from_frequencies(w)
    wc.to_file(path)


def make_qr(url, path):
    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1E1B4B", back_color="white")
    img.save(path)


def load_config():
    p = os.path.join(ROOT, "data", "config.json")
    if os.path.exists(p):
        return json.load(open(p))
    return {"qr_url": "https://www.doubao.com", "chromium": "",
            "desktop_viewport": [1360, 2380], "mobile_viewport": [430, 2400]}


def find_chromium():
    """自动探测系统已安装的 Chromium/Chrome，找不到返回空串（回退 Playwright 自带）。"""
    candidates = [
        "/usr/local/bin/chromium", "/usr/bin/chromium",
        "/usr/local/bin/chromium-browser", "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def screenshot(html_path, viewport, out_path, chromium):
    """用 playwright 整页截图，自动适配完整页面高度（不截断）。"""
    from playwright.sync_api import sync_playwright
    w, h = viewport
    chromium = chromium or find_chromium()
    with sync_playwright() as p:
        launch_kw = {"args": ["--no-sandbox"]}
        if chromium:  # 显式指定或自动探测到系统浏览器才传，否则用 Playwright 自带
            launch_kw["executable_path"] = chromium
        b = p.chromium.launch(**launch_kw)
        pg = b.new_page(viewport={"width": w, "height": min(h, 1400)})
        pg.goto("file://" + html_path)
        pg.wait_for_timeout(900)
        pg.screenshot(path=out_path, full_page=True)
        b.close()
    return out_path


def main():
    date = sys.argv[1]
    cfg = load_config()
    qr_url = sys.argv[2] if len(sys.argv) > 2 else cfg["qr_url"]
    d = json.load(open(os.path.join(ROOT, "data", f"built_{date}.json")))
    ident = d["identity"]
    code = ident["code"]
    animal = ident["animal"]
    role = ident["role"]

    # 词云
    wc_path = os.path.join(ROOT, "data", f"wc_{date}.png")
    make_wordcloud(d, wc_path)
    # 二维码
    qr_path = os.path.join(ROOT, "data", f"qr_{date}.png")
    make_qr(qr_url, qr_path)

    # 透明hero（动物中文名 → 英文文件名）
    ANIMAL_EN = {"猫头鹰": "owl", "孔雀": "peacock", "蜜蜂": "bee", "鹦鹉": "parrot",
                 "啄木鸟": "woodpecker", "狐狸": "fox", "金毛犬": "golden", "浣熊": "raccoon"}
    hero_path = os.path.join(ROOT, "data", f"hero_{ANIMAL_EN.get(animal, animal)}.webp")
    if not os.path.exists(hero_path):
        raise FileNotFoundError(f"缺少透明hero: {hero_path}，请先抠图")

    m = d["metrics"]
    cat = d["category"]
    hist = load_history()
    streak = streak_days(date, hist)
    tot = sum(v for v in cat.values()) or 1
    segs = [{"color": {"工程与读写": "#4F46E5", "任务统筹": "#06B6D4", "视觉创作": "#D946EF",
                       "检索研究": "#F59E0B", "交付与调度": "#FB7185"}[k],
             "pct": round(n / tot * 100), "label": k}
            for k, n in sorted(cat.items(), key=lambda x: -x[1]) if n > 0]
    # 修正pct和为100
    diff = 100 - sum(s["pct"] for s in segs)
    if segs:
        segs[0]["pct"] += diff

    tools_sorted = sorted(d["tool_calls"].items(), key=lambda x: -x[1])[:8]
    tcolors = ["#4F46E5", "#3B82F6", "#D946EF", "#06B6D4", "#FB7185", "#4F46E5", "#06B6D4", "#F59E0B"]
    ratio = m["tokens_in"] / max(m["tokens_out"], 1)
    ratio_str = f"1:{round(m['tokens_out']/max(m['tokens_in'],1),1)}"
    # 活跃时长：非零小时数 × 40 分钟
    active_hours = sum(1 for v in d["hourly"].values() if v > 0)
    active_minutes = active_hours * 40

    kws = d["keywords"]
    DASH = {
        "activity": build_activity(d),
        "donut": {"segs": segs, "center": {"big": f"{len(segs)} 类", "small": "并行任务"}},
        "tools": {"total": m["tool_calls_total"],
                  "list": [{"name": n, "v": v, "color": tcolors[i % 8]} for i, (n, v) in enumerate(tools_sorted)]},
        "tags": {"big": kws[0] if kws else role,
                 "mid": kws[1:3], "rest": kws[3:6]},
        "week": build_week(date, hist),
        "ratio": {"num": ratio_str.replace(":", '<span>:</span>'),
                  "desc": "输入 : 输出 Token 比<br>每给 1 个 Token，"
                          f"产出 {round(m['tokens_out']/max(m['tokens_in'],1),1)} 个",
                  "inPct": round(m["tokens_in"] / max(m["tokens_in"] + m["tokens_out"], 1) * 100, 1),
                  "outPct": 100,
                  "note": f"{m['user_turns']} 条指令、{m['tool_calls_total']} 次工具调用，"
                          f"覆盖 {len(segs)} 类任务，长短指令结合推进。"},
        "footer": {"f1": f'{streak}<small style="font-size:14px"> 天</small>',
                   "f2": f"{m['tokens_total']:,}",
                   "f3": f'{active_minutes}<small style="font-size:14px"> 分钟</small>',
                   "f4": str(round(m["tool_calls_total"] / max(m["user_turns"], 1), 1))},
    }

    dt = datetime.fromisoformat(date + "T12:00:00").replace(tzinfo=CST)
    weekday = "星期" + WEEK_CN[dt.weekday()]
    traits = "".join(f'<span class="htrait">{k}</span>' for k in kws[:3])
    traits += '<span class="htrait warm">灵活应变</span>'
    mlegend = ('<span><i style="background:#6366F1"></i>深夜波</span>'
               '<span><i style="background:#D946EF"></i>白天波</span>'
               '<span style="margin-left:auto;color:var(--ink-3)">'
               f'峰值：{max(DASH["activity"]["vals"] or [0])} 次</span>')

    line = f"{m['user_turns']} 条指令、{m['tool_calls_total']} 次工具调用，"
    line += f"你是今天的「{role}」——{('、'.join(kws[:3]))}。"

    tpl = open(os.path.join(ROOT, "reports", "template_v3.html")).read()
    repl = {
        "__DATE__": date,
        "__DATE_FULL__": f"{dt.year}年{dt.month}月{dt.day}日 {weekday}",
        "__HERO_B64__": b64_file(hero_path),
        "__HERO_CODE__": f"{code} · {animal.upper() if animal.isalpha() else animal}",
        "__HERO_T1__": role[:len(role)//2] or role,
        "__HERO_T2__": role[len(role)//2:] or "",
        "__HERO_TRAITS__": traits,
        "__H_TOK__": f"{m['tokens_total']:,}",
        "__H_CALLS__": str(m["tool_calls_total"]),
        "__H_PROB__": str(m["user_turns"]),
        "__H_RATIO__": ratio_str,
        "__HERO_LINE__": line,
        "__K1_V__": f"{m['tokens_total']:,}",
        "__K1_F__": f"入 {m['tokens_in']:,} · 出 {m['tokens_out']:,}",
        "__K2_V__": f'{m["images_gen"]}<small> 张</small>',
        "__K2_F__": "视觉创作",
        "__K3_V__": f'{m["images_edit"]}<small> 张</small>',
        "__K3_F__": "精修打磨",
        "__K4_V__": f'{m["assistant_chars"]:,}<small> 字</small>',
        "__K4_F__": f"你输入 {m['user_chars']:,} 字",
        "__K5_V__": f'{m["user_turns"]}<small> 个</small>',
        "__K5_F__": f"{m['assistant_turns']} 次回复",
        "__M_HINT__": "全天活跃流",
        "__M_LEGEND__": mlegend,
        "__WC_B64__": b64_file(wc_path),
        "__SHARE_DATE__": f"{dt.month} / {dt.day}",
        "__SHARE_T1__": "今日身份 ·",
        "__SHARE_T2__": role,
        "__SM1__": f"{m['tokens_total']:,}",
        "__SM2__": f'{m["images_gen"]} 张',
        "__SM3__": f'{m["images_edit"]} 张',
        "__SM4__": f'{m["assistant_chars"]:,} 字',
        "__SM5__": f'{m["user_turns"]} 个',
        "__SM6__": f'{m["tool_calls_total"]} 次',
        "__QR_B64__": b64_file(qr_path),
        "__SHARE_FOOT__": f"豆包每日仪表盘 · {date} · 由 AI 生成",
        "__REPORT_DATA__": json.dumps(DASH, ensure_ascii=False),
    }
    for k, v in repl.items():
        assert k in tpl, k
        tpl = tpl.replace(k, v)
    out_html = os.path.join(ROOT, "reports", f"{date}.html")
    open(out_html, "w").write(tpl)
    # 自动截图（桌面 + 手机）
    prev_dir = os.path.join(ROOT, "previews")
    os.makedirs(prev_dir, exist_ok=True)
    d_png = os.path.join(prev_dir, f"{date}_desktop.png")
    m_png = os.path.join(prev_dir, f"{date}_mobile.png")
    screenshot(out_html, cfg["desktop_viewport"], d_png, cfg["chromium"])
    screenshot(out_html, cfg["mobile_viewport"], m_png, cfg["chromium"])
    print(json.dumps({"rendered": out_html, "size_kb": len(tpl) // 1024,
                      "desktop": d_png, "mobile": m_png}, ensure_ascii=False))


if __name__ == "__main__":
    main()
