"""분 단위 타이핑 통계를 SQLite에 저장/조회한다.

키 내용(어떤 글자를 눌렀는지)은 절대 저장하지 않는다.
분(minute) 단위로 '몇 번 눌렀는지'와 '실제로 타이핑한 시간'만 남긴다.
"""
import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(os.environ.get("TYPING_TRACKER_DB", Path.home() / ".typing_tracker" / "typing.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS minute_stats (
    minute_start   TEXT PRIMARY KEY,   -- 로컬 시각 'YYYY-MM-DD HH:MM'
    keys           INTEGER NOT NULL,   -- 이 분에 눌린 전체 타건 수
    active_keys    INTEGER NOT NULL,   -- 연속 타이핑 구간 안에서 눌린 타건 수
    active_seconds REAL    NOT NULL,   -- 연속 타이핑 구간의 실제 시간(초)
    backspaces     INTEGER NOT NULL    -- 백스페이스/Delete 횟수 (수정 빈도)
);
"""


def connect(db_path=None):
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(SCHEMA)
    return conn


def add_minutes(conn, buckets):
    """buckets: {minute_start: [keys, active_keys, active_seconds, backspaces]} 를 누적 저장."""
    conn.executemany(
        """
        INSERT INTO minute_stats (minute_start, keys, active_keys, active_seconds, backspaces)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(minute_start) DO UPDATE SET
            keys           = keys           + excluded.keys,
            active_keys    = active_keys    + excluded.active_keys,
            active_seconds = active_seconds + excluded.active_seconds,
            backspaces     = backspaces     + excluded.backspaces
        """,
        [(m, *v) for m, v in buckets.items()],
    )
    conn.commit()


def load_minutes(conn):
    cur = conn.execute(
        "SELECT minute_start, keys, active_keys, active_seconds, backspaces FROM minute_stats ORDER BY minute_start"
    )
    return cur.fetchall()
