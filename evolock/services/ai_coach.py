import urllib.request
import urllib.error
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from evolock.i18n import tr


def _analyze_pw_usage(pw_summary: dict) -> str:
    """Phân tích pattern dùng password — trả về đoạn text tiếng Nhật."""
    if not pw_summary:
        return ""

    stops     = pw_summary.get("total_password_stops", 0)
    em        = pw_summary.get("total_emergency", 0)
    days      = pw_summary.get("days", 7)
    morning   = pw_summary.get("morning_stops", 0)
    afternoon = pw_summary.get("afternoon_stops", 0)
    evening   = pw_summary.get("evening_stops", 0)
    by_date   = pw_summary.get("stops_by_date", {})

    lines = [tr("\n🔑 パスワード使用分析:")]

    # Tổng lần dừng học
    if stops == 0:
        lines.append(tr("  ✅ 素晴らしい！{0}日間、学習を途中で止めませんでした。").format(days))
    elif stops <= 2:
        lines.append(tr("  ⚠️ {0}日間で{1}回、学習を途中で止めました。").format(days, stops))
    elif stops <= 5:
        lines.append(tr("  ⚠️ {0}日間で{1}回と、やや止めすぎです。").format(days, stops))
    else:
        lines.append(tr("  🚨 {0}日間で{1}回も止めています。学習時間を短く設定しましょう。").format(days, stops))

    # Thời điểm hay dừng
    if stops > 0:
        peak = max(
            [(tr("朝（5〜12時）"), morning), (tr("午後（12〜18時）"), afternoon), (tr("夜（18〜24時）"), evening)],
            key=lambda x: x[1]
        )
        if peak[1] > 0:
            lines.append(tr("  📍 よく止める時間帯: {0} ({1}回)").format(peak[0], peak[1]))

    # Ngày hay dừng nhất
    if by_date:
        worst_date = max(by_date, key=lambda d: len(by_date[d]))
        worst_count = len(by_date[worst_date])
        if worst_count >= 2:
            lines.append(tr("  📅 最も多く止めた日: {0} ({1}回)").format(worst_date, worst_count))

    # Emergency code
    if em == 0:
        if stops > 0:
            lines.append(tr("  👍 緊急コードは使っていません。"))
    elif em == 1:
        lines.append(tr("  🆘 緊急コードを1回使用しました。本当に必要だったか振り返りましょう。"))
    else:
        lines.append(tr("  🚨 緊急コードを{0}回使用！意志力の強化が必要です。").format(em))

    # Đề xuất dựa trên số lần dừng
    if stops >= 3:
        lines.append(tr("  💡 提案: 学習時間を短く（15〜20分）して回数を増やしてみましょう。"))
    if em >= 2:
        lines.append(tr("  💡 提案: 緊急コードを別の場所に保管し、すぐに使えない環境を作りましょう。"))

    return "\n".join(lines)


def _linreg_slope(ys: list[float]) -> float:
    """Độ dốc hồi quy tuyến tính đơn giản (phút/ngày thay đổi mỗi ngày)."""
    n = len(ys)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in enumerate(ys))
    den = sum((x - mean_x) ** 2 for x in range(n))
    return num / den if den else 0.0


