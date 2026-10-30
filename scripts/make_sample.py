#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成完全编造的示例数据 sample_data.json，用于公开 Demo（不含任何真实用户数据）。
用法: python3 make_sample.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 示例固定日期（中性、可解析）
DATE = "2026-10-15"

# 24 小时活跃分布（编造）：深夜一小波 + 上午高峰 + 下午高峰
hourly = {
    0: 18, 1: 6, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0,
    8: 12, 9: 46, 10: 58, 11: 40, 12: 16,
    13: 8, 14: 22, 15: 52, 16: 44, 17: 20,
    18: 0, 19: 0, 20: 0, 21: 0, 22: 0, 23: 0,
}

# 5 类任务（均衡，符合"全能多面手"），合计 248
category = {
    "工程与读写": 120,
    "视觉创作": 56,
    "任务统筹": 40,
    "交付与调度": 20,
    "检索研究": 12,
}

# 工具调用明细（编造，按分类对齐，合计 248）
tool_calls = {
    # 工程与读写 120
    "Bash": 46, "Read": 38, "Edit": 20, "Write": 10, "Grep": 6,
    # 视觉创作 56
    "image_gen": 12, "image_edit": 3, "text_to_video": 18, "image_to_video": 14,
    "text_to_audio_plus": 9,
    # 任务统筹 40
    "task_update": 22, "task_create": 14, "manage_preference": 4,
    # 交付与调度 20
    "present_files": 12, "Wait": 6, "get_current_time": 2,
    # 检索研究 12
    "general_search": 7, "web.fetch": 5,
}

sample = {
    "date": DATE,
    "window_start": "2026-10-14T11:00:00+00:00",
    "window_end": "2026-10-15T10:50:00+00:00",
    "identity": {"code": "MIX-08", "animal": "浣熊", "role": "全能多面手", "tone": "均衡"},
    "metrics": {
        "tokens_total": 8888,
        "tokens_in": 1200,
        "tokens_out": 7688,
        "images_gen": 12,
        "images_edit": 3,
        "user_chars": 950,
        "assistant_chars": 6420,
        "user_turns": 16,
        "assistant_turns": 280,
        "tool_calls_total": 248,
        "images_in": 2,
        "first_ts": "2026-10-14T16:05:00+00:00",
        "last_ts": "2026-10-15T09:48:00+00:00",
    },
    "category": category,
    "tool_calls": tool_calls,
    "hourly": hourly,
    "keywords": ["创意", "设计", "多任务", "工程", "视觉", "复盘", "统筹", "写作", "调试", "灵感"],
}

out = os.path.join(ROOT, "data", "sample_data.json")
json.dump(sample, open(out, "w"), ensure_ascii=False, indent=2)
print(json.dumps({"sample": out, "date": DATE, "tool_calls": sum(tool_calls.values()),
                  "category_sum": sum(category.values())}, ensure_ascii=False))
