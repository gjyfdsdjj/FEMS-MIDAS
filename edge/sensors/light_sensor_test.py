#!/usr/bin/env python3
import time
import argparse
import spidev


def read_mcp3008(spi, channel: int) -> int:
    if not 0 <= channel <= 7:
        raise ValueError("channel must be 0~7")

    # MCP3008 single-ended read
    response = spi.xfer2([1, (8 + channel) << 4, 0])
    value = ((response[1] & 3) << 8) | response[2]
    return value


def decide_light(raw: int, threshold: int, invert: bool = False) -> bool:
    light_on = raw >= threshold
    return (not light_on) if invert else light_on


def main():
    parser = argparse.ArgumentParser(description="CdS + MCP3008 light sensor test")
    parser.add_argument("--seconds", type=float, default=60.0, help="test duration, 0 = infinite")
    parser.add_argument("--interval", type=float, default=1.0, help="read interval seconds")
    parser.add_argument("--threshold", type=int, default=500, help="light on/off threshold (0~1023)")
    parser.add_argument("--invert", action="store_true", help="invert bright/dark logic if needed")
    parser.add_argument("--use-ch1", action="store_true", help="also read channel 1")
    args = parser.parse_args()

    spi = spidev.SpiDev()
    spi.open(0, 0)          # bus=0, CE0
    spi.max_speed_hz = 1_000_000
    spi.mode = 0

    start = time.time()

    try:
        print("=== CdS + MCP3008 test start ===")
        print(f"threshold={args.threshold}, interval={args.interval}s")
        print("Cover sensor with hand / shine phone flashlight to test.\n")

        while True:
            elapsed = time.time() - start
            ch0 = read_mcp3008(spi, 0)
            ratio0 = ch0 / 1023.0
            light0 = decide_light(ch0, args.threshold, args.invert)

            msg = (
                f"[{elapsed:6.1f}s] "
                f"CH0 raw={ch0:4d}, ratio={ratio0:.3f}, "
                f"state={'LIGHT ON' if light0 else 'LIGHT OFF'}"
            )

            if args.use_ch1:
                ch1 = read_mcp3008(spi, 1)
                ratio1 = ch1 / 1023.0
                light1 = decide_light(ch1, args.threshold, args.invert)
                msg += (
                    f" | CH1 raw={ch1:4d}, ratio={ratio1:.3f}, "
                    f"state={'LIGHT ON' if light1 else 'LIGHT OFF'}"
                )

            print(msg)

            if args.seconds > 0 and elapsed >= args.seconds:
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n[STOP] Ctrl+C pressed")

    finally:
        spi.close()
        print("[DONE] test finished")


if __name__ == "__main__":
    main()