def _calc_stats(sessions):
    by_date = defaultdict(lambda: {"study": 0, "play": 0})
    for s in sessions:
        by_date[s.date][s.session_type] += s.duration_minutes

    days = sorted(by_date)
    study_per_day = [by_date[d]["study"] for d in days]
    play_per_day  = [by_date[d]["play"] for d in days]
    total_study   = sum(study_per_day)
    total_play    = sum(play_per_day)
    active_days   = sum(1 for m in study_per_day if m > 0)
    avg_study     = total_study / len(days) if days else 0
    best_day      = max(days, key=lambda d: by_date[d]["study"]) if days else None
    best_minutes  = by_date[best_day]["study"] if best_day else 0

    # Độ đều đặn: 1.0 = học đều mỗi ngày, càng gần 0 càng thất thường
    if study_per_day and avg_study > 0:
        variance = sum((m - avg_study) ** 2 for m in study_per_day) / len(study_per_day)
        stdev = math.sqrt(variance)
        consistency = max(0.0, 1 - stdev / avg_study)
    else:
        stdev, consistency = 0.0, 0.0

    # Xu hướng dựa trên độ dốc hồi quy thay vì so sánh 2 nửa (nhạy với nhiễu hơn)
    slope = _linreg_slope(study_per_day)
    if avg_study > 0 and abs(slope) / max(avg_study, 1) > 0.08:
        trend = "up" if slope > 0 else "down"
    else:
        trend = "flat"

    return {
        "days": days, "by_date": by_date,
        "total_study": total_study, "total_play": total_play,
        "active_days": active_days,
        "avg_study": avg_study, "best_day": best_day,
        "best_minutes": best_minutes, "trend": trend,
        "stdev": stdev, "consistency": consistency,
    }


def summarize_tasks(tasks) -> dict:
    """Tóm tắt danh sách Task (từ TaskManager.tasks) để đưa vào phân tích."""
    if not tasks:
        return {}
    completed = [t for t in tasks if t.completed]
    pending   = [t for t in tasks if not t.completed]
    total     = len(tasks)
    rate      = len(completed) / total if total else 0.0

    by_type = defaultdict(int)
    for t in completed:
        by_type[t.task_type] += 1
    top_type = max(by_type, key=by_type.get) if by_type else None

    return {
        "total": total, "completed": len(completed), "pending": len(pending),
        "completion_rate": rate, "by_type": dict(by_type), "top_type": top_type,
    }


def _analyze_tasks(ts: dict) -> str:
    if not ts or not ts.get("total"):
        return ""
    lines = [tr("\n📋 タスク分析:")]
    rate = ts["completion_rate"]
    lines.append(tr("  完了率: {0}/{1} ({2:.0f}%)").format(ts['completed'], ts['total'], rate * 100))
    if ts.get("top_type"):
        lines.append(tr("  よく取り組むカテゴリ: {0}").format(ts['top_type']))
    if ts["pending"] >= 5:
        lines.append(tr("  ⚠️ 未完了タスクが{0}件溜まっています。優先順位をつけて片付けましょう。").format(ts['pending']))
    elif ts["pending"] == 0:
        lines.append(tr("  ✅ 未完了タスクなし。良い状態です！"))
    return "\n".join(lines)


def _build_task_prompt(ts: dict) -> str:
    if not ts or not ts.get("total"):
        return ""
    return (
        f"\nタスクデータ：完了{ts['completed']}件 / 未完了{ts['pending']}件"
        f"（完了率{ts['completion_rate'] * 100:.0f}%、主なカテゴリ: {ts.get('top_type') or '—'}）"
    )


# ── Cửa sổ phân tích và các phát hiện do code tính ─────────────────────
# Model nhỏ hay đọc sai số hoặc bịa nguyên nhân khi phải tự suy luận từ log
# thô. Vì vậy code tính sẵn "sự thật" (kèm gợi ý hành động), model chỉ diễn đạt.

def _parse_date(s) -> date | None:
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def select_window(all_sessions, days: int = 7, today: date | None = None) -> dict:
    """Chọn khoảng `days` ngày để phân tích. Nếu 7 ngày gần đây không có phiên
    nào (lâu rồi chưa dùng app) thì lùi về tuần có dữ liệu gần nhất thay vì
    báo "không có dữ liệu" dù lịch sử vẫn còn."""
    today = today or date.today()
    dated = [(d, s) for s in all_sessions if (d := _parse_date(s.date))]
    start = today - timedelta(days=days - 1)
    recent = [s for d, s in dated if start <= d <= today]
    if recent or not dated:
        return {"start": start, "end": today, "sessions": recent,
                "stale": False, "last_date": None, "days_ago": 0}
    last = max(d for d, _ in dated)
    wstart = last - timedelta(days=days - 1)
    return {"start": wstart, "end": last,
            "sessions": [s for d, s in dated if wstart <= d <= last],
            "stale": True, "last_date": last, "days_ago": (today - last).days}


