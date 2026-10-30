#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包每日数据采集脚本
扫描所有会话的 trajectory.jsonl + assignment.md，按时间窗口输出活动统计。
用法: python3 collect_stats.py <window_start_utc> <window_end_utc>
例如: python3 collect_stats.py 2026-10-27T11:00:00 2026-10-28T10:50:00
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

# 会话数据根目录：优先读环境变量，默认指向豆包桌面端的标准安装路径。
# 若你的数据目录不同，设置环境变量 DOUBAO_SESSIONS_ROOT 覆盖，例如:
#   export DOUBAO_SESSIONS_ROOT="/your/path/.sessions"
SESSIONS_ROOT = os.environ.get(
    "DOUBAO_SESSIONS_ROOT",
    os.path.expanduser("~/.doubao/agent_mode/workspace/.sessions"),
)

ASSIGN_TS_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)Z\]\s*需求")


def parse_utc(s):
    """解析时间戳；naive（无 Z/时区）一律按 UTC 处理。"""
    dt = datetime.fromisoformat(s.replace("Z", ""))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_assignment_timestamps(path):
    """从 assignment.md 提取用户 turn 时间戳列表（UTC datetime）。"""
    ts_list = []
    if not os.path.exists(path):
        return ts_list
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = ASSIGN_TS_RE.match(line.strip())
            if m:
                ts_list.append(parse_utc(m.group(1)))
    return ts_list


def cjk_count(text):
    """统计中日韩字符数。"""
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" or "\uac00" <= ch <= "\ud7af")


def estimate_tokens(text):
    """粗估 Token：中文等 CJK 字符约 1 字 ≈ 1.3 token；其余按约 4 字符/token。"""
    if not text:
        return 0
    cjk = cjk_count(text)
    other = len(text) - cjk
    return int(cjk * 1.3 + other / 4)


def collect_window(start_utc, end_utc):
    sessions = []
    for session_id in sorted(os.listdir(SESSIONS_ROOT)):
        sdir = os.path.join(SESSIONS_ROOT, session_id)
        if not os.path.isdir(sdir):
            continue
        agents_dir = os.path.join(sdir, "agents")
        if not os.path.isdir(agents_dir):
            continue
        for agent_id in sorted(os.listdir(agents_dir)):
            adir = os.path.join(agents_dir, agent_id)
            traj_path = os.path.join(adir, "system", "trajectory.jsonl")
            assign_path = os.path.join(adir, "system", "assignment.md")
            if not os.path.exists(traj_path):
                continue
            user_ts = parse_assignment_timestamps(assign_path)
            ts_idx = 0
            rows = []
            with open(traj_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    row_ts = None
                    if d.get("role") == "user":
                        if ts_idx < len(user_ts):
                            row_ts = user_ts[ts_idx]
                            ts_idx += 1
                    else:
                        # 归属到最近一个用户 turn
                        if ts_idx > 0:
                            row_ts = user_ts[ts_idx - 1]
                    d["_ts"] = row_ts.isoformat() if row_ts else None
                    d["_session"] = session_id
                    d["_agent"] = agent_id
                    rows.append(d)
            # 窗口过滤
            in_window = [r for r in rows if r["_ts"] and start_utc <= parse_utc(r["_ts"]) < end_utc]
            if in_window:
                sessions.append({
                    "session_id": session_id,
                    "agent_id": agent_id,
                    "rows": in_window,
                })
    return sessions


def summarize(sessions):
    stats = {
        "user_turns": 0,
        "assistant_turns": 0,
        "user_chars": 0,
        "assistant_chars": 0,
        "user_tokens": 0,
        "assistant_tokens": 0,
        "images_in": 0,
        "tool_calls": {},
        "tool_call_details": [],
        "hourly_activity": {},
        "first_ts": None,
        "last_ts": None,
    }
    for sess in sessions:
        for r in sess["rows"]:
            role = r.get("role")
            ts = parse_utc(r["_ts"])
            if not stats["first_ts"] or ts < parse_utc(stats["first_ts"]):
                stats["first_ts"] = r["_ts"]
            if not stats["last_ts"] or ts > parse_utc(stats["last_ts"]):
                stats["last_ts"] = r["_ts"]
            # 转为 +8 小时桶
            hour_cst = (ts.hour + 8) % 24
            content = r.get("content")
            if role == "user":
                stats["user_turns"] += 1
                if isinstance(content, str):
                    stats["user_chars"] += len(content)
                    stats["user_tokens"] += estimate_tokens(content)
                for img in r.get("image_link_list", []) or []:
                    stats["images_in"] += 1
                stats["hourly_activity"][hour_cst] = stats["hourly_activity"].get(hour_cst, 0) + 1
            elif role == "assistant":
                stats["assistant_turns"] += 1
                if isinstance(content, str):
                    stats["assistant_chars"] += len(content)
                    stats["assistant_tokens"] += estimate_tokens(content)
                stats["hourly_activity"][hour_cst] = stats["hourly_activity"].get(hour_cst, 0) + 1
                for tc in r.get("tool_calls", []) or []:
                    fn = tc.get("function", {})
                    name = fn.get("name", "?")
                    raw_args = fn.get("arguments", {})
                    if isinstance(raw_args, dict):
                        args = raw_args
                    elif isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args)
                        except json.JSONDecodeError:
                            args = {}
                    else:
                        args = {}
                    count = 1
                    if name in ("image_gen", "image_edit") and isinstance(args.get("request_list"), list):
                        count = len(args["request_list"])
                    stats["tool_calls"][name] = stats["tool_calls"].get(name, 0) + count
                    stats["tool_call_details"].append({
                        "tool": name,
                        "ts": r["_ts"],
                        "count": count,
                        "session": sess["session_id"],
                    })
            elif role == "tool":
                stats["hourly_activity"][hour_cst] = stats["hourly_activity"].get(hour_cst, 0) + 1
    return stats


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    start = parse_utc(sys.argv[1])
    end = parse_utc(sys.argv[2])
    sessions = collect_window(start, end)
    stats = summarize(sessions)
    out = {
        "window_start_utc": start.isoformat(),
        "window_end_utc": end.isoformat(),
        "sessions_in_window": [
            {"session_id": s["session_id"], "agent_id": s["agent_id"], "row_count": len(s["rows"])}
            for s in sessions
        ],
        "stats": stats,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
