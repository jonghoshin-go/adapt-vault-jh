# 타이핑 속도 측정기 (typing_tracker)

업무 중 타이핑 속도가 **몇 시에, 무슨 요일에** 빠르고 느린지 확인하기 위한 도구입니다.
백그라운드에서 키 입력 타이밍을 기록하고, 시간대·요일별 리포트(HTML)를 만듭니다.

## 개인정보
- **어떤 키를 눌렀는지(글자 내용)는 저장하지 않습니다.** 비밀번호·메신저 내용이 남지 않습니다.
- 저장하는 것은 분 단위의 `타건 수`, `연속 타이핑 시간(초)`, `Backspace/Delete 횟수`뿐입니다.
- 데이터는 내 PC의 `~/.typing_tracker/typing.db`(SQLite)에만 저장되고 외부로 전송되지 않습니다.

## 속도는 어떻게 계산하나
업무 중 타이핑은 생각·회의·마우스 작업으로 계속 끊기기 때문에, "1시간에 몇 타"는 속도가 아니라 작업량입니다.
그래서 **키 간격이 2초 이하인 연속 타이핑 구간만** 모아서

    속도(타/분) = 연속 구간 타건 수 ÷ 연속 구간 시간 × 60

으로 계산합니다. 손이 실제로 키보드 위에서 움직일 때의 순수 속도입니다.

- 단축키(Ctrl/Alt/Cmd 조합), 방향키, F키, Shift 단독, 한/영 키, 키를 누르고 있을 때의 자동반복은 세지 않습니다.
- **수정 비율** = Backspace/Delete ÷ 전체 타건. 속도와 함께 보면 "빠르지만 오타가 많은 시간대"도 찾을 수 있습니다.
- 한글은 자모 하나가 1타로 세어지므로 일반적인 한글 타자 연습의 '타수'와 비슷한 단위입니다.

## 설치
Python 3.8 이상 필요.

```bash
pip install -r requirements.txt
```

- **macOS**: 시스템 설정 → 개인정보 보호 및 보안 → **입력 모니터링**(및 손쉬운 사용)에 터미널(또는 Python)을 허용해야 키 입력이 잡힙니다.
- **Windows**: 별도 설정 없이 동작합니다. 관리자 권한으로 실행된 창(일부 보안 프로그램 등)에서의 입력은 잡히지 않을 수 있습니다.

## 사용법

### 1. 측정 시작 (업무 시작할 때 켜두기)
```bash
python -m typing_tracker track          # 종료: Ctrl+C
python -m typing_tracker track -v       # 30초마다 저장되는 분 단위 결과를 화면에 표시
```

### 2. 리포트 보기
```bash
python -m typing_tracker report                     # 평일 09~18시 기준
python -m typing_tracker report --start 10 --end 19 # 업무시간 변경
python -m typing_tracker report --days 14           # 최근 2주만
python -m typing_tracker report --weekends          # 주말 포함
```
터미널에 요약이 출력되고 `typing_report.html`이 생성됩니다. 리포트에는
요일×시간 히트맵, 시간대별/요일별 막대, 최근 일자별 추이가 들어 있습니다.
연속 타이핑이 3분 미만인 칸은 흐리게 표시됩니다(표본 부족).

### 미리보기 (가짜 데이터)
```bash
python -m typing_tracker --db demo.db demo
python -m typing_tracker --db demo.db report -o demo_report.html
```

## PC 켤 때 자동 실행
- **Windows**: `Win+R` → `shell:startup` → 바로가기 생성, 대상:
  `pythonw -m typing_tracker track` (시작 위치: 이 폴더). `pythonw`는 콘솔 창 없이 실행됩니다.
- **macOS**: `~/Library/LaunchAgents`에 launchd plist를 만들어 `python3 -m typing_tracker track`을 등록하세요.

## 해석 팁
- 최소 **2~4주**는 모아야 요일 차이가 우연인지 패턴인지 구분됩니다. 요일별 칸은 주마다 1일씩만 쌓이기 때문입니다.
- 속도는 **하는 일의 종류**에도 크게 좌우됩니다(긴 문서 작성 vs 엑셀 숫자 입력 vs 메신저). 특정 시간대에 늘 같은 업무를 한다면 그 영향일 수 있습니다.
- 수정 비율이 함께 오르는 시간대는 피로·집중력 저하 신호일 가능성이 큽니다.