def in_window(items, window: dict) -> list:
    """Lọc các bản ghi có thuộc tính `.date` (activity/override/...) theo cửa sổ."""
    out = []
    for it in items:
        d = _parse_date(getattr(it, "date", None))
        if d and window["start"] <= d <= window["end"]:
            out.append(it)
    return out


def _time_bucket(hhmm: str) -> str | None:
    try:
        h = int(hhmm.split(":")[0])
    except (ValueError, AttributeError):
        return None
    if 5 <= h < 12:
        return "朝（5〜12時）"
    if 12 <= h < 18:
        return "午後（12〜18時）"
    if 18 <= h < 24:
        return "夜（18〜24時）"
    return "深夜（0〜5時）"


def _episodes(events, gap_minutes: int = 3) -> list[dict]:
    """Gộp các sự kiện warn/kill liên tiếp của cùng một app thành 1 "đợt" xao
    nhãng. Log ghi mỗi lần quét (3 giây) nên số sự kiện thô lớn gấp nhiều lần
    số lần thật sự mất tập trung."""
    keyed = []
    for e in events:
        try:
            dt = datetime.fromisoformat(f"{e.date}T{e.timestamp}")
        except ValueError:
            continue
        keyed.append((e.app, dt, e.kind))
    keyed.sort(key=lambda x: (x[0], x[1]))
    episodes: list[dict] = []
    for app, dt, kind in keyed:
        last = episodes[-1] if episodes else None
        if last and last["app"] == app and (dt - last["end"]) <= timedelta(minutes=gap_minutes):
            last["end"] = dt
            last["killed"] = last["killed"] or kind == "kill"
        else:
            episodes.append({"app": app, "start": dt, "end": dt, "killed": kind == "kill"})
    return episodes


OVERRIDE_HINT_DEFAULT = "止めたくなった時の理由を毎回メモに残すと、傾向が見えてくる。"
_OVERRIDE_HINTS = {
    "急用": "開始前に急ぎの用事がないか確認し、ある日は最初から短いセッションにする。",
    "休憩したい": "休憩を途中で取る前提にして、25分学習＋5分休憩のように最初から計画に入れる。",
    "予定が変わった": "予定が変わりやすい日は学習を短く区切り、完了を積み上げる。",
}


