"""Standalone PyQt6 GUI for lock geometry inspection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

# 上次使用的標註位置（ROI、基準線、判斷參數）會存在 app/Data/last_region.json，
# 下次啟動時自動還原。
DATA_DIR = MODULE_DIR.parent / "Data"
LAST_REGION_PATH = DATA_DIR / "last_region.json"

try:
    from .lock_geometry import (
        analyze_lock_geometry_regions,
        default_lock_geometry_region,
        draw_lock_geometry_overlay,
        normalise_lock_geometry_regions,
    )
    from .roi_preview import RoiPreview
except ImportError:
    from lock_geometry import (
        analyze_lock_geometry_regions,
        default_lock_geometry_region,
        draw_lock_geometry_overlay,
        normalise_lock_geometry_regions,
    )
    from roi_preview import RoiPreview


# 風格依據專案根目錄的「風格設計.md」：淺色工業控制台，
# 暖灰米白底、白底卡片、墨綠主操作色、低飽和警示紅。
STYLE_SHEET = """
* {
    font-family: "Microsoft JhengHei UI", "Segoe UI", Arial;
}

QMainWindow, QWidget#root {
    background: #f1eee7;
    color: #172026;
}

QLabel {
    color: #172026;
}

QGroupBox {
    background: #ffffff;
    border: 1px solid #d7dee2;
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    color: #172026;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #41515c;
    font-weight: 700;
}

QPushButton {
    background: #eef2f4;
    color: #172026;
    border: 1px solid #c8d1d6;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 700;
}

QPushButton:hover {
    background: #e2e8ec;
}

QPushButton:pressed {
    background: #d6dde1;
}

QPushButton[buttonRole="primary"] {
    background: #176b5d;
    color: #ffffff;
    border: 1px solid #135b50;
}

QPushButton[buttonRole="primary"]:hover,
QPushButton[buttonRole="primary"]:pressed {
    background: #135b50;
}

QPushButton[buttonRole="danger"] {
    background: #ffe2df;
    color: #9f1f16;
    border: 1px solid #f4aaa4;
}

QPushButton[buttonRole="danger"]:hover {
    background: #ffd2cc;
}

QPushButton[buttonRole="danger"]:pressed {
    background: #f4aaa4;
}

QSpinBox, QDoubleSpinBox, QComboBox {
    background: #ffffff;
    color: #172026;
    border: 1px solid #c9d4d9;
    border-radius: 6px;
    padding: 3px 6px;
}

QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    background: #eef2f4;
    color: #687981;
}

QComboBox QAbstractItemView {
    background: #ffffff;
    color: #172026;
    border: 1px solid #c9d4d9;
    selection-background-color: #176b5d;
    selection-color: #ffffff;
}

QCheckBox {
    color: #41515c;
}

QLabel#resultBadge {
    background: #e6ecef;
    color: #56656d;
    border: 1px solid #bcc8ce;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 18px;
    font-weight: 800;
}

QLabel#resultBadge[status="locked"] {
    background: #dff4e9;
    color: #0d6b3f;
    border: 1px solid #8fd7b3;
}

QLabel#resultBadge[status="separated"] {
    background: #ffe2df;
    color: #b42318;
    border: 1px solid #f4aaa4;
}

QLabel#hintText {
    color: #687981;
}

QLabel#roiReadout {
    background: #eef2f4;
    color: #172026;
    border: 1px solid #c9d4d9;
    border-radius: 6px;
    padding: 6px 8px;
    font-family: Consolas, "Courier New", monospace;
}

