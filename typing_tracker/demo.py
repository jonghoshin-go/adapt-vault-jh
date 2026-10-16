"""리포트를 미리 확인해 볼 수 있도록 가짜 4주치 데이터를 만든다 (실제 측정과 무관)."""
import random
from datetime import date, datetime, timedelta

from . import storage


def generate(db_path, weeks=4, seed=7):
    rnd = random.Random(seed)
    buckets = {}
    start = date.today() - timedelta(weeks=weeks)
    for i in range(weeks * 7):
        d = start + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        day_mood = rnd.gauss(0, 15)
        for h in range(9, 19):
            # 오전 10~11시 집중, 점심 직후 처짐, 월요일 오전·금요일 오후 느림
            base = 330 + {9: -20, 10: 25, 11: 30, 12: -10, 13: -45, 14: -25, 15: 5, 16: 10, 17: -5, 18: -30}[h]
            if d.weekday() == 0 and h < 12:
                base -= 30
            if d.weekday() == 4 and h >= 15:
                base -= 35
            for m in range(60):
                if h == 12 or rnd.random() > 0.35:   # 점심·회의 등으로 안 친 분
                    continue
                sec = rnd.uniform(5, 40)
                spd = max(80, rnd.gauss(base + day_mood, 35))
                ak = int(spd * sec / 60)
                keys = ak + rnd.randint(1, 4)
                bs = int(keys * rnd.uniform(0.04, 0.12))
                key = datetime(d.year, d.month, d.day, h, m).strftime("%Y-%m-%d %H:%M")
                buckets[key] = [keys, ak, sec, bs]
    conn = storage.connect(db_path)
    storage.add_minutes(conn, buckets)
    conn.close()
    print(f"데모 데이터 {len(buckets)}분치 생성: {db_path}")