def compute_findings(all_sessions, window: dict, activity_events, override_records,
                     goal_minutes: int = 120) -> list[dict]:
    """Trả về danh sách {"fact": ..., "hint": ...}. Mọi con số do code tính."""
    findings: list[dict] = []

    def add(fact: str, hint: str = ""):
        findings.append({"fact": fact, "hint": hint})

    if window.get("stale"):
        add(tr("最後に学習したのは{0}日前（{1}）。この分析は今週ではなく、直近の学習週（{2}〜{3}）が対象。").format(window['days_ago'], window['last_date'], window['start'], window['end']),
            tr("今日の最初のセッションは短め（15〜25分）から始める。"))

    sessions = window["sessions"]
    if not sessions:
        return findings

    study = [s for s in sessions if s.session_type == "study"]
    total_study = sum(s.duration_minutes for s in study)

    # 前の週との比較
    prev_start = window["start"] - timedelta(days=7)
    prev_end = window["start"] - timedelta(days=1)
    prev = 0
    for s in all_sessions:
        d = _parse_date(s.date)
        if s.session_type == "study" and d and prev_start <= d <= prev_end:
            prev += s.duration_minutes
    if prev > 0 and total_study > 0 and abs(total_study - prev) >= 10:
        diff = total_study - prev
        word = tr("多い") if diff > 0 else tr("少ない")
        add(tr("この週の学習は合計{0}分で、その前の週（{1}分）より{2}分{3}。").format(total_study, prev, abs(diff), word),
            "" if diff > 0 else tr("まず1日1セッションを確実に取ることから戻す。"))

    # 学習が集中している時間帯
    by_bucket: dict[str, int] = defaultdict(int)
    for s in study:
        b = _time_bucket(s.start_time)
        if b:
            by_bucket[b] += s.duration_minutes
    if total_study >= 30 and by_bucket:
        b, m = max(by_bucket.items(), key=lambda kv: kv[1])
        share = round(m / total_study * 100)
        if share >= 50:
            add(tr("学習時間の{0}%（{1}分）が{2}に集中している。").format(share, m, tr(b)),
                tr("{0}に学習枠を固定すると続けやすい。").format(tr(b)))

    # 目標達成
    stats = _calc_stats(sessions)
    if goal_minutes > 0 and stats["days"]:
        study_per_day = [stats["by_date"][d]["study"] for d in stats["days"]]
        met = sum(1 for m in study_per_day if m >= goal_minutes)
        best = max(study_per_day)
        hint = ""
        if met == 0 and best > 0:
            hint = tr("目標{0}分が高すぎる可能性。最長{1}分を基準に段階的に上げる。").format(goal_minutes, best)
        add(tr("1日の目標{0}分に届いた日は、記録のある{1}日中{2}日。1日の最長は{3}分。").format(goal_minutes, len(stats['days']), met, best), hint)

    # 集中が途切れた場面
    eps = _episodes(in_window(activity_events, window))
    if eps:
        kills = sum(1 for e in eps if e["killed"])
        by_app: dict[str, int] = defaultdict(int)
        for e in eps:
            by_app[e["app"]] += 1
        top_app, top_n = max(by_app.items(), key=lambda kv: kv[1])
        add(tr("集中が途切れた場面（娯楽の兆候が続いた連続区間）は{0}回、うち強制終了{1}回。最多は{2}（{3}回）。").format(len(eps), kills, top_app, top_n),
            tr("{0}は学習中は閉じる・通知を切るなど、開きにくい状態にしておく。").format(top_app))
        by_b: dict[str, int] = defaultdict(int)
        for e in eps:
            b = _time_bucket(e["start"].strftime("%H:%M"))
            if b:
                by_b[b] += 1
        if len(eps) >= 3 and by_b:
            b, n = max(by_b.items(), key=lambda kv: kv[1])
            if n / len(eps) >= 0.5:
                add(tr("集中が途切れた場面の{0}/{1}回が{2}に起きている。").format(n, len(eps), tr(b)),
                    tr("{0}は集中が切れやすい。この時間帯は15〜20分の短いセッションにする。").format(tr(b)))

    # 早期終了
    ovr = in_window(override_records, window)
    if ovr:
        by_reason: dict[str, int] = defaultdict(int)
        for r in ovr:
            by_reason[r.reason] += 1
        top_reason, top_c = max(by_reason.items(), key=lambda kv: kv[1])
        shortfall = sum(max(0, r.planned_minutes - r.actual_minutes) for r in ovr) / len(ovr)
        # 1回のセッションで複数回止めようとすることもあるため、回数が
        # セッション数を超える場合は分母を出さない（17回/12回中、のような矛盾を避ける）。
        denom = tr("（学習セッション{0}回中）").format(len(study)) if len(ovr) <= len(study) else ""
        add(tr("予定より早く学習を終えようとしたのは{0}回{1}。最も多い理由は「{2}」{3}回、平均{4:.0f}分早く終了。").format(len(ovr), denom, tr(top_reason), top_c, shortfall),
            tr(_OVERRIDE_HINTS.get(top_reason, OVERRIDE_HINT_DEFAULT)))
        ovr_b: dict[str, int] = defaultdict(int)
        for r in ovr:
            b = _time_bucket(r.time)
            if b:
                ovr_b[b] += 1
        if len(ovr) >= 3 and ovr_b:
            b, n = max(ovr_b.items(), key=lambda kv: kv[1])
            if n / len(ovr) >= 0.5:
                add(tr("早期終了の{0}/{1}回が{2}に集中している。").format(n, len(ovr), tr(b)),
                    tr("{0}は最初から短いセッションにするか、別の時間帯に学習を移す。").format(tr(b)))

    return findings


