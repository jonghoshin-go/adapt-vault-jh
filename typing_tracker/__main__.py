import argparse

from . import demo, report, storage, tracker


def main():
    p = argparse.ArgumentParser(prog="python -m typing_tracker", description="업무 중 타이핑 속도 측정·분석")
    p.add_argument("--db", help=f"DB 경로 (기본: {storage.DEFAULT_DB})")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("track", help="백그라운드 측정 시작")
    t.add_argument("--idle-gap", type=float, default=tracker.IDLE_GAP, help="연속 타이핑으로 볼 최대 키 간격(초)")
    t.add_argument("-v", "--verbose", action="store_true", help="저장할 때마다 분 단위 결과 출력")

    r = sub.add_parser("report", help="시간대·요일별 리포트 생성")
    r.add_argument("-o", "--out", default="typing_report.html")
    r.add_argument("--start", type=int, default=9, help="업무 시작 시각 (기본 9)")
    r.add_argument("--end", type=int, default=18, help="업무 종료 시각 (기본 18)")
    r.add_argument("--weekends", action="store_true", help="주말 포함")
    r.add_argument("--days", type=int, help="최근 N일만 분석")

    d = sub.add_parser("demo", help="가짜 데이터로 리포트 미리보기용 DB 생성")
    d.add_argument("--weeks", type=int, default=4)

    a = p.parse_args()
    if a.cmd == "track":
        tracker.run(a.db, a.idle_gap, a.verbose)
    elif a.cmd == "report":
        report.run(a.db, a.out, a.start, a.end, a.weekends, a.days)
    elif a.cmd == "demo":
        demo.generate(a.db or "demo.db", a.weeks)


if __name__ == "__main__":
    main()
