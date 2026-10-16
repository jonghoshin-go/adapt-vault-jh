"""백그라운드에서 키 입력 '타이밍'만 기록하는 트래커.

속도 정의
---------
업무 중에는 타이핑 → 생각 → 회의 → 타이핑 처럼 쉬는 시간이 섞여 있다.
그래서 '1시간 동안 몇 타를 쳤나'는 속도가 아니라 '얼마나 많이 쳤나'에 가깝다.

여기서는 키 사이 간격이 IDLE_GAP(기본 2초) 이하인 것만 '연속 타이핑'으로 보고,
    속도(타/분) = 연속 구간 타건 수 / 연속 구간 시간 × 60
으로 계산한다. 즉 '손이 키보드 위에서 움직이고 있을 때의 순수 속도'다.
"""
import signal
import threading
import time
from datetime import datetime

from . import storage

IDLE_GAP = 2.0        # 이 간격(초)을 넘으면 연속 타이핑이 끊긴 것으로 본다
FLUSH_INTERVAL = 30   # DB 저장 주기(초)


class Aggregator:
    def __init__(self, idle_gap=IDLE_GAP):
        self.idle_gap = idle_gap
        self.lock = threading.Lock()
        self.buckets = {}
        self.last_ts = None

    def record(self, ts, is_backspace):
        minute = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        with self.lock:
            b = self.buckets.setdefault(minute, [0, 0, 0.0, 0])
            b[0] += 1
            if self.last_ts is not None:
                gap = ts - self.last_ts
                if 0 < gap <= self.idle_gap:
                    b[1] += 1
                    b[2] += gap
            if is_backspace:
                b[3] += 1
            self.last_ts = ts

    def drain(self):
        with self.lock:
            out, self.buckets = self.buckets, {}
        return out


def run(db_path=None, idle_gap=IDLE_GAP, verbose=False):
    try:
        from pynput import keyboard
    except ImportError:
        raise SystemExit("pynput 이 필요합니다:  pip install pynput")

    K = keyboard.Key
    modifiers = {K.ctrl, K.ctrl_l, K.ctrl_r, K.alt, K.alt_l, K.alt_r, K.alt_gr,
                 K.cmd, K.cmd_l, K.cmd_r}
    # 글자를 만드는 특수키만 타이핑으로 센다 (방향키·F키·Shift 등은 제외)
    typing_special = {K.space, K.enter, K.backspace, K.delete}
    ime_vks = {0x15, 0x19}  # Windows 한/영(VK_HANGUL), 한자(VK_HANJA) 키는 제외

    agg = Aggregator(idle_gap)
    held = set()
    held_mods = set()
    conn = storage.connect(db_path)
    stop = threading.Event()

    def on_press(key):
        if key in modifiers:
            held_mods.add(key)
            return
        if key in held:          # 키를 누르고 있어서 생기는 자동반복은 무시
            return
        held.add(key)
        if held_mods:            # Ctrl+C, Alt+Tab 같은 단축키는 타이핑이 아님
            return
        if isinstance(key, keyboard.KeyCode):
            if getattr(key, "vk", None) in ime_vks:
                return
            agg.record(time.time(), False)
        elif key in typing_special:
            agg.record(time.time(), key in (K.backspace, K.delete))

    def on_release(key):
        held_mods.discard(key)
        held.discard(key)

    def flush():
        buckets = agg.drain()
        if buckets:
            storage.add_minutes(conn, buckets)
            if verbose:
                for m, (k, ak, sec, bs) in sorted(buckets.items()):
                    spd = ak / sec * 60 if sec else 0
                    print(f"{m}  타건 {k:4d}  연속 {sec:5.1f}s  속도 {spd:5.0f} 타/분  수정 {bs}")

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: stop.set())

    print(f"타이핑 측정 시작 (DB: {db_path or storage.DEFAULT_DB}). 종료: Ctrl+C")
    print("※ 키 내용은 저장하지 않고, 분 단위 타건 수와 타이핑 시간만 기록합니다.")
    try:
        while not stop.wait(FLUSH_INTERVAL):
            flush()
    finally:
        listener.stop()
        flush()
        conn.close()
        print("측정 종료, 저장 완료.")