# ── ダッシュボード用の集計（グラフの元データ） ──────────────────────────
# AIを使わず、コードだけで計算する。データがあれば分析前でもグラフを出せる。

BUCKET_ORDER = ["朝", "午後", "夜", "深夜"]


def _bucket_short(hhmm: str) -> str | None:
    full = _time_bucket(hhmm)
    return full.split("（")[0] if full else None


def compute_chart_data(all_sessions, window: dict, activity_events, override_records,
                       goal_minutes: int = 120) -> dict:
    """分析期間（window）のグラフ用データを返す。すべての数値はコードが計算する。"""
    study_by_date: dict[str, int] = defaultdict(int)
    study_by_bucket: dict[str, int] = defaultdict(int)
    for s in window["sessions"]:
        if s.session_type != "study":
            continue
        study_by_date[s.date] += s.duration_minutes
        bucket = _bucket_short(s.start_time)
        if bucket:
            study_by_bucket[bucket] += s.duration_minutes

    daily = []
    day = window["start"]
    while day <= window["end"]:
        daily.append((day.strftime("%m/%d"), study_by_date.get(str(day), 0)))
        day += timedelta(days=1)

    episodes = _episodes(in_window(activity_events, window))
    episodes_by_bucket: dict[str, int] = defaultdict(int)
    episodes_by_app: dict[str, int] = defaultdict(int)
    for e in episodes:
        bucket = _bucket_short(e["start"].strftime("%H:%M"))
        if bucket:
            episodes_by_bucket[bucket] += 1
        episodes_by_app[e["app"]] += 1

    early = in_window(override_records, window)
    study_days = [m for m in study_by_date.values() if m > 0]
    return {
        "daily": daily,
        "goal": goal_minutes,
        "study_by_bucket": [(b, study_by_bucket.get(b, 0)) for b in BUCKET_ORDER],
        "distraction_by_bucket": [(b, episodes_by_bucket.get(b, 0)) for b in BUCKET_ORDER],
        "distraction_by_app": sorted(episodes_by_app.items(), key=lambda kv: -kv[1])[:5],
        "totals": {
            "study_minutes": sum(study_by_date.values()),
            "active_days": len(study_days),
            "goal_days": sum(1 for m in study_days if goal_minutes > 0 and m >= goal_minutes),
            "episodes": len(episodes),
            "kills": sum(1 for e in episodes if e["killed"]),
            "early_stops": len(early),
        },
    }


def clean_coach_text(text: str) -> str:
    """小型モデルの出力を読みやすく整える：Markdownの記号を除き、番号付き見出しを消し、
    同じ文の繰り返しを1回にする。意味は変えない。"""
    import re
    lines = []
    pending_bullet = False
    for raw in (text or "").replace("\r", "").split("\n"):
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        if line in ("-", "*", "•", "・"):  # 記号だけの行 → 次の行を箇条書きにする
            pending_bullet = True
            continue
        if pending_bullet:
            line, pending_bullet = "・" + line, False
        # 「1. **状況のまとめ**」のような見出しだけの行は捨てる
        if re.fullmatch(r"(\d+[.．)]\s*)?(\*\*|__)[^*_]+(\*\*|__)\s*[:：]?", line):
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^\d+[.．)]\s*", "", line)
        line = re.sub(r"^[-*•]\s+", "・", line)
        line = re.sub(r"(\*\*|__|`)", "", line)
        lines.append(line.strip())

    seen: set[str] = set()
    paragraphs, current = [], []

    def flush():
        if current:
            paragraphs.append("".join(current))
            current.clear()

    for line in lines:
        if not line:
            flush()
            continue
        if line.startswith("・"):
            flush()
        kept = []
        # 全角「：」でも区切る（「見出し：本文」の本文だけが繰り返されても検出できる）。
        # 半角「:」は時刻（10:30）を壊すので区切らない。
        for sentence in re.findall(r"[^。！？!?：]+[。！？!?：]?", line):
            key = re.sub(r"\s+", "", sentence)
            if key and key not in seen:
                seen.add(key)
                kept.append(sentence)
        if kept:
            current.append("".join(kept))
            if line.startswith("・"):
                flush()
    flush()
    return "\n\n".join(p for p in paragraphs if p.strip())


