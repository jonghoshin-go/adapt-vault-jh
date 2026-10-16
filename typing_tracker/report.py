"""수집된 분 단위 데이터로 시간대·요일별 타이핑 속도 리포트를 만든다."""
import html
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta

from . import storage

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
MIN_ACTIVE_SEC = 180   # 한 칸(예: 화요일 10시)에 연속 타이핑이 3분 미만이면 '표본 부족'


class Cell:
    """여러 분(minute)을 합친 통계. 속도는 합계 기준(가중평균)으로 계산한다."""

    def __init__(self):
        self.keys = self.active_keys = self.backspaces = 0
        self.active_seconds = 0.0
        self.days = set()
        self.per_day = defaultdict(lambda: [0, 0.0])  # date -> [active_keys, active_seconds]

    def add(self, d, keys, active_keys, active_seconds, backspaces):
        self.keys += keys
        self.active_keys += active_keys
        self.active_seconds += active_seconds
        self.backspaces += backspaces
        if active_seconds > 0:
            self.days.add(d)
            pd = self.per_day[d]
            pd[0] += active_keys
            pd[1] += active_seconds

    @property
    def speed(self):
        return self.active_keys / self.active_seconds * 60 if self.active_seconds else None

    @property
    def backspace_ratio(self):
        return self.backspaces / self.keys if self.keys else None

    @property
    def enough(self):
        return self.active_seconds >= MIN_ACTIVE_SEC

    @property
    def day_spread(self):
        """일자별 속도의 표준편차 (같은 시간대라도 날마다 얼마나 들쭉날쭉한지)."""
        speeds = [k / s * 60 for k, s in self.per_day.values() if s >= 60]
        return statistics.stdev(speeds) if len(speeds) >= 2 else None


def analyze(rows, start_hour=9, end_hour=18, weekends=False, days=None):
    since = date.today() - timedelta(days=days) if days else None
    total, by_hour, by_wd, by_date = Cell(), defaultdict(Cell), defaultdict(Cell), defaultdict(Cell)
    heat = defaultdict(Cell)
    for minute_start, keys, ak, sec, bs in rows:
        dt = datetime.strptime(minute_start, "%Y-%m-%d %H:%M")
        d = dt.date()
        if since and d < since:
            continue
        if not (start_hour <= dt.hour < end_hour):
            continue
        if not weekends and dt.weekday() >= 5:
            continue
        for c in (total, by_hour[dt.hour], by_wd[dt.weekday()], by_date[d], heat[(dt.weekday(), dt.hour)]):
            c.add(d, keys, ak, sec, bs)
    hours = list(range(start_hour, end_hour))
    wds = list(range(7 if weekends else 5))
    return dict(total=total, by_hour=by_hour, by_wd=by_wd, by_date=by_date, heat=heat,
                hours=hours, wds=wds)


# ---------------------------------------------------------------- 텍스트 요약

def _rank(cells, label):
    ok = [(k, c) for k, c in cells.items() if c.enough]
    ok.sort(key=lambda kc: kc[1].speed, reverse=True)
    return [(label(k), c) for k, c in ok]


def summary_lines(a):
    t = a["total"]
    if not t.active_seconds:
        return ["아직 업무 시간대에 수집된 데이터가 없습니다."]
    lines = [
        f"전체 평균 속도: {t.speed:.0f} 타/분  (연속 타이핑 {t.active_seconds/60:.0f}분, {len(t.days)}일, "
        f"수정키 비율 {t.backspace_ratio:.1%})",
    ]
    hr = _rank(a["by_hour"], lambda h: f"{h:02d}시")
    wd = _rank(a["by_wd"], lambda w: f"{WEEKDAYS[w]}요일")
    for title, ranked in (("시간대", hr), ("요일", wd)):
        if len(ranked) >= 2:
            (fk, fc), (sk, sc) = ranked[0], ranked[-1]
            diff = (fc.speed - sc.speed) / sc.speed
            lines.append(f"{title}: 가장 빠름 {fk} {fc.speed:.0f} 타/분 · 가장 느림 {sk} {sc.speed:.0f} 타/분 "
                         f"→ 차이 {diff:+.0%}")
    if len(t.days) < 10:
        lines.append(f"※ 아직 {len(t.days)}일치 데이터라 패턴이 우연일 수 있습니다. 2~4주 이상 모아보세요.")
    return lines


# ---------------------------------------------------------------- HTML 리포트

def _color(v, lo, hi):
    if v is None or hi <= lo:
        return "var(--empty)"
    x = max(0.0, min(1.0, (v - lo) / (hi - lo)))
    # 느림(주황) → 빠름(파랑)
    return f"color-mix(in oklab, var(--slow) {100 - x*100:.0f}%, var(--fast))"


def _bars(cells, keys, label, lo, hi):
    out = []
    for k in keys:
        c = cells.get(k)
        sp = c.speed if c else None
        w = 0 if sp is None else max(2, (sp - lo * 0.8) / (hi - lo * 0.8) * 100)
        cls = "" if c and c.enough else " weak"
        val = f"{sp:.0f}" if sp is not None else "–"
        sub = f"{c.active_seconds/60:.0f}분 · {len(c.days)}일" if c else "데이터 없음"
        if c and c.backspace_ratio is not None:
            sub += f" · 수정 {c.backspace_ratio:.0%}"
        out.append(
            f'<div class="bar{cls}"><span class="lbl">{label(k)}</span>'
            f'<span class="track"><span class="fill" style="width:{w:.0f}%;background:{_color(sp, lo, hi)}"></span></span>'
            f'<span class="val">{val}</span><span class="sub">{sub}</span></div>'
        )
    return "\n".join(out)


