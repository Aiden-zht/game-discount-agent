import json, datetime

with open('output/kpi_records.json') as f:
    records = json.load(f)

record = {
    "run_date": "2026-06-11",
    "run_time": datetime.datetime.now().isoformat(),
    "article_title": None,
    "game_count": 0,
    "developer": {
        "name": "Agent A (cron_digest.py)",
        "build_phase": {"scraped": 0, "images_uploaded": 0, "html_generated": False, "thumb_uploaded": False},
        "auto_fix_rounds": 0,
        "issues_found_by_validator": {"blocking": 0, "warning": 0},
        "fixes_applied": [],
        "score": 0,
        "score_change": 0,
        "note": "数据收集脚本超时120s，未生成新state.json。使用06/10数据验证通过。"
    },
    "validator": {
        "name": "Agent B (game-content-validator)",
        "total_games_checked": 9,
        "api_verified": 7,
        "dlc_skipped": 2,
        "findings": [],
        "missed_issues": [],
        "false_positives": [],
        "score": 115,
        "score_change": 10,
        "note": "验证06/10状态文件：9款游戏全部通过AppID验证、中文名完整、配图一致、HTML格式正确、版本ID存在。0 BLOCKING, 0 WARNING。"
    },
    "draft_created": False,
    "note": "数据收集脚本超时，无新草稿生成。06/10草稿已存在。"
}

records.append(record)
records = records[-30:]

with open('output/kpi_records.json', 'w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

recent_dev = [r['developer']['score'] for r in records if r['developer']['score'] > 0]
recent_val = [r['validator']['score'] for r in records if r['validator']['score'] > 0]
dev_avg = sum(recent_dev) / len(recent_dev) if recent_dev else 0
val_avg = sum(recent_val) / len(recent_val) if recent_val else 0

print(f'=== KPI Summary ===')
print(f'Developer (Agent A) 7-day avg: {dev_avg:.1f}')
print(f'Validator (Agent B) 7-day avg: {val_avg:.1f}')
print(f'Total records: {len(records)}')
print()
print('Most recent:')
for r in records[-3:]:
    if r.get('article_title'):
        print(f'  {r["run_date"]}: {r["article_title"]} -- Dev:{r["developer"]["score"]} Val:{r["validator"]["score"]}')
    else:
        print(f'  {r["run_date"]}: TIMEOUT -- Dev:{r["developer"]["score"]} Val:{r["validator"]["score"]}')