def _build_prompt(sessions, window: dict | None = None) -> str:
    """Bảng học/chơi theo ngày trong cửa sổ phân tích."""
    if window is None:
        window = select_window(sessions)
    by_date = defaultdict(list)
    for s in sessions:
        by_date[s.date].append(s)
    lines = []
    d = window["start"]
    while d <= window["end"]:
        key = str(d)
        if key in by_date:
            study = sum(s.duration_minutes for s in by_date[key] if s.session_type == "study")
            play  = sum(s.duration_minutes for s in by_date[key] if s.session_type == "play")
            lines.append(f"{key}: 学習{study}分 | プレイ{play}分")
        else:
            lines.append(f"{key}: 記録なし")
        d += timedelta(days=1)
    return "\n".join(lines)


def _period_label(window: dict) -> str:
    label = f"{window['start']}〜{window['end']}"
    if window.get("stale"):
        label += tr("（最後の学習が{0}日前のため、今週ではなく直近の学習週）").format(window['days_ago'])
    return label


def _offline_analyze(sessions, pw_summary: dict | None = None,
                      task_stats: dict | None = None,
                      streak: int = 0, goal_minutes: int = 120,
                      window: dict | None = None,
                      findings: list[dict] | None = None) -> str:
    if not sessions:
        return (
            tr("📊 分析結果\n\n"
            "学習データがありません。\n"
            "「学習開始」を押して最初のセッションを記録しましょう！\n\n"
            "💪 まず今日1分だけ始めてみよう！")
        )

    window = window or select_window(sessions)
    s      = _calc_stats(sessions)
    total  = s["total_study"]
    avg    = s["avg_study"]
    active = s["active_days"]
    trend  = s["trend"]
    consistency = s["consistency"]

    lines = [tr("📊 学習分析レポート（オフライン）  {0}\n").format(_period_label(window))]

    if avg >= 60:
        lines.append(tr("✅ 素晴らしい！平均{0:.0f}分/日で安定して学習できています。").format(avg))
    elif avg >= 30:
        lines.append(tr("👍 良いペースです。平均{0:.0f}分/日、継続できています。").format(avg))
    elif avg >= 10:
        lines.append(tr("📈 平均{0:.0f}分/日。少しずつ増やしていきましょう。").format(avg))
    else:
        lines.append(tr("⚠️ 平均{0:.0f}分/日。もう少し時間を確保できると良いです。").format(avg))
    lines.append(tr("   7日間の合計: {0}分 | 学習した日: {1}/7日").format(total, active))

    # 目標達成率
    if goal_minutes > 0 and s["days"]:
        met_days = sum(1 for d in s["days"] if s["by_date"][d]["study"] >= goal_minutes)
        n_days = len(s["days"])
        if met_days == 0:
            lines.append(tr("  🎯 1日の目標（{0}分）に達した日はありませんでした。").format(goal_minutes))
        elif met_days / n_days >= 0.7:
            lines.append(tr("  🎯 目標（{0}分/日）達成: {1}/{2}日。素晴らしい達成率です！").format(goal_minutes, met_days, n_days))
        else:
            lines.append(tr("  🎯 目標（{0}分/日）達成: {1}/{2}日。もう一歩で安定達成できそうです。").format(goal_minutes, met_days, n_days))

    issues = []
    if active < 4:
        issues.append(tr("・学習できなかった日が{0}日あります。毎日少しでも続けましょう。").format(7 - active))
    if avg > 0 and consistency < 0.4:
        issues.append(tr("・日によって学習時間のムラが大きいです。同じ時間帯に学習する習慣をつけると安定します。"))
    if trend == "down":
        issues.append(tr("・後半にかけて学習時間が減っています。疲れが溜まっていませんか？"))
    if total > 0 and s["total_play"] > total * 1.5:
        issues.append(tr("・プレイ時間（{0}分）が学習時間（{1}分）を大きく上回っています。バランスを見直しましょう。").format(s['total_play'], total))
    if issues:
        lines.append(tr("\n⚠️ 改善ポイント:"))
        lines.extend(issues)

    # データから分かったこと（コードが計算した事実と、それに基づく行動提案）
    if findings:
        lines.append(tr("\n📌 データから分かったこと:"))
        for f in findings:
            lines.append(tr("・{0}").format(f['fact']))
        hints = [f["hint"] for f in findings if f["hint"]]
        if hints:
            lines.append(tr("\n💡 具体的な提案:"))
            for h in hints[:3]:
                lines.append(tr("・{0}").format(h))

    lines.append(tr("\n💡 全体の方針:"))
    if active < 7:
        lines.append(tr("・毎日同じ時間に「学習開始」を押す習慣をつけましょう。"))
    if avg < 25:
        lines.append(tr("・まず25分（ポモドーロ1セット）を目標にしてみてください。"))
    elif avg < 60:
        lines.append(tr("・60分/日を目標にもう一段階上げてみましょう。"))
    else:
        lines.append(tr("・質を高めるため、学習内容をタスクに記録すると効果的です。"))
    if trend == "up":
        lines.append(tr("・上昇傾向が続いています！この調子を維持しましょう。"))
    elif trend == "down":
        lines.append(tr("・休息も大切です。無理せず短い時間でも毎日続けましょう。"))

    cheers = {
        "up":   tr("📈 調子が上がっています！この勢いで行こう！"),
        "down": tr("🌱 コツコツ続けることが一番の近道。また明日！"),
        "flat": tr("⚡ 安定は力なり。今日も一歩前へ！"),
    }
    lines.append(f"\n{cheers[trend]}")

    if streak >= 7:
        lines.append(tr("🔥 {0}日連続でアクティブ！この調子で続けましょう。").format(streak))
    elif streak == 0 and active > 0:
        lines.append(tr("💤 連続記録が途切れています。今日からまた積み上げましょう。"))

    if task_stats:
        lines.append(_analyze_tasks(task_stats))

    if pw_summary:
        lines.append(_analyze_pw_usage(pw_summary))

    return "\n".join(lines)


