"""Interactive preview widget with a mouse-draggable ROI.

The widget shows a BGR frame (already annotated by OpenCV) scaled to fit and
lets the user define the ROI directly on the picture:

* press and drag on empty area  -> draw a new ROI
* drag inside the ROI           -> move it
* drag an edge or corner handle -> resize it
* arrow keys                    -> nudge by 1 px (Shift: 10 px)

The ROI is kept in image pixel coordinates and published through
``regionChanged`` as normalised (x, y, w, h) ratios in the 0~1 range, which is
what ``lock_geometry`` expects.
"""

from __future__ import annotations

import cv2
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget


class RoiPreview(QWidget):
    """Frame viewer that lets the user draw, move and resize one ROI."""

    regionChanged = pyqtSignal(float, float, float, float)

    HANDLE_HIT = 9  # pixels around an edge/corner that count as a handle
    HANDLE_SIZE = 8  # drawn handle square size
    MIN_ROI_PX = 4  # smallest ROI side, in image pixels

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._image_w = 0
        self._image_h = 0
        self._roi: QRectF | None = None  # image pixel coordinates
        self._drag_mode: str | None = None  # "new" | "move" | "resize"
        self._drag_start = QPointF()
        self._drag_offset = QPointF()
        self._drag_rect = QRectF()
        self._resize_edges = ""  # subset of "lrtb"
        self._hover_zone = ""
        self._placeholder = "No image"

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(720, 520)
        self.setStyleSheet(
            "background: #172026; color: #e6ecef; border: 1px solid #bcc8ce; border-radius: 6px;"
        )

    # ------------------------------------------------------------------ data
    def set_frame(self, frame) -> None:
        """Show a BGR numpy frame. Pass ``None`` to clear the view."""
        if frame is None:
            self._pixmap = None
            self._image_w = self._image_h = 0
            self.update()
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(image.copy())
        self._image_w, self._image_h = width, height
        self.update()

    def set_roi_ratio(self, x: float, y: float, w: float, h: float) -> None:
        """Sync the ROI from normalised ratios (does not emit ``regionChanged``)."""
        if self._image_w <= 0 or self._image_h <= 0:
            return
        rect = QRectF(x * self._image_w, y * self._image_h, w * self._image_w, h * self._image_h)
        rect = self._clamp_rect(rect)
        if self._roi is None or (self._roi != rect and self._drag_mode is None):
            self._roi = rect
            self.update()

    def roi_ratio(self):
        if self._roi is None or self._image_w <= 0 or self._image_h <= 0:
            return None
        r = self._roi
        return (
            r.x() / self._image_w,
            r.y() / self._image_h,
            r.width() / self._image_w,
            r.height() / self._image_h,
        )

    def roi_pixels(self):
        if self._roi is None:
            return None
        r = self._roi
        return int(round(r.x())), int(round(r.y())), int(round(r.width())), int(round(r.height()))

    def has_image(self) -> bool:
        return self._pixmap is not None

    # ------------------------------------------------------------ geometry
    def _view_scale_offset(self):
        """Return (scale, offset_x, offset_y) mapping image px -> widget px."""
        if self._image_w <= 0 or self._image_h <= 0:
            return 1.0, 0.0, 0.0
        avail_w = max(1, self.width() - 2)
        avail_h = max(1, self.height() - 2)
        scale = min(avail_w / self._image_w, avail_h / self._image_h)
        off_x = 1 + (avail_w - self._image_w * scale) / 2.0
        off_y = 1 + (avail_h - self._image_h * scale) / 2.0
        return scale, off_x, off_y

    def _to_widget(self, point: QPointF) -> QPointF:
        scale, ox, oy = self._view_scale_offset()
        return QPointF(point.x() * scale + ox, point.y() * scale + oy)

    def _to_image(self, point: QPointF) -> QPointF:
        scale, ox, oy = self._view_scale_offset()
        x = (point.x() - ox) / scale
        y = (point.y() - oy) / scale
        return QPointF(min(max(0.0, x), float(self._image_w)), min(max(0.0, y), float(self._image_h)))

    def _rect_to_widget(self, rect: QRectF) -> QRectF:
        return QRectF(self._to_widget(rect.topLeft()), self._to_widget(rect.bottomRight()))

    def _clamp_rect(self, rect: QRectF) -> QRectF:
        rect = rect.normalized()
        max_w = float(self._image_w)
        max_h = float(self._image_h)
        w = min(max(float(self.MIN_ROI_PX), rect.width()), max_w)
        h = min(max(float(self.MIN_ROI_PX), rect.height()), max_h)
        x = min(max(0.0, rect.x()), max_w - w)
        y = min(max(0.0, rect.y()), max_h - h)
        return QRectF(x, y, w, h)

    def _hit_test(self, pos: QPointF) -> str:
        """Return "" (outside), "move", or a resize code made of l/r/t/b."""
        if self._roi is None:
            return ""
        r = self._rect_to_widget(self._roi)
        hit = self.HANDLE_HIT
        near_l = abs(pos.x() - r.left()) <= hit
        near_r = abs(pos.x() - r.right()) <= hit
        near_t = abs(pos.y() - r.top()) <= hit
        near_b = abs(pos.y() - r.bottom()) <= hit
        within_x = r.left() - hit <= pos.x() <= r.right() + hit
        within_y = r.top() - hit <= pos.y() <= r.bottom() + hit
        code = ""
        if within_y:
            if near_l:
                code += "l"
            elif near_r:
                code += "r"
        if within_x:
            if near_t:
                code += "t"
            elif near_b:
                code += "b"
        if code:
            return code
        if r.contains(pos):
            return "move"
        return ""

    @staticmethod
    def _cursor_for(zone: str):
        if zone == "move":
            return Qt.CursorShape.SizeAllCursor
        if zone in ("l", "r"):
            return Qt.CursorShape.SizeHorCursor
        if zone in ("t", "b"):
            return Qt.CursorShape.SizeVerCursor
        if zone in ("lt", "rb"):
            return Qt.CursorShape.SizeFDiagCursor
        if zone in ("rt", "lb"):
            return Qt.CursorShape.SizeBDiagCursor
        return Qt.CursorShape.CrossCursor

    def _emit_region(self) -> None:
        ratio = self.roi_ratio()
        if ratio is not None:
            self.regionChanged.emit(*ratio)

    # --------------------------------------------------------------- events
    def mousePressEvent(self, event):
        if self._pixmap is None or event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self.setFocus()
        pos = event.position()
        zone = self._hit_test(pos)
        image_pos = self._to_image(pos)
        if zone == "move":
            self._drag_mode = "move"
            self._drag_offset = image_pos - self._roi.topLeft()
        elif zone:
            self._drag_mode = "resize"
            self._resize_edges = zone
            self._drag_rect = QRectF(self._roi)
        else:
            self._drag_mode = "new"
            self._drag_start = image_pos
            self._drag_rect = QRectF(image_pos, image_pos)
        self.update()

    def mouseMoveEvent(self, event):
        if self._pixmap is None:
            return super().mouseMoveEvent(event)
        pos = event.position()
        if self._drag_mode is None:
            zone = self._hit_test(pos)
            if zone != self._hover_zone:
                self._hover_zone = zone
                self.setCursor(self._cursor_for(zone))
            return

        image_pos = self._to_image(pos)
        if self._drag_mode == "move":
            rect = QRectF(self._roi)
            rect.moveTopLeft(image_pos - self._drag_offset)
            self._roi = self._clamp_rect(rect)
            self._emit_region()
        elif self._drag_mode == "resize":
            rect = QRectF(self._drag_rect)
            edges = self._resize_edges
            if "l" in edges:
                rect.setLeft(min(image_pos.x(), rect.right() - self.MIN_ROI_PX))
            if "r" in edges:
                rect.setRight(max(image_pos.x(), rect.left() + self.MIN_ROI_PX))
            if "t" in edges:
                rect.setTop(min(image_pos.y(), rect.bottom() - self.MIN_ROI_PX))
            if "b" in edges:
                rect.setBottom(max(image_pos.y(), rect.top() + self.MIN_ROI_PX))
            self._roi = self._clamp_rect(rect)
            self._emit_region()
        elif self._drag_mode == "new":
            self._drag_rect = QRectF(self._drag_start, image_pos).normalized()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._drag_mode is None:
            return super().mouseReleaseEvent(event)
        mode = self._drag_mode
        self._drag_mode = None
        if mode == "new":
            rect = self._drag_rect.normalized()
            if rect.width() >= self.MIN_ROI_PX and rect.height() >= self.MIN_ROI_PX:
                self._roi = self._clamp_rect(rect)
                self._emit_region()
        self._hover_zone = self._hit_test(event.position())
        self.setCursor(self._cursor_for(self._hover_zone))
        self.update()

    def leaveEvent(self, event):
        self._hover_zone = ""
        self.unsetCursor()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if self._pixmap is None or self._roi is None:
            return super().keyPressEvent(event)
        step = 10.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
        dx = dy = 0.0
        key = event.key()
        if key == Qt.Key.Key_Left:
            dx = -step
        elif key == Qt.Key.Key_Right:
            dx = step
        elif key == Qt.Key.Key_Up:
            dy = -step
        elif key == Qt.Key.Key_Down:
            dy = step
        else:
            return super().keyPressEvent(event)
        rect = QRectF(self._roi)
        rect.translate(dx, dy)
        self._roi = self._clamp_rect(rect)
        self._emit_region()
        self.update()

    # ---------------------------------------------------------------- paint
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        painter.fillRect(self.rect(), QColor("#172026"))
        painter.setPen(QPen(QColor("#bcc8ce"), 1))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)

        if self._pixmap is None:
            painter.setPen(QColor("#e6ecef"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._placeholder)
            return

        scale, ox, oy = self._view_scale_offset()
        target = QRectF(ox, oy, self._image_w * scale, self._image_h * scale)
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))

        if self._drag_mode == "new":
            self._draw_rubber_band(painter, self._rect_to_widget(self._drag_rect))
        elif self._roi is not None:
            self._draw_roi(painter, self._rect_to_widget(self._roi), self._roi)

    def _draw_rubber_band(self, painter: QPainter, rect: QRectF) -> None:
        pen = QPen(QColor("#ffffff"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(23, 107, 93, 60))
        painter.drawRect(rect)
        self._draw_size_label(painter, rect, self._drag_rect)

    def _draw_roi(self, painter: QPainter, rect: QRectF, image_rect: QRectF) -> None:
        # Outline: a thin white line so the box stays visible on any background.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
        painter.drawRect(rect)

        # Eight handles: white square with dark-green border.
        half = self.HANDLE_SIZE / 2.0
        painter.setPen(QPen(QColor("#135b50"), 1))
        painter.setBrush(QColor("#ffffff"))
        cx = (rect.left() + rect.right()) / 2.0
        cy = (rect.top() + rect.bottom()) / 2.0
        for hx, hy in (
            (rect.left(), rect.top()),
            (cx, rect.top()),
            (rect.right(), rect.top()),
            (rect.left(), cy),
            (rect.right(), cy),
            (rect.left(), rect.bottom()),
            (cx, rect.bottom()),
            (rect.right(), rect.bottom()),
        ):
            painter.drawRect(QRectF(hx - half, hy - half, self.HANDLE_SIZE, self.HANDLE_SIZE))

        self._draw_size_label(painter, rect, image_rect)

    def _draw_size_label(self, painter: QPainter, rect: QRectF, image_rect: QRectF) -> None:
        text = (
            f"x {int(round(image_rect.x()))}  y {int(round(image_rect.y()))}   "
            f"{int(round(image_rect.width()))} x {int(round(image_rect.height()))} px"
        )
        font = QFont(painter.font())
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        pad = 4
        box_w = metrics.horizontalAdvance(text) + pad * 2
        box_h = metrics.height() + pad
        x = rect.left()
        y = rect.bottom() + 6
        if y + box_h > self.height() - 2:
            y = rect.top() - box_h - 6
        if y < 2:
            y = rect.top() + 6
        x = min(max(2.0, x), self.width() - box_w - 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(23, 32, 38, 200))
        painter.drawRoundedRect(QRectF(x, y, box_w, box_h), 4, 4)
        painter.setPen(QColor("#e6ecef"))
        painter.drawText(QRectF(x, y, box_w, box_h), Qt.AlignmentFlag.AlignCenter, text)