def render_html(a, title="타이핑 속도 리포트"):
    heat, hours, wds = a["heat"], a["hours"], a["wds"]
    speeds = [c.speed for c in list(heat.values()) + list(a["by_hour"].values()) + list(a["by_wd"].values())
              if c.enough]
    lo, hi = (min(speeds), max(speeds)) if speeds else (0, 1)

    head = "".join(f"<th>{h:02d}</th>" for h in hours)
    body = []
    for w in wds:
        tds = []
        for h in hours:
            c = heat.get((w, h))
            if not c or not c.active_seconds:
                tds.append('<td class="na">·</td>')
                continue
            tip = f"{WEEKDAYS[w]} {h:02d}시: {c.speed:.0f} 타/분, 연속 타이핑 {c.active_seconds/60:.1f}분, {len(c.days)}일"
            cls = "" if c.enough else ' class="weak"'
            tds.append(f'<td{cls} style="background:{_color(c.speed, lo, hi)}" title="{html.escape(tip)}">'
                       f'{c.speed:.0f}</td>')
        body.append(f"<tr><th>{WEEKDAYS[w]}</th>{''.join(tds)}</tr>")

    dates = sorted(a["by_date"])
    trend = _bars(a["by_date"], dates[-21:], lambda d: f"{d:%m/%d}({WEEKDAYS[d.weekday()]})", lo, hi)
    summary = "".join(f"<li>{html.escape(s)}</li>" for s in summary_lines(a))
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ --bg:#fbfaf8; --fg:#1f2328; --muted:#6b7280; --line:#e5e3df; --card:#fff;
        --slow:#e8833a; --fast:#2f6fdb; --empty:#eeece8; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#16181c; --fg:#e8e6e3; --muted:#9aa0a6; --line:#2b2f36; --card:#1d2026;
          --slow:#c96a28; --fast:#4c8ef0; --empty:#262a31; }} }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.55 -apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif; }}
main {{ max-width:980px; margin:0 auto; padding:32px 16px 64px }}
h1 {{ font-size:24px; margin:0 0 4px }} h2 {{ font-size:17px; margin:36px 0 10px }}
.meta,.note {{ color:var(--muted); font-size:13px }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px }}
ul.sum {{ margin:0; padding-left:18px }} ul.sum li {{ margin:4px 0 }}
.scroll {{ overflow-x:auto }}
table.heat {{ border-collapse:separate; border-spacing:3px; font-variant-numeric:tabular-nums }}
table.heat th {{ font-weight:500; color:var(--muted); font-size:12px; padding:2px 6px }}
table.heat td {{ width:52px; height:38px; text-align:center; border-radius:6px; color:#fff; font-weight:600; font-size:13px }}
table.heat td.na {{ background:var(--empty); color:var(--muted); font-weight:400 }}
.weak {{ opacity:.45 }}
.bar {{ display:grid; grid-template-columns:84px 1fr 48px; grid-template-rows:auto auto; column-gap:10px; align-items:center; margin:6px 0 }}
.bar .lbl {{ font-size:13px }} .bar .val {{ text-align:right; font-weight:600; font-variant-numeric:tabular-nums }}
.bar .track {{ height:14px; background:var(--empty); border-radius:7px; overflow:hidden }}
.bar .fill {{ display:block; height:100% }}
.bar .sub {{ grid-column:2 / 4; font-size:11.5px; color:var(--muted) }}
.legend {{ display:flex; align-items:center; gap:8px; font-size:12px; color:var(--muted); margin-top:8px }}
.legend .g {{ width:120px; height:10px; border-radius:5px; background:linear-gradient(90deg,var(--slow),var(--fast)) }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px }}
@media (max-width:720px) {{ .grid2 {{ grid-template-columns:1fr }} }}
</style></head><body><main>
<h1>{html.escape(title)}</h1>
<div class="meta">생성 {generated} · 업무시간 {hours[0]:02d}–{hours[-1]+1:02d}시 · 단위: 타/분 (연속 타이핑 구간 기준)</div>

<h2>요약</h2>
<div class="card"><ul class="sum">{summary}</ul></div>

<h2>요일 × 시간대</h2>
<div class="card scroll">
<table class="heat"><tr><th></th>{head}</tr>{''.join(body)}</table>
<div class="legend">느림 <span class="g"></span> 빠름 · 흐린 칸 = 연속 타이핑 {MIN_ACTIVE_SEC//60}분 미만(표본 부족)</div>
</div>

<div class="grid2">
<div><h2>시간대별</h2><div class="card">{_bars(a["by_hour"], hours, lambda h: f"{h:02d}시", lo, hi)}</div></div>
<div><h2>요일별</h2><div class="card">{_bars(a["by_wd"], wds, lambda w: f"{WEEKDAYS[w]}요일", lo, hi)}</div></div>
</div>

<h2>최근 일자별</h2>
<div class="card">{trend or '<span class="note">데이터 없음</span>'}</div>

<p class="note">속도 = 키 간격 2초 이하인 연속 타이핑 구간의 타건 수 ÷ 그 시간. 생각하거나 회의하느라 쉰 시간은 빠집니다.
'수정'은 전체 타건 중 Backspace/Delete 비율로, 높을수록 오타·고쳐쓰기가 많다는 뜻입니다.</p>
</main></body></html>"""


def run(db_path=None, out="typing_report.html", start_hour=9, end_hour=18, weekends=False, days=None):
    conn = storage.connect(db_path)
    rows = storage.load_minutes(conn)
    conn.close()
    a = analyze(rows, start_hour, end_hour, weekends, days)
    for line in summary_lines(a):
        print(line)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render_html(a))
    print(f"\nHTML 리포트: {out}")