def _build_pw_prompt(pw_summary: dict) -> str:
    if not pw_summary:
        return ""
    stops = pw_summary.get("total_password_stops", 0)
    em    = pw_summary.get("total_emergency", 0)
    days  = pw_summary.get("days", 7)
    return (
        f"\nパスワード使用データ（過去{days}日）："
        f"\n・学習を途中で止めた回数: {stops}回"
        f"\n・緊急コード使用回数: {em}回"
    )


COACH_SYSTEM_PROMPT = (
    "あなたはEvoLockアプリの学習コーチです。コードが集計した「事実」だけを根拠に、"
    "信頼できる先輩コーチのように自然な日本語で話しかけてください。\n"
    "厳守事項：\n"
    "・「事実」に書かれた数値と出来事だけを使う。数字を計算し直したり、書かれていない原因・理由・出来事を推測・創作しない。\n"
    "・データや事実が少ないときは、無理に結論を出さず「データがまだ少ない」と正直に伝える。\n"
    "・「絶対」「必ず」などの断定や、根拠のない励ましは避ける。\n"
    "・分析期間は「今日」ではなく「この週」「この期間」と呼ぶ。\n"
    "・同じ内容や同じ文を繰り返さない。\n"
    "・見出し、番号、太字(**)、Markdownは使わない。普通の文章だけで書く。\n"
    "・全体で250字以内。絵文字は使わない。"
)


