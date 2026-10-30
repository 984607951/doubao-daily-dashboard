#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键生成每日豆包报告：采集 → 分类 → 身份 → 词云 → 二维码 → 注入 → 截图。
用法:
  python3 build_report.py                      # 自动窗口（昨日19:00 至今日18:50，Asia/Shanghai）
  python3 build_report.py <start_utc> <end_utc> <date>
"""
import json, os, sys, base64, subprocess
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import collect_stats as cs

CST = timezone(timedelta(hours=8))

# 工具 → 任务分类
CATEGORY = {
    "工程与读写": ["Bash", "Read", "Write", "Edit", "Grep", "Glob", "analyze_audio", "calculator"],
    "任务统筹": ["task_create", "task_update", "task_get", "task_list", "task_update_", "manage_preference"],
    "视觉创作": ["image_gen", "image_edit", "text_to_video", "image_to_video", "video_edit", "media_to_video",
              "audio_to_audio_plus", "text_to_audio_plus"],
    "检索研究": ["general_search", "image_search", "web.fetch", "tool_search", "execute_defer_tool",
              "seed_finance_lookup", "seed_legal_search", "seed_medical_search", "enterprise_agentic_search"],
    "交付与调度": ["present_files", "present_cards", "create_cron_job", "delete_cron_job", "get_cron_job",
              "list_cron_jobs", "update_cron_job", "get_current_time", "Wait", "interaction.ask",
              "interaction.request_action"],
}
CAT_COLOR = {
    "工程与读写": "#4F46E5",
    "任务统筹": "#06B6D4",
    "视觉创作": "#D946EF",
    "检索研究": "#F59E0B",
    "交付与调度": "#FB7185",
}
# 身份库：代号, 动物, 身份, 主导分类, 关键词, 冷暖
IDENTITIES = {
    "SVA-01": ("猫头鹰", "自我量化架构师", "工程与读写", ["数据", "复盘", "量化"], "冷"),
    "PCV-02": ("孔雀", "像素指挥官", "任务统筹", ["统筹", "调度", "多任务"], "暖"),
    "DRS-03": ("蜜蜂", "深度研究员", "检索研究", ["研究", "深挖", "求证"], "冷"),
    "WRT-04": ("鹦鹉", "文字工匠", "工程与读写", ["文字", "表达", "打磨"], "中"),
    "DBG-05": ("啄木鸟", "调试工程师", "工程与读写", ["调试", "排错", "修复"], "冷"),
    "CDR-06": ("狐狸", "创意总监", "视觉创作", ["创意", "视觉", "设计"], "暖"),
    "LFC-07": ("金毛犬", "生活顾问", "检索研究", ["生活", "陪伴", "建议"], "暖"),
    "MIX-08": ("浣熊", "全能多面手", None, ["多面手", "并行", "全能"], "均衡"),
}


def categorize(tool_calls):
    """把工具调用计数按分类汇总。"""
    cat = {k: 0 for k in CATEGORY}
    for tool, n in tool_calls.items():
        hit = False
        for c, names in CATEGORY.items():
            if tool in names or any(tool.startswith(nm) for nm in names):
                cat[c] += n
                hit = True
                break
        if not hit:
            cat["工程与读写"] += n
    return cat


def judge_identity(cat, total_calls):
    """基于分类占比判断身份。"""
    if total_calls == 0:
        return "MIX-08"
    ranked = sorted(((c, n) for c, n in cat.items() if n > 0), key=lambda x: -x[1])
    top_c, top_n = ranked[0]
    share = top_n / total_calls
    # 没有任何一类占比超过 42% → 多面手
    if share < 0.42 or len(ranked) >= 4:
        return "MIX-08"
    # 特殊：工程与读写主导时，看是否调试类
    if top_c == "工程与读写":
        return "SVA-01"
    for code, (_, _, dom, _, _) in IDENTITIES.items():
        if dom == top_c and code != "WRT-04":
            return code
    return "MIX-08"


def hourly_series(stats):
    """构造活跃流（按小时）。"""
    ha = stats["hourly_activity"]
    return {h: ha.get(h, 0) for h in range(24)}


STOP = set("的 了 我 你 他 她 是 在 和 与 及 或 吗 呢 吧 啊 这 那 个 把 被 对 给 让 就 都 也 很 最 不 没 有 要 会 能 可以 一个 一下 我们 你们 他们 什么 怎么 这样 那样 现在 今天 明天 然后 因为 所以 如果 但是 而且 以及 进行 这个 那个 觉得 一点 第二 第一 目前 咱们 还有 就是 不是 还是 或者 已经 之后 之前 底部 顶部 增加 现在 早上 晚上".split())
BAD_END = "的 了 在 是 没 把 被 就 都 也 很 有 要 会 和 与 及 着 过 到 从 向 于 吗 呢 吧 点 第 得".split()
BAD_START = "的 了 是 把 被 就 都 也 很 最 不 没 有 要 会 和 与 着 过 点 我 你 他".split()


def extract_keywords(text, cat, idkws):
    """从用户文本提取2-6字高频词，叠加身份词与分类词。"""
    import re
    from collections import Counter
    freq = Counter()
    # 简单中文词：连续2-4个汉字
    for w in re.findall(r"[一-鿿]{2,4}", text):
        if w not in STOP and not any(s in w for s in ("可以", "一下", "我们")):
            freq[w] += 1
    top = [w for w, n in freq.most_common(20) if n >= 1
           and w[0] not in BAD_START and w[-1] not in BAD_END
           and not any(b in w for b in ("觉得", "咱们", "一点", "第二", "第一"))]
    # 分类词
    catw = [c for c, n in sorted(cat.items(), key=lambda x: -x[1]) if n > 0][:3]
    merged = list(dict.fromkeys(idkws[:2] + catw + top[:7]))
    return merged[:12]


def update_daily_stats(result):
    """把当天 built 数据转成 daily_stats 记录并追加/更新。"""
    m = result["metrics"]
    ws = datetime.fromisoformat(result["window_start"]).astimezone(CST)
    we = datetime.fromisoformat(result["window_end"]).astimezone(CST)
    cat = {k: v for k, v in result["category"].items() if v}
    tot = sum(cat.values()) or 1
    categories = {k: round(v / tot * 100) for k, v in sorted(cat.items(), key=lambda x: -x[1])}
    # 修正占比和为100
    if categories:
        d2 = 100 - sum(categories.values())
        first = next(iter(categories))
        categories[first] += d2
    hourly_cst = {str(h): v for h, v in result["hourly"].items() if v}
    active_hours = sum(1 for v in result["hourly"].values() if v)

    def hhmm(ts):
        return datetime.fromisoformat(ts).astimezone(CST).strftime("%H:%M") if ts else "--:--"

    io_ratio = round(m["tokens_out"] / max(m["tokens_in"], 1), 1)
    rec = {
        "date": result["date"],
        "weekday": ws.strftime("%A"),
        "window": {"start_cst": ws.isoformat(), "end_cst": we.isoformat()},
        "metrics": {
            "total_tokens": m["tokens_total"],
            "input_tokens": m["tokens_in"],
            "output_tokens": m["tokens_out"],
            "io_ratio": io_ratio,
            "images_generated": m["images_gen"],
            "images_edited": m["images_edit"],
            "videos_generated": 0,
            "text_chars_in": m["user_chars"],
            "text_chars_out": m["assistant_chars"],
            "user_turns": m["user_turns"],
            "assistant_turns": m["assistant_turns"],
            "tool_calls_total": m["tool_calls_total"],
            "tool_density": round(m["tool_calls_total"] / max(m["user_turns"], 1), 1),
            "problems_solved": m["user_turns"],
            "images_input": m["images_in"],
            "first_active_cst": hhmm(m["first_ts"]),
            "last_active_cst": hhmm(m["last_ts"]),
            "active_span_min": active_hours * 40,
            "hourly_cst": hourly_cst,
            "tool_calls": result["tool_calls"],
            "categories": categories,
            "identity": result["identity"]["role"],
            "keywords": result["keywords"],
            "summary": f'{m["user_turns"]} 条指令、{m["tool_calls_total"]} 次工具调用，'
                       f'今日身份：{result["identity"]["role"]}，输入输出比 1:{io_ratio}。',
        },
    }
    p = os.path.join(ROOT, "data", "daily_stats.json")
    store = json.load(open(p)) if os.path.exists(p) else {"version": 1, "days": []}
    store["days"] = [x for x in store["days"] if x["date"] != rec["date"]]
    store["days"].append(rec)
    store["days"].sort(key=lambda x: x["date"])
    json.dump(store, open(p, "w"), ensure_ascii=False, indent=2)
    return p


def main():
    now = datetime.now(CST)
    if len(sys.argv) >= 4:
        start = cs.parse_utc(sys.argv[1])
        end = cs.parse_utc(sys.argv[2])
        date = sys.argv[3]
    else:
        # 报告归属"今天"：窗口为昨日19:00 至今日18:50（Asia/Shanghai）
        report_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_cst = report_day - timedelta(days=1) + timedelta(hours=19)
        end_cst = report_day + timedelta(hours=18, minutes=50)
        start = start_cst.astimezone(timezone.utc)
        end = end_cst.astimezone(timezone.utc)
        date = report_day.strftime("%Y-%m-%d")

    sessions = cs.collect_window(start, end)
    stats = cs.summarize(sessions)
    total_calls = sum(stats["tool_calls"].values())
    cat = categorize(stats["tool_calls"])
    code = judge_identity(cat, total_calls)
    animal, role, dom, idkws, tone = IDENTITIES[code]

    # 从用户文本提取高频实词
    user_text = ""
    for sess in sessions:
        for r in sess["rows"]:
            if r.get("role") == "user" and isinstance(r.get("content"), str):
                user_text += r["content"] + " "
    keywords = extract_keywords(user_text, cat, idkws)

    result = {
        "date": date,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "identity": {"code": code, "animal": animal, "role": role, "tone": tone},
        "metrics": {
            "tokens_total": stats["user_tokens"] + stats["assistant_tokens"],
            "tokens_in": stats["user_tokens"],
            "tokens_out": stats["assistant_tokens"],
            "images_gen": stats["tool_calls"].get("image_gen", 0),
            "images_edit": stats["tool_calls"].get("image_edit", 0),
            "user_chars": stats["user_chars"],
            "assistant_chars": stats["assistant_chars"],
            "user_turns": stats["user_turns"],
            "assistant_turns": stats["assistant_turns"],
            "tool_calls_total": total_calls,
            "images_in": stats["images_in"],
            "first_ts": stats["first_ts"],
            "last_ts": stats["last_ts"],
        },
        "category": cat,
        "tool_calls": stats["tool_calls"],
        "hourly": hourly_series(stats),
        "keywords": keywords,
    }
    out_path = os.path.join(ROOT, "data", f"built_{date}.json")
    json.dump(result, open(out_path, "w"), ensure_ascii=False, indent=2)
    stats_path = update_daily_stats(result)
    print(json.dumps({"date": date, "identity": f"{code} {animal}·{role}",
                      "total_calls": total_calls, "tokens": result["metrics"]["tokens_total"],
                      "built": out_path, "daily_stats": stats_path}, ensure_ascii=False))


if __name__ == "__main__":
    main()
