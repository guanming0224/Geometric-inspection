"""螺絲與平面間隙幾何檢測工具的主程式入口。

用法：
    python main.py                    # 啟動 PyQt6 圖形化介面
    python main.py --image sample.jpg # 對單張圖片做無視窗檢測並輸出標註影像

無視窗模式可另外指定 ROI 與判斷參數，例如：
    python main.py --image sample.jpg --x 0.35 --y 0.35 --w 0.25 --h 0.20 \
        --mode both --gap-threshold 6 --output result.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def run_gui() -> None:
    from app.src.lock_geometry_gui import main as gui_main

    gui_main()


def run_headless(args: argparse.Namespace) -> int:
    import cv2

    from app.src.lock_geometry import (
        analyze_lock_geometry_regions,
        default_lock_geometry_region,
        draw_lock_geometry_overlay,
    )

    image_path = Path(args.image)
    frame = cv2.imread(str(image_path))
    if frame is None:
        print(f"無法讀取圖片：{image_path}", file=sys.stderr)
        return 1

    regions = [
        default_lock_geometry_region(
            1,
            {
                "x": args.x,
                "y": args.y,
                "w": args.w,
                "h": args.h,
                "mode": args.mode,
                "gap_threshold_px": args.gap_threshold,
            },
        )
    ]

    analyses = analyze_lock_geometry_regions(frame, regions)
    annotated = draw_lock_geometry_overlay(frame.copy(), analyses)

    for analysis in analyses:
        result = analysis.result
        print(f"prediction: {result.prediction}")
        print(f"reason: {result.reason}")

    output_path = (
        Path(args.output)
        if args.output
        else image_path.with_name(f"{image_path.stem}_geometry_overlay{image_path.suffix}")
    )
    cv2.imwrite(str(output_path), annotated)
    print(f"標註影像已儲存：{output_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="螺絲與平面間隙幾何檢測工具。未指定 --image 時啟動 GUI。",
    )
    parser.add_argument("--image", help="要檢測的圖片路徑（無視窗模式）")
    parser.add_argument("--output", help="標註影像輸出路徑，預設為原檔名加上 _geometry_overlay")
    parser.add_argument("--x", type=float, default=0.35, help="ROI 相對 X 位置（0~1）")
    parser.add_argument("--y", type=float, default=0.35, help="ROI 相對 Y 位置（0~1）")
    parser.add_argument("--w", type=float, default=0.25, help="ROI 相對寬度（0~1）")
    parser.add_argument("--h", type=float, default=0.20, help="ROI 相對高度（0~1）")
    parser.add_argument(
        "--mode",
        choices=["gap", "dark", "both"],
        default="both",
        help="判斷模式",
    )
    parser.add_argument(
        "--gap-threshold",
        type=int,
        default=6,
        help="間隙判斷界線值（像素）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.image:
        sys.exit(run_headless(args))
    run_gui()


if __name__ == "__main__":
    main()