def _build_coach_user_prompt(context: str, findings: list[dict], extra: str, window: dict) -> str:
    facts = "\n".join(
        f"・{f['fact']}" + (f"\n  ヒント案: {f['hint']}" if f["hint"] else "")
        for f in findings
    ) or "・特筆すべき事実なし"
    return (
        f"分析期間: {_period_label(window)}\n\n"
        f"日ごとの記録:\n{context}\n\n"
        f"事実（コードが集計した正確な数値）:\n{facts}\n\n"
        f"補足:{extra}\n\n"
        "画面には数値のグラフと事実の一覧がすでに表示されています。数値を並べ直さず、"
        "コーチとしての短いコメントだけを書いてください。\n"
        "・最初に、この期間の様子を1〜2文で。\n"
        "・次に、事実の中で最も大切なものを最大2つ選び、「・」で始まる短い行動提案を1行ずつ。"
        "ヒント案があれば参考にしてよい。\n"
        "・最後に一言の励まし。"
    )


def _assemble_prompt(sessions, window: dict, findings: list[dict],
                     pw_summary: dict | None, task_stats: dict | None,
                     streak: int, goal_minutes: int, language: str = "ja") -> str:
    extra = (
        _build_pw_prompt(pw_summary or {})
        + _build_task_prompt(task_stats or {})
        + f"\n連続アクティブ日数: {streak}日\n1日の目標学習時間: {goal_minutes}分"
    )
    prompt = _build_coach_user_prompt(_build_prompt(sessions, window), findings, extra, window)
    # プロンプト自体は日本語のまま、出力する言語だけ指定する（事実の数値は変えない）。
    answer_language = {"vi": "ベトナム語", "en": "英語"}.get(language)
    if answer_language:
        prompt += f"\n\n回答は必ず{answer_language}で書いてください。数値と固有名詞はそのまま使うこと。"
    return prompt


def _ollama_analyze(model: str, prompt: str) -> str:
    payload = json.dumps({
        "model":  model,
        "messages": [
            {"role": "system", "content": COACH_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.3},
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # コーチ分析はリアルタイム性不要（ボタンを押した時だけ実行）なので、
    # ブロッカーのScreen AIより長めのタイムアウトを許容する。
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["message"]["content"]


def _tidy(text: str) -> str:
    return clean_coach_text(text) or text


def analyze(api_key: str, sessions, ollama_model: str = "",
            pw_summary: dict | None = None, task_stats: dict | None = None,
            streak: int = 0, goal_minutes: int = 120,
            window: dict | None = None,
            findings: list[dict] | None = None,
            language: str = "ja") -> str:
    """`sessions` は window 内の学習セッション。window/findings を渡さない場合は
    sessions のみから自動で作る（アクティビティ・早期終了の事実は含まれない）。"""
    window = window or select_window(sessions)
    if findings is None:
        findings = compute_findings(sessions, window, [], [], goal_minutes)

    def offline() -> str:
        return _offline_analyze(sessions, pw_summary, task_stats, streak,
                                goal_minutes, window, findings)

    if not sessions:
        return offline()

    prompt = _assemble_prompt(sessions, window, findings, pw_summary,
                              task_stats, streak, goal_minutes, language)

    # 優先度: Ollama → Anthropic API → オフライン
    if ollama_model:
        try:
            return _tidy(_ollama_analyze(ollama_model, prompt))
        except urllib.error.URLError:
            return (
                tr("⚠️ Ollamaに接続できません。\n"
                   "Ollamaが起動しているか確認してください: ollama serve\n\n") + offline()
            )
        except Exception as e:
            return tr("⚠️ Ollamaエラー: {0}\n\n").format(e) + offline()

    if api_key:
        try:
            import anthropic
            client   = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                temperature=0.3,
                system=COACH_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return _tidy(response.content[0].text)
        except ImportError:
            pass
        except Exception as e:
            return tr("APIエラー: {0}\n\n").format(e) + offline()

    return offline()
