"""
전기요금 시간대별 시뮬레이터 - 터미널 버전
현실 1분 = 24시간 (1초 = 24분)
"""

import time
import os

# ── 요금 함수 ──────────────────────────────────────
def get_rate_weekday(hour: float) -> float:
    if hour < 8 or hour >= 22:
        return 117.0
    elif (8 <= hour < 11) or (18 <= hour < 21):
        return 135.0
    elif 11 <= hour < 18:
        return 155.0
    else:
        return 117.0

def get_rate_holiday(hour: float) -> float:
    if 11 <= hour < 14:
        return 60.0
    return 117.0

def get_zone_weekday(hour: float) -> str:
    if hour < 8 or hour >= 22:
        return "경부하  "
    elif (8 <= hour < 11) or (18 <= hour < 21):
        return "중간부하"
    elif 11 <= hour < 18:
        return "최대부하"
    else:
        return "경부하  "

def get_zone_holiday(hour: float) -> str:
    if 11 <= hour < 14:
        return "경부하  "
    return "기본요금"

# ── 바 그래프 ──────────────────────────────────────
BAR_WIDTH = 30
MAX_RATE  = 160.0
MIN_RATE  = 60.0

def rate_to_bar(rate: float) -> str:
    filled = int((rate - MIN_RATE) / (MAX_RATE - MIN_RATE) * BAR_WIDTH)
    filled = max(0, min(BAR_WIDTH, filled))
    return "█" * filled + "░" * (BAR_WIDTH - filled)

def rate_to_color(rate: float, is_holiday: bool = False) -> str:
    if is_holiday and rate < 100:
        return "\033[94m"   # 파랑
    if rate >= 155:
        return "\033[91m"   # 빨강
    elif rate >= 135:
        return "\033[93m"   # 노랑
    else:
        return "\033[96m"   # 청록

RESET = "\033[0m"
BOLD  = "\033[1m"
GRAY  = "\033[90m"

# ── 24시간 타임라인 ────────────────────────────────
def draw_timeline(current_hour: float, get_rate_fn, width: int = 48) -> str:
    result = ""
    for i in range(width):
        h = i / width * 24
        rate = get_rate_fn(h)
        if abs(h - current_hour) < (24 / width):
            result += "\033[97m▼\033[0m"
        elif rate >= 155:
            result += "\033[91m▬\033[0m"
        elif rate >= 135:
            result += "\033[93m▬\033[0m"
        elif rate < 100:
            result += "\033[94m▬\033[0m"
        else:
            result += "\033[96m▬\033[0m"
    return result

def draw_hour_axis(width: int = 48) -> str:
    marks = {0: "0", 6: "6", 12: "12", 18: "18", 23: "24"}
    axis = [" "] * width
    for h, label in marks.items():
        pos = int(h / 24 * width)
        for j, ch in enumerate(label):
            if pos + j < width:
                axis[pos + j] = ch
    return "".join(axis)

# ── 메인 루프 ──────────────────────────────────────
SIM_DURATION = 60.0   # 현실 60초 = 24시간

def main():
    start = time.monotonic()

    while True:
        elapsed = time.monotonic() - start
        if elapsed > SIM_DURATION:
            elapsed = SIM_DURATION

        sim_hour = (elapsed / SIM_DURATION) * 24.0
        progress = elapsed / SIM_DURATION

        rate_wd = get_rate_weekday(sim_hour)
        rate_hd = get_rate_holiday(sim_hour)
        zone_wd = get_zone_weekday(sim_hour)
        zone_hd = get_zone_holiday(sim_hour)

        h_int = int(sim_hour)
        m_int = int((sim_hour - h_int) * 60)
        time_str = f"{h_int:02d}:{m_int:02d}"

        prog_filled = int(progress * 40)
        prog_bar = "█" * prog_filled + "░" * (40 - prog_filled)

        bar_wd = rate_to_bar(rate_wd)
        bar_hd = rate_to_bar(rate_hd)
        col_wd = rate_to_color(rate_wd)
        col_hd = rate_to_color(rate_hd, is_holiday=True)

        os.system('clear')
        print(f"{BOLD}{'=' * 62}{RESET}")
        print(f"{BOLD}  전기요금 시뮬레이터     현실 1분 = 24시간{RESET}")
        print(f"{'=' * 62}")
        print(f"  시각: {BOLD}{time_str}{RESET}   "
              f"진행: [{GRAY}{prog_bar}{RESET}] {progress*100:.1f}%")
        print(f"{'-' * 62}")

        # 평일
        print(f"\n  {BOLD}[ 평일 ]{RESET}")
        print(f"  구간: {col_wd}{BOLD}{zone_wd}{RESET}   "
              f"요금: {col_wd}{BOLD}{rate_wd:.0f} 원/kWh{RESET}")
        print(f"  {col_wd}{bar_wd}{RESET}  {rate_wd:.0f} 원")
        print(f"  타임라인: {draw_timeline(sim_hour, get_rate_weekday)}")
        print(f"  시각:     {GRAY}{draw_hour_axis()}{RESET}")

        # 주말
        print(f"\n  {BOLD}[ 일요일·공휴일 ]{RESET}")
        print(f"  구간: {col_hd}{BOLD}{zone_hd}{RESET}   "
              f"요금: {col_hd}{BOLD}{rate_hd:.0f} 원/kWh{RESET}")
        print(f"  {col_hd}{bar_hd}{RESET}  {rate_hd:.0f} 원")
        print(f"  타임라인: {draw_timeline(sim_hour, get_rate_holiday)}")
        print(f"  시각:     {GRAY}{draw_hour_axis()}{RESET}")

        print(f"\n{'-' * 62}")
        print(f"  {GRAY}범례: \033[91m■{GRAY}최대부하(155)  "
              f"\033[93m■{GRAY}중간부하(135)  "
              f"\033[96m■{GRAY}경부하(117)  "
              f"\033[94m■{GRAY}저요금(60)   Ctrl+C 종료{RESET}")
        print(f"{'=' * 62}")

        if elapsed >= SIM_DURATION:
            print(f"\n  {BOLD}시뮬레이션 완료!{RESET}\n")
            break

        time.sleep(0.2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  종료됨.\n")