QLabel#detailBox {
    background: #fff8e7;
    color: #6f4e00;
    border: 1px solid #f0d68a;
    border-radius: 6px;
    padding: 8px 10px;
}
"""


class GeometryGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lock Geometry Inspector")
        self.resize(1180, 760)

        self.frame = None
        self.annotated_frame = None
        self.capture = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_camera_frame)

        self.region = self.load_last_region()
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(300)
        self.save_timer.timeout.connect(self.save_last_region)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview = RoiPreview()
        self.preview.regionChanged.connect(self.on_roi_dragged)
        preview_layout.addWidget(self.preview, 1)
        layout.addWidget(preview_group, 3)

        side = QVBoxLayout()
        side.setSpacing(10)
        layout.addLayout(side, 2)

        source_group = QGroupBox("Source")
        source_layout = QGridLayout(source_group)
        self.load_button = QPushButton("Load Image")
        self.load_button.setProperty("buttonRole", "primary")
        self.load_button.clicked.connect(self.load_image)
        self.save_button = QPushButton("Save Overlay")
        self.save_button.clicked.connect(self.save_overlay)
        self.camera_index = QSpinBox()
        self.camera_index.setRange(0, 20)
        self.camera_index.setValue(0)
        self.start_camera_button = QPushButton("Start Camera")
        self.start_camera_button.setProperty("buttonRole", "primary")
        self.start_camera_button.clicked.connect(self.start_camera)
        self.stop_camera_button = QPushButton("Stop Camera")
        self.stop_camera_button.setProperty("buttonRole", "danger")
        self.stop_camera_button.clicked.connect(self.stop_camera)
        source_layout.addWidget(self.load_button, 0, 0)
        source_layout.addWidget(self.save_button, 0, 1)
        source_layout.addWidget(QLabel("Camera"), 1, 0)
        source_layout.addWidget(self.camera_index, 1, 1)
        source_layout.addWidget(self.start_camera_button, 2, 0)
        source_layout.addWidget(self.stop_camera_button, 2, 1)
        side.addWidget(source_group)

        roi_group = QGroupBox("ROI")
        roi_layout = QVBoxLayout(roi_group)
        roi_hint = QLabel(
            "直接在預覽畫面上操作：\n"
            "• 在空白處按住拖曳 → 畫出新的 ROI\n"
            "• 拖曳框內 → 移動；拉邊或角 → 調整大小\n"
            "• 方向鍵微調 1 px，Shift + 方向鍵 10 px"
        )
        roi_hint.setObjectName("hintText")
        roi_hint.setWordWrap(True)
        self.roi_readout = QLabel("ROI: --")
        self.roi_readout.setObjectName("roiReadout")
        self.roi_readout.setWordWrap(True)
        self.reset_roi_button = QPushButton("Reset ROI")
        self.reset_roi_button.clicked.connect(self.reset_roi)
        roi_layout.addWidget(roi_hint)
        roi_layout.addWidget(self.roi_readout)
        roi_layout.addWidget(self.reset_roi_button)
        side.addWidget(roi_group)

        rule_group = QGroupBox("Geometry Rules")
        rule_form = QFormLayout(rule_group)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Gap", "gap")
        self.mode_combo.addItem("Dark", "dark")
        self.mode_combo.addItem("Both", "both")
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(self.region["mode"])))
        self.mode_combo.currentIndexChanged.connect(self.update_region_from_controls)
        self.gap_spin = self.integer_spin(0, 500, self.region["gap_threshold_px"])
        self.dark_ratio_spin = self.ratio_spin(self.region["dark_threshold_ratio"], step=0.01)
        self.dark_gray_spin = self.integer_spin(0, 255, self.region["dark_gray_threshold"])
        self.edge_count_spin = self.integer_spin(1, 5, self.region["metal_edge_count"])
        for spin in [self.gap_spin, self.dark_ratio_spin, self.dark_gray_spin, self.edge_count_spin]:
            spin.valueChanged.connect(self.update_region_from_controls)
        rule_form.addRow("Mode", self.mode_combo)
        rule_form.addRow("Gap threshold px", self.gap_spin)
        rule_form.addRow("Dark ratio threshold", self.dark_ratio_spin)
        rule_form.addRow("Dark gray threshold", self.dark_gray_spin)
        rule_form.addRow("Metal edge count", self.edge_count_spin)
        side.addWidget(rule_group)

        line_group = QGroupBox("Reference Lines")
        line_form = QFormLayout(line_group)
        self.base_auto, self.base_spin = self.optional_ratio_row("Auto base")
        self.red_enabled, self.red_spin = self.optional_ratio_row("Use red line", checked=False)
        self.split_auto, self.split_spin = self.optional_ratio_row("Auto split")
        self.base_auto.setChecked(self.region["base_line_y"] is None)
        self.base_spin.setValue(0.8 if self.region["base_line_y"] is None else self.region["base_line_y"])
        self.red_enabled.setChecked(self.region["red_line_y"] is not None)
        self.red_spin.setValue(0.1 if self.region["red_line_y"] is None else self.region["red_line_y"])
        self.split_auto.setChecked(self.region["split_line_y"] is None)
        self.split_spin.setValue(0.5 if self.region["split_line_y"] is None else self.region["split_line_y"])
        for checkbox, spin in [
            (self.base_auto, self.base_spin),
            (self.red_enabled, self.red_spin),
            (self.split_auto, self.split_spin),
        ]:
            checkbox.stateChanged.connect(self.update_line_enabled)
            checkbox.stateChanged.connect(self.update_region_from_controls)
            spin.valueChanged.connect(self.update_region_from_controls)
        line_form.addRow("Base line", self.row_widget(self.base_auto, self.base_spin))
        line_form.addRow("Red line", self.row_widget(self.red_enabled, self.red_spin))
        line_form.addRow("Split line", self.row_widget(self.split_auto, self.split_spin))
        side.addWidget(line_group)

        self.result_label = QLabel("Prediction: --")
        self.result_label.setObjectName("resultBadge")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label = QLabel("Gap: -- px\nDark: --\nReason: --")
        self.detail_label.setObjectName("detailBox")
        self.detail_label.setWordWrap(True)
        side.addWidget(self.result_label)
        side.addWidget(self.detail_label)
        side.addStretch(1)

        self.update_line_enabled()
        self.update_preview()

    # ------------------------------------------------------------ persistence
    def load_last_region(self):
        """讀取 app/Data/last_region.json；檔案不存在或損壞時回傳預設值。"""
        try:
            with open(LAST_REGION_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return default_lock_geometry_region()
        if not isinstance(data, dict):
            return default_lock_geometry_region()
        return default_lock_geometry_region(1, data)

    def save_last_region(self):
        """把目前的標註位置與參數寫入 app/Data/last_region.json。"""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            payload = {
                key: self.region[key]
                for key in (
                    "x",
                    "y",
                    "w",
                    "h",
                    "base_line_y",
                    "red_line_y",
                    "split_line_y",
                    "mode",
                    "gap_threshold_px",
                    "dark_threshold_ratio",
                    "dark_gray_threshold",
                    "metal_edge_count",
                )
            }
            tmp_path = LAST_REGION_PATH.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            tmp_path.replace(LAST_REGION_PATH)
        except OSError as exc:
            print(f"無法儲存標註位置：{exc}", file=sys.stderr)

    def schedule_save(self):
        # 拖曳時每次滑鼠移動都會觸發更新，用 300ms 的延遲合併成一次寫檔。
        self.save_timer.start()

    def ratio_spin(self, value=0.0, step=0.001):
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 1.0)
        spin.setSingleStep(step)
        spin.setDecimals(3)
        spin.setValue(float(value))
        return spin

    def integer_spin(self, minimum, maximum, value):
        spin = QSpinBox()
        spin.setRange(int(minimum), int(maximum))
        spin.setValue(int(value))
        return spin

    def optional_ratio_row(self, label, checked=True):
        checkbox = QCheckBox(label)
        checkbox.setChecked(checked)
        spin = self.ratio_spin()
        return checkbox, spin

    def row_widget(self, first, second):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(first)
        layout.addWidget(second)
        return row

    def update_line_enabled(self):
        self.base_spin.setEnabled(not self.base_auto.isChecked())
        self.red_spin.setEnabled(self.red_enabled.isChecked())
        self.split_spin.setEnabled(not self.split_auto.isChecked())

    def update_region_from_controls(self):
        self.region = normalise_lock_geometry_regions(
            [
                {
                    **self.region,
                    "mode": self.mode_combo.currentData() or "both",
                    "gap_threshold_px": self.gap_spin.value(),
                    "dark_threshold_ratio": self.dark_ratio_spin.value(),
                    "dark_gray_threshold": self.dark_gray_spin.value(),
                    "metal_edge_count": self.edge_count_spin.value(),
                    "base_line_y": None if self.base_auto.isChecked() else self.base_spin.value(),
                    "red_line_y": self.red_spin.value() if self.red_enabled.isChecked() else None,
                    "split_line_y": None if self.split_auto.isChecked() else self.split_spin.value(),
                }
            ]
        )[0]
        self.schedule_save()
        self.update_preview()

    def on_roi_dragged(self, x, y, w, h):
        # 由預覽元件的滑鼠操作更新 ROI，比例值交給 normalise 做最後的範圍檢查。
        self.region = normalise_lock_geometry_regions([{**self.region, "x": x, "y": y, "w": w, "h": h}])[0]
        self.schedule_save()
        self.update_preview()

    def reset_roi(self):
        default = default_lock_geometry_region()
        self.region = normalise_lock_geometry_regions(
            [{**self.region, "x": default["x"], "y": default["y"], "w": default["w"], "h": default["h"]}]
        )[0]
        self.schedule_save()
        self.update_preview()

    def update_roi_readout(self):
        pixels = self.preview.roi_pixels()
        if pixels is None:
            self.roi_readout.setText("ROI: --")
            return
        x, y, w, h = pixels
        self.roi_readout.setText(
            f"X {x} px   Y {y} px\nW {w} px   H {h} px\n"
            f"ratio  x {self.region['x']:.3f}  y {self.region['y']:.3f}  "
            f"w {self.region['w']:.3f}  h {self.region['h']:.3f}"
        )

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load image",
            str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.bmp);;All files (*)",
        )
        if not path:
            return
        frame = cv2.imread(path)
        if frame is None:
            QMessageBox.warning(self, "Load failed", "Could not read the selected image.")
            return
        self.stop_camera()
        self.frame = frame
        self.update_preview()

    def save_overlay(self):
        if self.annotated_frame is None:
            QMessageBox.information(self, "No overlay", "There is no annotated frame to save.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save overlay",
            str(Path.cwd() / "lock_geometry_overlay.jpg"),
            "JPEG (*.jpg);;PNG (*.png);;All files (*)",
        )
        if not path:
            return
        if not cv2.imwrite(path, self.annotated_frame):
            QMessageBox.warning(self, "Save failed", "Could not write the overlay image.")

    def start_camera(self):
        self.stop_camera()
        capture = cv2.VideoCapture(self.camera_index.value())
        if not capture.isOpened():
            capture.release()
            QMessageBox.warning(self, "Camera unavailable", "Could not open the selected camera.")
            return
        self.capture = capture
        self.timer.start(33)

    def stop_camera(self):
        self.timer.stop()
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def read_camera_frame(self):
        if self.capture is None:
            return
        ok, frame = self.capture.read()
        if not ok or frame is None:
            self.stop_camera()
            QMessageBox.warning(self, "Camera stopped", "Could not read from the camera.")
            return
        self.frame = frame
        self.update_preview()

    def set_result_status(self, prediction):
        # 依風格設計.md 的狀態色規則切換徽章樣式：
        # locked=PASS 綠、separated=NG 紅、其他=中性灰藍。
        status = prediction if prediction in ("locked", "separated") else "neutral"
        if self.result_label.property("status") != status:
            self.result_label.setProperty("status", status)
            self.result_label.style().unpolish(self.result_label)
            self.result_label.style().polish(self.result_label)

    def update_preview(self):
        if self.frame is None:
            self.preview.set_frame(None)
            self.update_roi_readout()
            self.result_label.setText("Prediction: --")
            self.set_result_status(None)
            self.detail_label.setText("Gap: -- px\nDark: --\nReason: --")
            return

        analyses = analyze_lock_geometry_regions(self.frame, [self.region])
        annotated = draw_lock_geometry_overlay(self.frame.copy(), analyses, show_result=True)
        self.annotated_frame = annotated
        if analyses:
            result = analyses[0].result
            self.result_label.setText(f"Prediction: {result.prediction}")
            self.set_result_status(result.prediction)
            self.detail_label.setText(
                "Gap: "
                f"{result.gap_px if result.gap_px is not None else '--'} px\n"
                f"Dark: {result.dark_ratio:.3f}\n"
                f"Reason: {result.reason}"
            )
        self.show_frame(annotated)

    def show_frame(self, frame):
        self.preview.set_frame(frame)
        self.preview.set_roi_ratio(
            self.region["x"], self.region["y"], self.region["w"], self.region["h"]
        )
        self.update_roi_readout()

    def closeEvent(self, event):
        self.stop_camera()
        self.save_timer.stop()
        self.save_last_region()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)
    window = GeometryGui()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
