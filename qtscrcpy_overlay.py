"""
========================================================================================
DỰ ÁN: TRỢ LÝ OVERLAY TRONG SUỐT CHO QTSCRCPY (BYPASS FLAG_SECURE QUA UIAUTOMATOR2)
========================================================================================
Tính năng nổi bật:
  1. Window Tracking thông minh:
     - Tự động nhận diện chính xác cửa sổ chia sẻ màn hình điện thoại từ QtScrcpy
       (tiêu đề dạng 'Phone-<serial>', VD: 'Phone-R3CT104B80P').
     - Không bao giờ dính nhầm vào trình duyệt (Thorium/Chrome/Edge) hay File Explorer.
  2. Bật / Tắt thủ công (Manual Toggle):
     - Click chuột vào các phím số hoặc phần tử KHÔNG tự tắt Overlay.
     - Cho phép bấm liên tiếp mã PIN 6 số (1 2 3 4 5 6) mượt mà.
     - Nút [❌ Tắt XML (ESC)] và phím ESC để tắt thủ công; phím F5 để quét lại.
  3. Giao diện & Màu sắc:
     - Bounding Box màu Cyan (Xanh lơ sáng).
     - Khu vực ô nhập liệu (EditText, pinEntry, password) hiển thị màu Tím Neon (Purple)
       kèm biểu tượng con trỏ chữ (I-Beam Cursor) nhấp nháy chậm trực quan.
  4. Nút Thoát Ứng Dụng ngay dưới thanh hiển thị:
     - Nút [⏻ Thoát ứng dụng] màu đỏ nằm ngay dưới thanh công cụ chính, cho phép thoát
       hoàn toàn tiến trình Python bất kỳ lúc nào (kể cả khi tắt chế độ soi XML).
  5. Tính năng CHIA LƯỚI KÉO THẢ (Word-style Grid Table Creator):
     - Dành cho các bàn phím bảo mật không thể soi bằng XML (như ShopeePay, ngân hàng).
     - Chỉ cần chuột phải vào khung (hoặc bấm [📐 Chia lưới]), một bảng kéo thả số dòng
       số cột thân thiện như trên Microsoft Word sẽ hiện ra.
     - Tự động chia khung lớn thành lưới các phím bấm ảo (VD: 4 hàng × 3 cột chuẩn bàn
       phím số điện thoại 1..9, 0, Xóa).
     - Click vào từng ô hoặc bấm phím số 0-9 / Backspace trên bàn phím máy tính sẽ tự động
       gửi click chính xác vào tâm của ô đó trên điện thoại!
========================================================================================
"""

import sys
import os
import io
import re
import time
import subprocess
import xml.etree.ElementTree as ET
from threading import Thread

# Chuyển console sang UTF-8 trên Windows để in tiếng Việt không lỗi charmap
if sys.platform.startswith("win"):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# 1. TÌM KIẾM VÀ CẤU HÌNH ĐƯỜNG DẪN ADB
# ---------------------------------------------------------------------------
def setup_adb_environment():
    """Tìm kiếm file thực thi adb.exe thật và bổ sung vào PATH."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "QtScrcpy-win-x64-v4.2.1", "adb.exe"),
        os.path.join(os.path.dirname(script_dir), "QtScrcpy-win-x64-v4.2.1", "adb.exe"),
        r"C:\Super App\QtScrcpy-win-x64-v3.3.3\adb.exe",
        os.path.join(script_dir, "adb.exe"),
        os.path.join(os.path.dirname(script_dir), "adb.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            adb_dir = os.path.dirname(c)
            if adb_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = adb_dir + os.path.pathsep + os.environ.get("PATH", "")
            return c

    for p in os.environ.get("PATH", "").split(os.path.pathsep):
        c = os.path.join(p, "adb.exe")
        if os.path.isfile(c):
            return c
    return None

REAL_ADB_PATH = setup_adb_environment()

def get_connected_serials():
    """Lấy danh sách serial các thiết bị Android đang kết nối qua ADB."""
    try:
        adb_bin = REAL_ADB_PATH or "adb"
        res = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=2)
        serials = []
        for line in res.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serials.append(parts[0])
        return serials
    except Exception:
        return []

# ---------------------------------------------------------------------------
# 2. HỖ TRỢ ĐA NỀN TẢNG QT (PyQt5 / PySide6)
# ---------------------------------------------------------------------------
try:
    from PyQt5.QtWidgets import (
        QApplication, QWidget, QPushButton, QLabel, QHBoxLayout, QVBoxLayout,
        QGraphicsDropShadowEffect, QFrame, QLayout, QDialog, QLineEdit, QPlainTextEdit
    )
    from PyQt5.QtCore import Qt, QTimer, QRect, QPoint, pyqtSignal as Signal, QThread
    from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush, QRegion, QCursor
    QT_BACKEND = "PyQt5"
except ImportError:
    from PySide6.QtWidgets import (
        QApplication, QWidget, QPushButton, QLabel, QHBoxLayout, QVBoxLayout,
        QGraphicsDropShadowEffect, QFrame, QLayout, QDialog, QLineEdit, QPlainTextEdit
    )
    from PySide6.QtCore import Qt, QTimer, QRect, QPoint, Signal, QThread
    from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush, QRegion, QCursor
    QT_BACKEND = "PySide6"

# ---------------------------------------------------------------------------
# 3. HỖ TRỢ WINDOWS API
# ---------------------------------------------------------------------------
try:
    import win32gui
    import win32con
    HAVE_WIN32GUI = True
except ImportError:
    HAVE_WIN32GUI = False

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Gắn kết thread với desktop "default" ngay từ đầu trước khi tạo bất kỳ cửa sổ nào
try:
    _h_desk_init = user32.OpenDesktopW("default", 0, False, 0x01FF)
    if _h_desk_init:
        user32.SetThreadDesktop(_h_desk_init)
except Exception:
    pass

# ---------------------------------------------------------------------------
# 4. KẾT NỐI UIAUTOMATOR2
# ---------------------------------------------------------------------------
try:
    import uiautomator2 as u2
    HAVE_U2 = True
except ImportError:
    HAVE_U2 = False

# Chuẩn bàn phím 4x3 cổ điển trên điện thoại (Hàng x Cột)
KEYPAD_LABELS_4X3 = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["",  "0", "⌫"]
]


# ===========================================================================
# CƠ CHẾ WINDOW TRACKING THÔNG MINH (CHÍNH XÁC VÀO CỬA SỔ PHONE QTSCRCPY)
# ===========================================================================

def get_process_name_by_pid(pid):
    """Lấy tên file thực thi của một Process ID."""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if h_proc:
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower()
        finally:
            kernel32.CloseHandle(h_proc)
    return ""


_DESKTOP_ATTACHED = False
def ensure_desktop_attached():
    global _DESKTOP_ATTACHED
    if not _DESKTOP_ATTACHED:
        try:
            h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
            if h_desk:
                user32.SetThreadDesktop(h_desk)
                _DESKTOP_ATTACHED = True
        except Exception:
            pass


def find_target_window(title_keyword="QtScrcpy", serial=None):
    """
    Tìm handle (HWND) chính xác của cửa sổ chia sẻ màn hình điện thoại từ QtScrcpy.
    """
    candidates = []

    def evaluate_window(hwnd):
        if not user32.IsWindowVisible(hwnd):
            return

        title_len = user32.GetWindowTextLengthW(hwnd)
        if title_len == 0:
            return
        tbuff = ctypes.create_unicode_buffer(title_len + 1)
        user32.GetWindowTextW(hwnd, tbuff, title_len + 1)
        title = tbuff.value

        cbuff = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cbuff, 256)
        cls_name = cbuff.value

        # Bỏ qua thanh công cụ dọc của QtScrcpy (Tool)
        if "tool" in cls_name.lower() or title.lower() == "tool":
            return

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pname = get_process_name_by_pid(pid.value)

        # Chặn các ứng dụng trình duyệt hoặc file explorer không liên quan
        ignored_procs = ["explorer.exe", "thorium.exe", "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "code.exe", "antigravity.exe"]
        if pname in ignored_procs:
            return

        is_iconic = user32.IsIconic(hwnd)
        score = 0
        is_scrcpy_proc = any(k in pname for k in ["scrcpy", "qtscrcpy"])

        if is_scrcpy_proc:
            score += 100
            if serial and serial.lower() in title.lower():
                score += 90
            if title.lower().startswith("phone-"):
                score += 70
            elif title.lower() != "qtscrcpy":
                score += 30
            else:
                score += 10
            if not is_iconic:
                score += 50
        else:
            if title.lower().startswith("phone-"):
                score += 60
            elif title_keyword and title_keyword.lower() not in ["qtscrcpy", "scrcpy"]:
                if title_keyword.lower() in title.lower():
                    score += 20
            if not is_iconic:
                score += 10

        if score > 0:
            candidates.append((score, hwnd, title))

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_cb(hwnd, _):
        evaluate_window(hwnd)
        return True

    if _h_desk_init:
        user32.EnumDesktopWindows(_h_desk_init, WNDENUMPROC(enum_cb), 0)
    else:
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_candidate = candidates[0]
    return best_candidate[1], best_candidate[2]


def get_client_rect_screen(hwnd):
    """Lấy tọa độ tuyệt đối của vùng hiển thị video QtScrcpy."""
    if not hwnd:
        return None

    ensure_desktop_attached()

    if user32.IsIconic(hwnd) or not user32.IsWindowVisible(hwnd):
        return None

    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, rect.right, rect.bottom


# ===========================================================================
# LUỒNG PHỤ (QThread): QUÉT VÀ PHÂN TÍCH XML TRÁNH TREO GUI
# ===========================================================================

class XMLScannerWorker(QThread):
    scan_success = Signal(list, int, int)
    scan_failed = Signal(str)

    def __init__(self, device, demo=False):
        super().__init__()
        self.device = device
        self.demo = demo

    def run(self):
        try:
            if self.demo:
                time.sleep(0.2)
                phone_w, phone_h = 1080, 2400
                xml_text = """<hierarchy rotation="0">
                  <node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">
                    <node class="android.widget.TextView" text="Nhập Mật khẩu ShopeePay" bounds="[60,300][980,420]" />
                    <node class="android.widget.EditText" resource-id="com.shopee:id/payment_password_field" text="••" desc="Ô nhập mã PIN" bounds="[130,520][950,670]" focused="true" password="true" />
                    <node class="android.view.View" resource-id="keyboard_number_view" bounds="[60,1100][1020,2100]" text="" desc="Bàn phím bảo mật ShopeePay" clickable="true" />
                    <node class="android.widget.TextView" resource-id="key1" text="1" bounds="[180,1200][360,1360]" clickable="true" />
                    <node class="android.widget.TextView" resource-id="key2" text="2" bounds="[450,1200][630,1360]" clickable="true" />
                    <node class="android.widget.TextView" resource-id="key3" text="3" bounds="[720,1200][900,1360]" clickable="true" />
                    <node class="android.widget.TextView" resource-id="delete_button" text="XÓA" bounds="[720,1850][900,2020]" clickable="true" />
                  </node>
                </hierarchy>"""
            else:
                if not self.device:
                    self.scan_failed.emit("Chưa kết nối được thiết bị Android qua ADB!")
                    return

                phone_w, phone_h = 1080, 2400
                try:
                    window_size = self.device.window_size()
                    phone_w, phone_h = window_size[0], window_size[1]
                except Exception:
                    pass

                xml_text = self.device.dump_hierarchy()
                if not xml_text:
                    self.scan_failed.emit("Không lấy được dữ liệu XML từ điện thoại!")
                    return

            root = ET.fromstring(xml_text.encode("utf-8"))

            # Quét tìm không gian tọa độ thực của XML từ node gốc [0,0][W,H]
            max_w, max_h = 0, 0
            for node in root.iter():
                bounds_str = node.attrib.get("bounds", "")
                if bounds_str:
                    coords = list(map(int, re.findall(r"\d+", bounds_str)))
                    if len(coords) >= 4 and coords[0] == 0 and coords[1] == 0:
                        if coords[2] > max_w:
                            max_w = coords[2]
                        if coords[3] > max_h:
                            max_h = coords[3]

            if max_w > 100 and max_h > 100:
                phone_w = max_w
                phone_h = max_h

            elements = []

            for node in root.iter():
                bounds_str = node.attrib.get("bounds", "")
                if not bounds_str:
                    continue

                coords = re.findall(r"\d+", bounds_str)
                if len(coords) < 4:
                    continue

                x1, y1, x2, y2 = map(int, coords[:4])
                bw = x2 - x1
                bh = y2 - y1

                if bw <= 0 or bh <= 0:
                    continue

                clickable = node.attrib.get("clickable", "false").lower() == "true"
                text = node.attrib.get("text", "").strip()
                desc = node.attrib.get("content-desc", "").strip()
                res_id = node.attrib.get("resource-id", "").strip()
                cls_name = node.attrib.get("class", "").strip()
                focused = node.attrib.get("focused", "false").lower() == "true"
                is_password = node.attrib.get("password", "false").lower() == "true"

                is_input = (
                    "edittext" in cls_name.lower()
                    or "textinput" in cls_name.lower()
                    or "autocomplete" in cls_name.lower()
                    or is_password
                    or focused
                    or any(k in res_id.lower() for k in ["pin", "password", "edt", "edit", "input", "search", "otp"])
                )

                area = bw * bh
                is_full_screen = (bw >= phone_w and bh >= phone_h)

                if (clickable or text or desc or res_id or is_input) and not (is_full_screen and not text and not desc):
                    short_id = res_id.split("/")[-1] if "/" in res_id else res_id
                    display_label = text or desc or short_id or cls_name.split(".")[-1]

                    elements.append({
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "width": bw,
                        "height": bh,
                        "area": area,
                        "center_x": (x1 + x2) // 2,
                        "center_y": (y1 + y2) // 2,
                        "clickable": clickable,
                        "text": text,
                        "desc": desc,
                        "res_id": res_id,
                        "short_id": short_id,
                        "label": display_label,
                        "class": cls_name,
                        "is_input": is_input,
                        "focused": focused,
                        "password": is_password,
                    })

            self.scan_success.emit(elements, phone_w, phone_h)

        except Exception as e:
            self.scan_failed.emit(f"Lỗi khi quét XML: {str(e)}")


# ===========================================================================
# TIỆN ÍCH CHIA LƯỚI BẢNG PHONG CÁCH WORD (WORD-STYLE TABLE GRID PICKER)
# ===========================================================================

class GridMatrixWidget(QWidget):
    """
    Ma trận các ô vuông tương tác: Cho phép rê chuột / kéo thả
    chọn số dòng và số cột y hệt giao diện chèn Bảng trên Microsoft Word.
    """
    grid_hovered = Signal(int, int)
    grid_picked = Signal(int, int)

    def __init__(self, max_rows=6, max_cols=5, parent=None):
        super().__init__(parent)
        self.max_rows = max_rows
        self.max_cols = max_cols
        self.cell_size = 25
        self.gap = 4
        self.margin = 6
        self.cur_r = 4
        self.cur_c = 3
        self.setMouseTracking(True)
        w = self.margin * 2 + self.max_cols * (self.cell_size + self.gap) - self.gap
        h = self.margin * 2 + self.max_rows * (self.cell_size + self.gap) - self.gap
        self.setFixedSize(w, h)

    def _update_selection_from_pos(self, pos):
        c = (pos.x() - self.margin) // (self.cell_size + self.gap)
        r = (pos.y() - self.margin) // (self.cell_size + self.gap)
        c = max(0, min(self.max_cols - 1, c))
        r = max(0, min(self.max_rows - 1, r))
        if r + 1 != self.cur_r or c + 1 != self.cur_c:
            self.cur_r = r + 1
            self.cur_c = c + 1
            self.grid_hovered.emit(self.cur_r, self.cur_c)
            self.update()

    def mouseMoveEvent(self, event):
        self._update_selection_from_pos(event.pos())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._update_selection_from_pos(event.pos())
            self.grid_picked.emit(self.cur_r, self.cur_c)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        for r in range(self.max_rows):
            for c in range(self.max_cols):
                x = self.margin + c * (self.cell_size + self.gap)
                y = self.margin + r * (self.cell_size + self.gap)
                rect = QRect(x, y, self.cell_size, self.cell_size)

                is_selected = (r < self.cur_r and c < self.cur_c)
                if is_selected:
                    # Các ô được chọn: Màu Cyan sáng với viền trắng
                    painter.setPen(QPen(QColor(255, 255, 255), 1.5))
                    painter.setBrush(QColor(0, 229, 255, 210))
                else:
                    # Các ô chưa chọn: Nền xám mờ
                    painter.setPen(QPen(QColor(71, 85, 105, 140), 1))
                    painter.setBrush(QColor(30, 41, 59, 140))

                painter.drawRoundedRect(rect, 4, 4)
        painter.end()


class WordTablePickerPopup(QFrame):
    """
    Cửa sổ Popup phong cách Microsoft Word để kéo thả chia lưới:
      - Ma trận trực quan để rê chuột chọn số hàng x số cột.
      - Nút chọn nhanh chuẩn bàn phím số (4x3) cho mã PIN.
      - Nút xóa lưới để trả lại khung bình thường.
    """
    grid_selected = Signal(int, int)

    def __init__(self, target_elem_label="Khung", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setObjectName("TablePickerPopup")
        self.setStyleSheet("""
            #TablePickerPopup {
                background-color: #0F172A;
                border: 2px solid #00F0FF;
                border-radius: 10px;
            }
            QLabel {
                color: #F8FAFC;
                font-family: 'Segoe UI', Tahoma, sans-serif;
            }
            QPushButton {
                background-color: #1E293B;
                color: #38BDF8;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 5px 9px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284C7;
                color: #FFFFFF;
                border-color: #00F0FF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Tiêu đề
        lbl_head = target_elem_label[:22] + ("..." if len(target_elem_label) > 22 else "")
        title_lbl = QLabel(f"📐 Chia lưới: {lbl_head}", self)
        title_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #00F0FF;")
        layout.addWidget(title_lbl)

        # Nhãn động hiển thị kích thước
        self.size_lbl = QLabel("4 × 3 (4 hàng × 3 cột) - Bàn phím số PIN", self)
        self.size_lbl.setStyleSheet("font-size: 11px; color: #38BDF8; font-weight: bold;")
        layout.addWidget(self.size_lbl)

        # Ma trận kéo thả phong cách Word
        self.matrix = GridMatrixWidget(max_rows=6, max_cols=5, parent=self)
        self.matrix.grid_hovered.connect(self._on_grid_hovered)
        self.matrix.grid_picked.connect(self._on_grid_picked)
        layout.addWidget(self.matrix, 0, Qt.AlignCenter)

        # Các nút bấm chọn nhanh
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        btn_4x3 = QPushButton("4 × 3 (PIN)", self)
        btn_4x3.setToolTip("Chuẩn 10 phím số + phím Xóa điện thoại")
        btn_4x3.clicked.connect(lambda: self._on_grid_picked(4, 3))
        btn_layout.addWidget(btn_4x3)

        btn_3x3 = QPushButton("3 × 3", self)
        btn_3x3.clicked.connect(lambda: self._on_grid_picked(3, 3))
        btn_layout.addWidget(btn_3x3)

        btn_clear = QPushButton("🗑 Xóa lưới", self)
        btn_clear.setStyleSheet("color: #EF4444; border-color: #7F1D1D;")
        btn_clear.clicked.connect(lambda: self._on_grid_picked(0, 0))
        btn_layout.addWidget(btn_clear)

        layout.addLayout(btn_layout)

    def _on_grid_hovered(self, r, c):
        hint = " - Bàn phím số PIN" if (r == 4 and c == 3) else ""
        self.size_lbl.setText(f"{r} × {c} ({r} hàng × {c} cột){hint}")

    def _on_grid_picked(self, r, c):
        self.grid_selected.emit(r, c)
        self.close()


# ===========================================================================
# CỬA SỔ DÒNG LỆNH ADB NHANH (HACKER TERMINAL - CƠ CHẾ CÔ LẬP THIẾT BỊ ĐÍCH)
# ===========================================================================

class CommandLineEdit(QLineEdit):
    """Ô nhập lệnh hỗ trợ duyệt lịch sử phím Mũi tên Lên / Xuống như terminal thật."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.history_index = -1

    def add_history(self, cmd):
        cmd = cmd.strip()
        if not cmd:
            return
        if not self.history or self.history[-1] != cmd:
            self.history.append(cmd)
        self.history_index = len(self.history)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            if self.history:
                if self.history_index > 0:
                    self.history_index -= 1
                elif self.history_index == -1:
                    self.history_index = len(self.history) - 1
                self.setText(self.history[self.history_index])
            return
        elif event.key() == Qt.Key_Down:
            if self.history:
                if self.history_index < len(self.history) - 1:
                    self.history_index += 1
                    self.setText(self.history[self.history_index])
                else:
                    self.history_index = len(self.history)
                    self.clear()
            return
        super().keyPressEvent(event)


class AdbCommandWorker(QThread):
    """Luồng ngầm chạy lệnh ADB không làm đơ giao diện người dùng."""
    output_received = Signal(str, bool)   # (text, is_error)
    finished_code = Signal(int)           # returncode

    def __init__(self, cmd_args, demo_mode=False, demo_serial=""):
        super().__init__()
        self.cmd_args = cmd_args
        self.demo_mode = demo_mode
        self.demo_serial = demo_serial

    def run(self):
        if self.demo_mode:
            time.sleep(0.12)
            cmd_joined = " ".join(self.cmd_args)
            if "keyevent" in cmd_joined:
                out = f"[Demo {self.demo_serial}] Gửi keyevent thành công: {cmd_joined}"
            elif "getprop" in cmd_joined:
                out = f"[Demo {self.demo_serial}] [ro.product.model]: SM-S908N"
            elif "wm size" in cmd_joined:
                out = f"Physical size: 1080x2400"
            elif "devices" in cmd_joined:
                out = f"List of devices attached\n{self.demo_serial}\tdevice"
            else:
                out = f"[Demo {self.demo_serial}] Lệnh đã thực thi giả lập thành công (mã 0)."
            self.output_received.emit(out, False)
            self.finished_code.emit(0)
            return

        try:
            creationflags = 0
            if sys.platform.startswith("win"):
                creationflags = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(
                self.cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags
            )
            stdout, stderr = proc.communicate(timeout=25)
            if stdout:
                self.output_received.emit(stdout.rstrip(), False)
            if stderr:
                self.output_received.emit(stderr.rstrip(), True)
            self.finished_code.emit(proc.returncode)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.output_received.emit("❌ Lệnh vượt quá thời gian chờ (Timeout 25s) và đã bị ngắt!", True)
            self.finished_code.emit(-1)
        except Exception as e:
            self.output_received.emit(f"❌ Lỗi thực thi subprocess: {str(e)}", True)
            self.finished_code.emit(-1)


class AdbCommandDialog(QDialog):
    """
    Cửa sổ nhỏ dòng lệnh ADB nhanh phong cách Hacker CMD:
    - Giao diện phông chữ Consolas màu xanh lá cây ma trận neon trên nền đen.
    - CƠ CHẾ CÔ LẬP THIẾT BỊ: Cho dù người dùng gõ lệnh chung (shell ...) hay
      vô tình truyền -s <thiết bị khác>, hệ thống luôn tự động ép buộc chạy
      duy nhất trên thiết bị mà cửa sổ Overlay này đang bám dính (-s device_serial).
    - Tránh triệt để lỗi 'more than one device/emulator' khi cắm đồng thời nhiều máy.
    - Cho phép gõ lệnh tự do, lưu lịch sử, và tích hợp các nút phím tắt nhanh.
    """
    def __init__(self, overlay=None, device_serial=None, demo_mode=False, parent=None):
        super().__init__(parent)
        self.overlay = overlay
        self.device_serial = device_serial or (overlay.device_serial if overlay else None)
        self.demo_mode = demo_mode
        self.worker = None

        self.setWindowTitle(self._build_window_title())
        self.resize(620, 440)
        self.setMinimumSize(480, 320)
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowStaysOnTopHint |
            Qt.WindowCloseButtonHint |
            Qt.WindowMinMaxButtonsHint
        )

        self.setStyleSheet("""
            QDialog {
                background-color: #0A0E14;
                color: #22C55E;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            QLabel {
                color: #4ADE80;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            QPlainTextEdit {
                background-color: #06090E;
                color: #4ADE80;
                border: 1px solid #1E293B;
                border-radius: 6px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                padding: 6px;
                selection-background-color: #047857;
            }
            QLineEdit {
                background-color: #0F172A;
                color: #86EFAC;
                border: 1px solid #059669;
                border-radius: 5px;
                padding: 6px 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #22C55E;
                background-color: #111827;
            }
            QPushButton {
                background-color: #064E3B;
                color: #86EFAC;
                border: 1px solid #059669;
                border-radius: 4px;
                padding: 5px 9px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #047857;
                color: #FFFFFF;
                border-color: #10B981;
            }
            QPushButton:pressed {
                background-color: #065F46;
            }
            #BtnRun {
                background-color: #047857;
                color: #ECFDF5;
                border: 1px solid #10B981;
                padding: 6px 16px;
                font-size: 12px;
            }
            #BtnRun:hover {
                background-color: #059669;
            }
            #BtnClear {
                background-color: #1E293B;
                color: #94A3B8;
                border: 1px solid #334155;
            }
            #BtnClear:hover {
                background-color: #334155;
                color: #F1F5F9;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Thanh tiêu đề trạng thái khóa thiết bị
        self.lbl_device_header = QLabel(self)
        self.lbl_device_header.setStyleSheet("""
            background-color: #0F2318;
            color: #34D399;
            border: 1px solid #059669;
            border-radius: 5px;
            padding: 6px 10px;
            font-size: 11px;
            font-weight: bold;
        """)
        layout.addWidget(self.lbl_device_header)
        self._refresh_header_text()

        # Màn hình hiển thị kết quả dòng lệnh
        self.txt_output = QPlainTextEdit(self)
        self.txt_output.setReadOnly(True)
        layout.addWidget(self.txt_output)

        # Khối các nút lệnh nhanh phổ biến
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(6)

        lbl_quick = QLabel("⚡ Nhanh:", self)
        lbl_quick.setStyleSheet("color: #6EE7B7; font-size: 11px;")
        quick_layout.addWidget(lbl_quick)

        actions = [
            ("Home", "shell input keyevent 3"),
            ("Back", "shell input keyevent 4"),
            ("Power", "shell input keyevent 26"),
            ("Menu", "shell input keyevent 187"),
            ("Kích thước", "shell wm size"),
            ("IP Wi-Fi", "shell ip route"),
        ]

        for name, cmd in actions:
            btn = QPushButton(name, self)
            btn.setToolTip(f"Chạy nhanh: {cmd}")
            btn.clicked.connect(lambda checked, c=cmd: self.run_quick_command(c))
            quick_layout.addWidget(btn)

        quick_layout.addStretch()

        btn_clear = QPushButton("🗑 Xóa log", self)
        btn_clear.setObjectName("BtnClear")
        btn_clear.clicked.connect(self.clear_output)
        quick_layout.addWidget(btn_clear)

        layout.addLayout(quick_layout)

        # Thanh nhập lệnh và nút Chạy
        input_layout = QHBoxLayout()
        input_layout.setSpacing(6)

        self.lbl_prompt = QLabel("adb >", self)
        self.lbl_prompt.setStyleSheet("color: #22C55E; font-weight: bold; font-size: 12px;")
        input_layout.addWidget(self.lbl_prompt)

        self.input_cmd = CommandLineEdit(self)
        self.input_cmd.setPlaceholderText("Nhập lệnh (VD: shell input keyevent 3, shell getprop ro.product.model...)")
        self.input_cmd.returnPressed.connect(self.on_execute_clicked)
        input_layout.addWidget(self.input_cmd)

        self.btn_run = QPushButton("Chạy (Enter)", self)
        self.btn_run.setObjectName("BtnRun")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.clicked.connect(self.on_execute_clicked)
        input_layout.addWidget(self.btn_run)

        layout.addLayout(input_layout)

        # Dòng hướng dẫn phím tắt phía dưới
        lbl_hint = QLabel("💡 Tự động khóa đích theo cửa sổ này. Hỗ trợ phím Mũi tên Lên/Xuống để xem lại lịch sử lệnh.", self)
        lbl_hint.setStyleSheet("color: #64748B; font-size: 10px;")
        layout.addWidget(lbl_hint)

        # Tin nhắn khởi động
        self._append_system_log(f"Đã mở ADB Terminal cho thiết bị: {self.get_current_serial_display()}")
        self._append_system_log("Mọi lệnh thực thi tại đây sẽ được tự động gắn '-s <serial>' để không gây xung đột đa thiết bị.")

    def _build_window_title(self):
        return f"ADB Terminal - [{self.get_current_serial_display()}]"

    def get_current_serial_display(self):
        if self.demo_mode:
            return "Demo Device 1080x2400"
        if self.device_serial:
            return f"Phone-{self.device_serial}"
        if self.overlay and self.overlay.device_serial:
            return f"Phone-{self.overlay.device_serial}"
        return "Tự động phát hiện"

    def update_device_serial(self, new_serial):
        """Cập nhật serial khi cửa sổ mục tiêu chuyển sang thiết bị khác."""
        if new_serial and new_serial != self.device_serial:
            self.device_serial = new_serial
            self.setWindowTitle(self._build_window_title())
            self._refresh_header_text()
            self._append_system_log(f"Đã chuyển mục tiêu sang thiết bị: {self.get_current_serial_display()}")

    def _refresh_header_text(self):
        serial_str = self.device_serial or (self.overlay.device_serial if self.overlay else None)
        if self.demo_mode:
            self.lbl_device_header.setText("🔒 CHẾ ĐỘ DEMO | Mục tiêu: Mô phỏng thiết bị [Phone-R3CT104B80P]")
        elif serial_str:
            self.lbl_device_header.setText(f"🔒 ĐÃ KHÓA THIẾT BỊ ĐÍCH: [{serial_str}] | Mọi lệnh chỉ áp dụng cho máy này")
        else:
            self.lbl_device_header.setText("⚠️ Chưa nhận diện được Serial cụ thể | Sẽ áp dụng cho thiết bị mặc định")

    def clear_output(self):
        self.txt_output.clear()

    def _append_system_log(self, text):
        now = time.strftime("%H:%M:%S")
        self.txt_output.appendPlainText(f"[{now}] ℹ️ {text}")
        self._scroll_to_bottom()

    def _append_command_log(self, cmd_display):
        now = time.strftime("%H:%M:%S")
        self.txt_output.appendPlainText(f"\n[{now}] $ {cmd_display}")
        self._scroll_to_bottom()

    def _append_output_log(self, text, is_error=False):
        if is_error:
            self.txt_output.appendPlainText(f"[LỖI] {text}")
        else:
            self.txt_output.appendPlainText(text)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        sb = self.txt_output.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def run_quick_command(self, cmd_text):
        self.input_cmd.setText(cmd_text)
        self.on_execute_clicked()

    def on_execute_clicked(self):
        raw_cmd = self.input_cmd.text().strip()
        if not raw_cmd:
            return

        self.input_cmd.add_history(raw_cmd)
        self.execute_command_isolated(raw_cmd)

    def execute_command_isolated(self, raw_input):
        target_serial = self.device_serial or (self.overlay.device_serial if self.overlay else None)
        final_cmd, err = self._parse_and_build_command(raw_input, target_serial)
        if err:
            self._append_output_log(err, is_error=True)
            return

        display_str = " ".join(final_cmd)
        self._append_command_log(display_str)

        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳...")

        self.worker = AdbCommandWorker(
            final_cmd,
            demo_mode=self.demo_mode,
            demo_serial=str(target_serial or "DemoDevice")
        )
        self.worker.output_received.connect(self._append_output_log)
        self.worker.finished_code.connect(self._on_command_finished)
        self.worker.start()

    def _on_command_finished(self, code):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("Chạy (Enter)")
        self.input_cmd.setFocus()

    def _parse_and_build_command(self, user_input_str, target_serial):
        """
        Thuật toán phân tích lệnh và ép buộc chỉ định thiết bị:
        - Tách chuỗi theo shlex để giữ nguyên dấu ngoặc nháy đơn/kép.
        - Bỏ qua tiền tố 'adb' hoặc 'adb.exe' nếu có.
        - Tự động lọc bỏ các cờ -s, -sSerial, --serial, --serial=... do người dùng gõ
          để KHÔNG BAO GIỜ bị gửi nhầm sang thiết bị khác!
        - Tự động gắn tiền tố: [adb_bin, "-s", target_serial] vào trước toàn bộ lệnh.
        """
        import shlex
        try:
            tokens = shlex.split(user_input_str, posix=False)
        except Exception:
            tokens = user_input_str.split()

        if not tokens:
            return None, "Vui lòng nhập lệnh hợp lệ."

        # Bỏ qua 'adb' / 'adb.exe' ở đầu
        if tokens[0].lower() in ["adb", "adb.exe"]:
            tokens = tokens[1:]

        cleaned = []
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t in ["-s", "--serial"]:
                i += 2  # Bỏ qua cờ -s và chuỗi serial đi kèm
                continue
            elif t.startswith("-s") and len(t) > 2:
                i += 1  # Bỏ qua dạng -sSerial
                continue
            elif t.startswith("--serial="):
                i += 1  # Bỏ qua dạng --serial=Serial
                continue
            else:
                cleaned.append(t)
                i += 1

        if not cleaned:
            return None, "Vui lòng nhập nội dung lệnh ADB (ví dụ: shell input keyevent 3)"

        adb_bin = REAL_ADB_PATH or "adb"
        if target_serial and not self.demo_mode:
            final_cmd = [adb_bin, "-s", str(target_serial)] + cleaned
        else:
            final_cmd = [adb_bin] + cleaned

        return final_cmd, None


# ===========================================================================
# LỚP GIAO DIỆN CHÍNH: OVERLAY TRONG SUỐT (TRANSPARENT OVERLAY)
# ===========================================================================

class TransparentOverlay(QWidget):
    export_finished = Signal(bool, str)

    def __init__(self, target_title="QtScrcpy", device_serial=None, demo_mode=False):
        super().__init__()
        self.target_title = target_title
        self.device_serial = device_serial
        self.demo_mode = demo_mode
        self.target_hwnd = None
        self.matched_title = ""
        self.adb_terminal_dialog = None
        self.export_finished.connect(self._on_export_finished)

        # Trạng thái ứng dụng
        self.is_scanning = False
        self.elements = []
        self.phone_width = 1080
        self.phone_height = 2400
        self.status_message = "Sẵn sàng"
        self.hovered_element = None
        self.hovered_grid_cell = None  # (elem, r, c)

        # Hiệu ứng thị giác khi click chuột
        self.click_effect_box = None
        self.click_effect_cell = None  # (elem, r, c)
        self.click_effect_timer = QTimer(self)
        self.click_effect_timer.setSingleShot(True)
        self.click_effect_timer.timeout.connect(self._clear_click_effect)

        # Hiệu ứng nhấp nháy chậm của Cursor trong ô nhập liệu (700ms)
        self.cursor_blink_visible = True
        self.cursor_blink_timer = QTimer(self)
        self.cursor_blink_timer.timeout.connect(self._toggle_cursor_blink)
        self.cursor_blink_timer.start(700)

        # Biến Scale
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.video_w = 0.0
        self.video_h = 0.0

        # Khởi tạo kết nối Android & Giao diện
        self.device = None
        self.init_android_device()
        self.init_window_flags()
        self.init_ui_components()

        # Timer bám đuôi cửa sổ QtScrcpy (50ms/lần)
        self.track_timer = QTimer(self)
        self.track_timer.timeout.connect(self.track_qtscrcpy)
        self.track_timer.start(50)

        self.scanner_worker = None
        self.table_picker_popup = None

    def init_android_device(self):
        """Khởi tạo kết nối uiautomator2 tới điện thoại."""
        if self.demo_mode:
            self.phone_width = 1080
            self.phone_height = 2400
            self.status_message = "Chế độ Demo: Mô phỏng điện thoại 1080x2400"
            print(f"[DEMO] {self.status_message}")
            return

        if not HAVE_U2:
            self.status_message = "Chưa cài đặt uiautomator2! Hãy chạy: pip install uiautomator2"
            print(f"[CẢNH BÁO] {self.status_message}")
            return

        try:
            if not self.device_serial:
                connected = get_connected_serials()
                if connected:
                    self.device_serial = connected[0]
                    print(f"[ADB] Tự động chọn thiết bị: {self.device_serial}")

            if self.device_serial:
                self.device = u2.connect(self.device_serial)
            else:
                self.device = u2.connect()

            w, h = self.device.window_size()
            self.phone_width = w
            self.phone_height = h
            self.status_message = f"Đã kết nối ({w}x{h})"
            print(f"[ADB] Kết nối thành công! Thiết bị: {self.device_serial or 'Mặc định'}, Độ phân giải: {w}x{h}")
        except Exception as e:
            self.status_message = f"Chưa kết nối ADB: {str(e)}"
            print(f"[ADB LỖI] {self.status_message}")

    def init_window_flags(self):
        """Thiết lập cửa sổ không viền, trong suốt, luôn trên cùng."""
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    def init_ui_components(self):
        """Tạo các nút bấm điều khiển (Control Bar) và nút Thoát ứng dụng ngay bên dưới."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.addStretch()

        # Container bao bọc toàn bộ thanh điều khiển và nút thoát ở đáy
        self.bottom_container = QWidget(self)
        self.bottom_container.setObjectName("BottomContainer")

        container_layout = QVBoxLayout(self.bottom_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        # 1. THANH CÔNG CỤ CHÍNH BÁM DÍNH (Top Bar)
        self.bottom_bar = QFrame(self.bottom_container)
        self.bottom_bar.setObjectName("BottomBar")
        self.bottom_bar.setStyleSheet("""
            #BottomBar {
                background-color: rgba(12, 18, 28, 240);
                border: 1px solid rgba(0, 240, 255, 95);
                border-radius: 8px;
            }
            QPushButton {
                color: #FFFFFF;
                font-weight: bold;
                font-size: 11px;
                padding: 6px 12px;
                border-radius: 5px;
                border: none;
            }
            #BtnScan {
                background-color: #0284C7;
            }
            #BtnScan:hover {
                background-color: #0369A1;
            }
            #BtnAdb {
                background-color: #064E3B;
                color: #4ADE80;
                border: 1px solid #10B981;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                font-weight: bold;
            }
            #BtnAdb:hover {
                background-color: #047857;
                color: #86EFAC;
                border: 1px solid #34D399;
            }
            #BtnAdb:pressed {
                background-color: #065F46;
            }
            #BtnCancel {
                background-color: #DC2626;
            }
            #BtnCancel:hover {
                background-color: #B91C1C;
            }
            #BtnGrid {
                background-color: #7C3AED;
            }
            #BtnGrid:hover {
                background-color: #6D28D9;
            }
            #BtnExport {
                background-color: #059669;
            }
            #BtnExport:hover {
                background-color: #047857;
            }
            #StatusLabel {
                color: #38BDF8;
                font-size: 11px;
                font-weight: 500;
                margin-left: 6px;
            }
        """)

        bar_layout = QHBoxLayout(self.bottom_bar)
        bar_layout.setContentsMargins(6, 4, 6, 4)
        bar_layout.setSpacing(6)

        # Nút kích hoạt / quét lại XML
        self.btn_scan = QPushButton("🔍 Soi XML", self.bottom_bar)
        self.btn_scan.setObjectName("BtnScan")
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        self.btn_scan.clicked.connect(self.toggle_scan_mode)
        bar_layout.addWidget(self.btn_scan)

        # Nút dòng lệnh ADB nhanh (màu xanh lá cây cmd hacker, khóa chặt thiết bị đích)
        self.btn_adb = QPushButton("💻 Lệnh ADB", self.bottom_bar)
        self.btn_adb.setObjectName("BtnAdb")
        self.btn_adb.setCursor(Qt.PointingHandCursor)
        self.btn_adb.setToolTip("Mở cửa sổ dòng lệnh ADB nhanh (Khóa chặt thiết bị đích) - Phím F7")
        self.btn_adb.clicked.connect(self.open_adb_terminal)
        bar_layout.addWidget(self.btn_adb)

        # Nút Tắt XML thủ công (ESC)
        self.btn_cancel = QPushButton("❌ Tắt XML (ESC)", self.bottom_bar)
        self.btn_cancel.setObjectName("BtnCancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.exit_scan_mode)
        self.btn_cancel.setVisible(False)
        bar_layout.addWidget(self.btn_cancel)

        # Nút Chia lưới ô (Bàn phím ảo mô phỏng)
        self.btn_grid = QPushButton("📐 Chia lưới", self.bottom_bar)
        self.btn_grid.setObjectName("BtnGrid")
        self.btn_grid.setCursor(Qt.PointingHandCursor)
        self.btn_grid.setToolTip("Chia khung đang rê chuột thành bảng bàn phím ảo (Chuột phải vào khung)")
        self.btn_grid.clicked.connect(self.on_grid_button_clicked)
        self.btn_grid.setVisible(False)
        bar_layout.addWidget(self.btn_grid)

        # Nút Trích xuất file XML (adb pull ra Downloads\XMlExtracted)
        self.btn_export = QPushButton("📥 Xuất XML", self.bottom_bar)
        self.btn_export.setObjectName("BtnExport")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setToolTip("Trích xuất file XML đầy đủ layout & text ra %USERPROFILE%\\Downloads\\XMlExtracted (Ctrl+S)")
        self.btn_export.clicked.connect(self.export_xml_hierarchy)
        bar_layout.addWidget(self.btn_export)

        # Nhãn hiển thị trạng thái
        self.lbl_status = QLabel(self.status_message, self.bottom_bar)
        self.lbl_status.setObjectName("StatusLabel")
        self.lbl_status.setMinimumWidth(0)
        bar_layout.addWidget(self.lbl_status)
        bar_layout.addStretch()

        container_layout.addWidget(self.bottom_bar)

        # 2. NÚT THOÁT Ở NGAY DƯỚI THANH HIỂN THỊ (Exit Sub-Bar)
        self.exit_bar = QFrame(self.bottom_container)
        self.exit_bar.setObjectName("ExitBar")
        self.exit_bar.setStyleSheet("""
            #ExitBar {
                background-color: rgba(10, 15, 25, 235);
                border: 1px solid rgba(239, 68, 68, 80);
                border-radius: 7px;
            }
            QPushButton {
                background-color: #B91C1C;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 10px;
                padding: 4px 10px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
            #LblHint {
                color: #94A3B8;
                font-size: 10px;
                margin-left: 6px;
            }
        """)

        exit_layout = QHBoxLayout(self.exit_bar)
        exit_layout.setContentsMargins(6, 3, 6, 3)
        exit_layout.setSpacing(8)

        self.btn_exit = QPushButton("⏻ Thoát", self.exit_bar)
        self.btn_exit.setCursor(Qt.PointingHandCursor)
        self.btn_exit.setToolTip("Đóng hoàn toàn tiến trình trợ lý Overlay")
        self.btn_exit.clicked.connect(self.close_application)
        exit_layout.addWidget(self.btn_exit)

        self.lbl_hint = QLabel("💡 Chuột phải: Chia lưới | F5: Quét | Ctrl+S: Xuất XML | F7: Lệnh ADB | ESC: Tắt", self.exit_bar)
        self.lbl_hint.setObjectName("LblHint")
        self.lbl_hint.setMinimumWidth(0)
        exit_layout.addWidget(self.lbl_hint)
        exit_layout.addStretch()

        container_layout.addWidget(self.exit_bar)

        self.main_layout.addWidget(self.bottom_container)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 190))
        shadow.setOffset(0, 3)
        self.bottom_container.setGraphicsEffect(shadow)

        # RẤT QUAN TRỌNG: Gỡ bỏ ép buộc kích thước tối thiểu (SetNoConstraint)
        # để cửa sổ Overlay tự do co giãn bám khít từng pixel theo cửa sổ QtScrcpy
        # không bao giờ bị phình to hơn hay lệch tâm khung hình
        self.main_layout.setSizeConstraint(QLayout.SetNoConstraint)
        container_layout.setSizeConstraint(QLayout.SetNoConstraint)
        bar_layout.setSizeConstraint(QLayout.SetNoConstraint)
        exit_layout.setSizeConstraint(QLayout.SetNoConstraint)

        self.setMinimumSize(1, 1)
        self.bottom_container.setMinimumSize(1, 1)
        self.bottom_bar.setMinimumSize(1, 1)
        self.exit_bar.setMinimumSize(1, 1)

        self.update_click_through_mask()

    def open_adb_terminal(self):
        """Mở hoặc hiển thị lại cửa sổ dòng lệnh ADB nhanh cô lập riêng cho thiết bị này."""
        if self.adb_terminal_dialog is None:
            self.adb_terminal_dialog = AdbCommandDialog(
                overlay=self,
                device_serial=self.device_serial,
                demo_mode=self.demo_mode
            )
        else:
            self.adb_terminal_dialog.update_device_serial(self.device_serial)

        self.adb_terminal_dialog.show()
        self.adb_terminal_dialog.raise_()
        self.adb_terminal_dialog.activateWindow()

    def close_application(self):
        """Đóng hoàn toàn ứng dụng Python Overlay."""
        print("[THOÁT] Đóng ứng dụng Overlay theo yêu cầu người dùng.")
        self.track_timer.stop()
        if hasattr(self, 'cursor_blink_timer'):
            self.cursor_blink_timer.stop()
        if hasattr(self, 'adb_terminal_dialog') and self.adb_terminal_dialog:
            self.adb_terminal_dialog.close()
        self.hide()
        QApplication.quit()

    # =======================================================================
    # BÁM ĐUÔI CỬA SỔ QTSCRCPY (TRACKING LOGIC)
    # =======================================================================

    def track_qtscrcpy(self):
        """Tìm và đồng bộ vị trí, kích thước với cửa sổ chia sẻ màn hình điện thoại."""
        ensure_desktop_attached()

        # 1. Kiểm tra nhanh nếu HWND đã tìm được trước đó vẫn còn tồn tại và hiển thị
        is_current_valid = False
        if self.target_hwnd:
            if user32.IsWindow(self.target_hwnd) and user32.IsWindowVisible(self.target_hwnd) and not user32.IsIconic(self.target_hwnd):
                is_current_valid = True

        if not is_current_valid:
            hwnd, title = find_target_window(self.target_title, self.device_serial)
            self.target_hwnd = hwnd
            self.matched_title = title
        else:
            title_len = user32.GetWindowTextLengthW(self.target_hwnd)
            if title_len > 0:
                tbuff = ctypes.create_unicode_buffer(title_len + 1)
                user32.GetWindowTextW(self.target_hwnd, tbuff, title_len + 1)
                self.matched_title = tbuff.value

        if not self.target_hwnd:
            if self.isVisible():
                self.hide()
            return

        # Tự động cập nhật kết nối nếu người dùng chuyển sang cửa sổ Phone-<serial> khác
        if not self.demo_mode and self.matched_title and self.matched_title.startswith("Phone-"):
            extracted_serial = self.matched_title.replace("Phone-", "").strip()
            if extracted_serial and extracted_serial != self.device_serial:
                self.device_serial = extracted_serial
                print(f"[ADB] Tự động phát hiện serial từ cửa sổ: {self.device_serial}")
                self.init_android_device()
                if hasattr(self, 'adb_terminal_dialog') and self.adb_terminal_dialog:
                    self.adb_terminal_dialog.update_device_serial(self.device_serial)

        rect = get_client_rect_screen(self.target_hwnd)
        if not rect:
            if self.isVisible():
                self.hide()
            return

        target_x, target_y, target_w, target_h = rect

        current_geo = self.geometry()
        geo_changed = (
            current_geo.x() != target_x or
            current_geo.y() != target_y or
            current_geo.width() != target_w or
            current_geo.height() != target_h
        )

        if geo_changed:
            self.setGeometry(target_x, target_y, target_w, target_h)
            self.update_click_through_mask()
            if self.is_scanning and self.elements:
                self.update()

        if not self.isVisible():
            self.show()

    # =======================================================================
    # CƠ CHẾ CLICK-THROUGH (XUYÊN THẤU CHUỘT)
    # =======================================================================

    def update_click_through_mask(self):
        """
        Khi is_scanning = False: Cả thanh Bottom Bar và nút Thoát ứng dụng vẫn nhận click bình thường!
        Khi is_scanning = True: Toàn bộ Overlay nhận click để tương tác tự do.
        """
        if self.is_scanning:
            self.clearMask()
        else:
            container_geo = self.bottom_container.geometry()
            if not container_geo.isEmpty():
                self.setMask(QRegion(container_geo))

    def _toggle_cursor_blink(self):
        """Hiệu ứng nhấp nháy chậm của Cursor trong ô nhập liệu."""
        self.cursor_blink_visible = not self.cursor_blink_visible
        if self.is_scanning:
            self.update()

    def _clear_click_effect(self):
        """Xóa hiệu ứng highlight nhấp nháy khi vừa bấm."""
        self.click_effect_box = None
        self.click_effect_cell = None
        if self.is_scanning:
            self.update()

    # =======================================================================
    # BẬT / TẮT THỦ CÔNG & QUÉT GIAO DIỆN XML
    # =======================================================================

    def toggle_scan_mode(self):
        """Bật hoặc quét lại giao diện XML."""
        self.enter_scan_mode()

    def enter_scan_mode(self):
        """Kích hoạt chế độ soi XML."""
        # 1. Đồng bộ ngay lập tức vị trí cửa sổ với QtScrcpy trước khi quét
        self.track_qtscrcpy()

        # 2. Xóa các phần tử cũ để không bị vẽ đè lệch vị trí trong lúc chờ quét XML
        self.elements = []
        self.hovered_element = None
        self.hovered_grid_cell = None
        self.click_effect_box = None
        self.click_effect_cell = None

        self.is_scanning = True
        self.btn_scan.setText("🔄 Đang quét...")
        self.btn_scan.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.btn_grid.setVisible(True)
        self.lbl_status.setText("Đang trích xuất giao diện...")
        self.update_click_through_mask()
        self.update()

        self.scanner_worker = XMLScannerWorker(self.device, demo=self.demo_mode)
        self.scanner_worker.scan_success.connect(self.on_scan_success)
        self.scanner_worker.scan_failed.connect(self.on_scan_failed)
        self.scanner_worker.start()

    def exit_scan_mode(self):
        """TẮT THỦ CÔNG: Chỉ tắt khi bấm nút hoặc ấn phím ESC."""
        self.is_scanning = False
        self.elements = []
        self.hovered_element = None
        self.hovered_grid_cell = None
        self.click_effect_box = None
        self.click_effect_cell = None
        self.btn_scan.setText("🔍 Soi XML")
        self.btn_scan.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.btn_grid.setVisible(False)
        self.lbl_status.setText(f"Đã tắt. Đang dính: {self.matched_title or 'QtScrcpy'}")
        self.update_click_through_mask()
        self.update()

    def on_scan_success(self, elements, phone_w, phone_h):
        """Quét XML thành công."""
        # 1. Đồng bộ lại cửa sổ phòng khi người dùng di chuyển cửa sổ QtScrcpy trong khi quét
        self.track_qtscrcpy()

        # 2. Cập nhật kích thước và elements mới
        self.phone_width = phone_w
        self.phone_height = phone_h
        self.elements = elements

        # 3. Tính toán trước scale và pc_rect cho toàn bộ elements để vẽ chuẩn xác 100% ngay frame đầu tiên
        scale, off_x, off_y, vid_w, vid_h = self.calculate_scale_and_offsets()
        for elem in self.elements:
            box_x = int(off_x + elem["x1"] * scale)
            box_y = int(off_y + elem["y1"] * scale)
            box_w = int(elem["width"] * scale)
            box_h = int(elem["height"] * scale)
            elem["pc_rect"] = QRect(box_x, box_y, box_w, box_h)

        self.btn_scan.setText("🔄 Quét lại (F5)")
        self.btn_scan.setEnabled(True)
        self.lbl_status.setText(f"Đã tải {len(elements)} phần tử. Bấm liên tiếp thoải mái!")
        self.update()

    def on_scan_failed(self, error_msg):
        """Quét XML thất bại."""
        self.btn_scan.setText("🔍 Soi XML")
        self.btn_scan.setEnabled(True)
        self.lbl_status.setText(f"❌ {error_msg}")
        self.update()

    # =======================================================================
    # TRÍCH XUẤT FILE XML (CẢ TEXT LẪN LAYOUT ĐẦY ĐỦ) RA THƯ MỤC MẶC ĐỊNH
    # adb pull /sdcard/window_dump.xml %USERPROFILE%\Downloads\XMlExtracted
    # =======================================================================

    def export_xml_hierarchy(self):
        """Trích xuất file XML đầy đủ layout & text ra %USERPROFILE%\\Downloads\\XMlExtracted."""
        self.btn_export.setEnabled(False)
        self.btn_export.setText("⏳ Đang xuất...")
        self.lbl_status.setText("Đang trích xuất file XML...")
        Thread(target=self._export_xml_worker, daemon=True).start()

    def _on_export_finished(self, success, message):
        self.btn_export.setEnabled(True)
        self.btn_export.setText("📥 Xuất XML")
        self.lbl_status.setText(message)
        print(f"[XUẤT XML] {message}")

    def _export_xml_worker(self):
        try:
            out_dir = os.path.expandvars(r"%USERPROFILE%\Downloads\XMlExtracted")
            os.makedirs(out_dir, exist_ok=True)
            default_target = os.path.join(out_dir, "window_dump.xml")
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            timestamp_target = os.path.join(out_dir, f"window_dump_{timestamp}.xml")

            xml_content = None

            if self.demo_mode:
                xml_content = """<hierarchy rotation="0">
  <node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">
    <node class="android.widget.TextView" text="Nhập Mật khẩu ShopeePay" bounds="[60,300][980,420]" />
    <node class="android.widget.EditText" resource-id="com.shopee:id/payment_password_field" text="••" desc="Ô nhập mã PIN" bounds="[130,520][950,670]" focused="true" password="true" />
    <node class="android.view.View" resource-id="keyboard_number_view" bounds="[60,1100][1020,2100]" text="" desc="Bàn phím bảo mật ShopeePay" clickable="true" />
    <node class="android.widget.TextView" resource-id="key1" text="1" bounds="[180,1200][360,1360]" clickable="true" />
    <node class="android.widget.TextView" resource-id="key2" text="2" bounds="[450,1200][630,1360]" clickable="true" />
    <node class="android.widget.TextView" resource-id="key3" text="3" bounds="[720,1200][900,1360]" clickable="true" />
    <node class="android.widget.TextView" resource-id="delete_button" text="XÓA" bounds="[720,1850][900,2020]" clickable="true" />
  </node>
</hierarchy>"""
                with open(default_target, "w", encoding="utf-8") as f:
                    f.write(xml_content)
                with open(timestamp_target, "w", encoding="utf-8") as f:
                    f.write(xml_content)
            else:
                adb_bin = REAL_ADB_PATH or "adb"
                serial_args = ["-s", self.device_serial] if self.device_serial else []

                # 1. Thử dump bằng lệnh adb uiautomator dump chuẩn /sdcard/window_dump.xml
                dump_cmd = [adb_bin] + serial_args + ["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"]
                subprocess.run(dump_cmd, capture_output=True, text=True, timeout=8)

                # 2. Thực hiện lệnh adb pull /sdcard/window_dump.xml %USERPROFILE%\Downloads\XMlExtracted
                pull_cmd = [adb_bin] + serial_args + ["pull", "/sdcard/window_dump.xml", default_target]
                subprocess.run(pull_cmd, capture_output=True, text=True, timeout=8)

                if os.path.isfile(default_target) and os.path.getsize(default_target) > 50:
                    with open(default_target, "r", encoding="utf-8", errors="replace") as f:
                        xml_content = f.read()
                else:
                    # Phương án dự phòng: Nếu adb dump bị vướng, trích xuất trực tiếp qua uiautomator2 (compressed=False để giữ trọn text và layout)
                    if self.device:
                        xml_content = self.device.dump_hierarchy(compressed=False)
                        with open(default_target, "w", encoding="utf-8") as f:
                            f.write(xml_content)
                        try:
                            self.device.push(default_target, "/sdcard/window_dump.xml")
                        except Exception:
                            pass
                    else:
                        self.export_finished.emit(False, "❌ Không kết nối được thiết bị để trích xuất XML!")
                        return

                if xml_content:
                    with open(timestamp_target, "w", encoding="utf-8") as f:
                        f.write(xml_content)

            size_kb = os.path.getsize(default_target) / 1024.0
            msg = f"✅ Đã xuất XML ({size_kb:.0f}KB) ra Downloads\\XMlExtracted\\window_dump.xml"
            self.export_finished.emit(True, msg)

        except Exception as e:
            self.export_finished.emit(False, f"❌ Lỗi xuất XML: {str(e)}")

    # =======================================================================
    # XỬ LÝ CHIA LƯỚI BÀN PHÍM ẢO
    # =======================================================================

    def on_grid_button_clicked(self):
        """Mở công cụ chia lưới cho phần tử đang chọn hoặc đang rê chuột."""
        target = self.hovered_element or self.click_effect_box
        if not target and self.elements:
            for e in self.elements:
                if any(k in e.get("res_id", "").lower() for k in ["keyboard", "keypad", "number", "pin"]):
                    target = e
                    break
            if not target:
                target = self.elements[0]

        if target:
            self.open_table_picker_for_element(target)
        else:
            self.lbl_status.setText("👉 Rê chuột hoặc bấm chuột phải vào khung cần chia lưới!")

    def open_table_picker_for_element(self, elem):
        """Hiển thị Popup kéo thả chia lưới phong cách Word."""
        self.table_picker_popup = WordTablePickerPopup(elem.get("label", "Khung"), self)
        pos = QCursor.pos()
        self.table_picker_popup.move(max(10, pos.x() - 60), max(10, pos.y() - 160))
        self.table_picker_popup.grid_selected.connect(lambda r, c: self._apply_grid_to_element(elem, r, c))
        self.table_picker_popup.show()

    def _apply_grid_to_element(self, elem, r, c):
        """Áp dụng cấu hình chia lưới vào phần tử."""
        if r > 0 and c > 0:
            elem["grid"] = {"rows": r, "cols": c}
            hint = " (Bàn phím số PIN)" if (r == 4 and c == 3) else ""
            self.lbl_status.setText(f"✅ Đã chia lưới {r}×{c}{hint} cho '{elem['label']}'")
            print(f"[GRID] Đã tạo lưới {r}x{c} cho phần tử '{elem['label']}'")
        else:
            elem.pop("grid", None)
            self.lbl_status.setText(f"🗑 Đã xóa lưới của '{elem['label']}'")
        self.update()

    # =======================================================================
    # TÍNH TOÁN TỈ LỆ KHUNG HÌNH (SCALING & ASPECT RATIO)
    # =======================================================================

    def calculate_scale_and_offsets(self):
        pc_w = self.width()
        pc_h = self.height()
        phone_w = self.phone_width
        phone_h = self.phone_height

        if phone_w <= 0 or phone_h <= 0 or pc_w <= 0 or pc_h <= 0:
            return 1.0, 0.0, 0.0, pc_w, pc_h

        aspect_phone = float(phone_w) / float(phone_h)
        aspect_pc = float(pc_w) / float(pc_h)

        # Ngưỡng dung sai tỷ lệ 0.8% để tránh giật viền sub-pixel (letterboxing jitter)
        # khi kích thước cửa sổ QtScrcpy chỉ lệch 1-2 pixel do làm tròn số nguyên
        if abs(aspect_pc - aspect_phone) < 0.008:
            self.video_w = float(pc_w)
            self.video_h = float(pc_h)
            self.offset_x = 0.0
            self.offset_y = 0.0
            self.scale = float(pc_w) / float(phone_w)
        elif aspect_pc > aspect_phone:
            self.video_h = float(pc_h)
            self.video_w = float(pc_h) * aspect_phone
            self.offset_x = (pc_w - self.video_w) / 2.0
            self.offset_y = 0.0
            self.scale = self.video_h / float(phone_h)
        else:
            self.video_w = float(pc_w)
            self.video_h = float(pc_w) / aspect_phone
            self.offset_x = 0.0
            self.offset_y = (pc_h - self.video_h) / 2.0
            self.scale = self.video_w / float(phone_w)

        return self.scale, self.offset_x, self.offset_y, self.video_w, self.video_h

    # =======================================================================
    # VẼ GIAO DIỆN BOUNDING BOX, Ô NHẬP LIỆU & LƯỚI BÀN PHÍM ẢO
    # =======================================================================

    def paintEvent(self, event):
        if not self.is_scanning:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        scale, off_x, off_y, vid_w, vid_h = self.calculate_scale_and_offsets()

        # Lớp nền đen mờ bao phủ video
        video_rect = QRect(int(off_x), int(off_y), int(vid_w), int(vid_h))
        painter.fillRect(video_rect, QColor(0, 0, 0, 135))

        if not self.elements:
            # Hiển thị thông báo đang trích xuất dữ liệu XML nhẹ nhàng ở giữa màn hình
            painter.setPen(QColor(0, 240, 255, 220))
            painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
            painter.drawText(video_rect, Qt.AlignCenter, "🔄 Đang trích xuất dữ liệu XML...")
            painter.end()
            return

        sorted_elements = sorted(self.elements, key=lambda e: e["area"], reverse=True)
        font_label = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font_label)

        for elem in sorted_elements:
            box_x = int(off_x + elem["x1"] * scale)
            box_y = int(off_y + elem["y1"] * scale)
            box_w = int(elem["width"] * scale)
            box_h = int(elem["height"] * scale)
            rect = QRect(box_x, box_y, box_w, box_h)
            elem["pc_rect"] = rect

            is_hovered = (elem == self.hovered_element)
            is_input = elem.get("is_input", False)
            is_just_clicked = (self.click_effect_box == elem)

            # ---------------------------------------------------------------
            # 1. THIẾT KẾ MÀU SẮC THEO YÊU CẦU:
            # - Ô NHẬP LIỆU: MÀU TÍM (PURPLE)
            # - CÁC KHUNG CÒN LẠI: MÀU CYAN (XANH LƠ SÁNG)
            # ---------------------------------------------------------------
            if is_just_clicked:
                pen = QPen(QColor(52, 211, 153), 3)
                painter.setPen(pen)
                painter.setBrush(QColor(52, 211, 153, 90))
            elif is_input:
                # KHU VỰC CURSOR NHẬP LIỆU: MÀU TÍM
                if is_hovered:
                    pen = QPen(QColor(216, 180, 254), 3)
                    painter.setPen(pen)
                    painter.setBrush(QColor(168, 85, 247, 75))
                else:
                    pen = QPen(QColor(192, 38, 211), 2.5)
                    painter.setPen(pen)
                    painter.setBrush(QColor(168, 85, 247, 40))
            elif is_hovered:
                # Cyan sáng rực khi rê chuột
                pen = QPen(QColor(0, 255, 255), 3)
                painter.setPen(pen)
                painter.setBrush(QColor(0, 255, 255, 60))
            elif elem["clickable"]:
                # Khung bình thường: Cyan
                pen = QPen(QColor(0, 229, 255, 230), 2)
                painter.setPen(pen)
                painter.setBrush(QColor(0, 229, 255, 12))
            else:
                pen = QPen(QColor(0, 180, 216, 150), 1.5, Qt.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)

            painter.drawRect(rect)

            # ---------------------------------------------------------------
            # 2. VẼ BIỂU TƯỢNG CURSOR ĐANG NHẤP NHÁY CHẬM TRONG Ô NHẬP LIỆU
            # ---------------------------------------------------------------
            if is_input and self.cursor_blink_visible and box_w > 15 and box_h > 10:
                cur_h = max(14, min(int(box_h * 0.65), 30))
                cur_top = box_y + (box_h - cur_h) // 2
                cur_bot = cur_top + cur_h

                metrics = painter.fontMetrics()
                text_len_px = metrics.horizontalAdvance(elem.get("text", "")) if elem.get("text") else 0
                cur_x = box_x + 14 + (text_len_px if text_len_px < box_w - 30 else 0)

                painter.fillRect(cur_x - 1, cur_top - 1, 5, cur_h + 2, QColor(192, 38, 211, 120))
                painter.fillRect(cur_x, cur_top, 3, cur_h, QColor(255, 255, 255, 255))

                painter.setPen(QPen(QColor(255, 255, 255, 240), 1.5))
                painter.drawLine(cur_x - 3, cur_top, cur_x + 5, cur_top)
                painter.drawLine(cur_x - 3, cur_bot, cur_x + 5, cur_bot)

            # ---------------------------------------------------------------
            # 3. VẼ LƯỚI BÀN PHÍM ẢO (VIRTUAL KEYPAD GRID) NẾU CÓ
            # ---------------------------------------------------------------
            if elem.get("grid"):
                g_rows = elem["grid"]["rows"]
                g_cols = elem["grid"]["cols"]

                # Font cho phím số
                key_font = QFont("Segoe UI", max(9, min(int(box_h / g_rows * 0.35), 18)), QFont.Bold)
                painter.setFont(key_font)

                for r in range(g_rows):
                    for c in range(g_cols):
                        cx1 = box_x + int(c * box_w / g_cols)
                        cy1 = box_y + int(r * box_h / g_rows)
                        cx2 = box_x + int((c + 1) * box_w / g_cols)
                        cy2 = box_y + int((r + 1) * box_h / g_rows)
                        cw = cx2 - cx1
                        ch = cy2 - cy1
                        cell_rect = QRect(cx1, cy1, cw, ch)

                        is_cell_hov = (self.hovered_grid_cell == (elem, r, c))
                        is_cell_clicked = (self.click_effect_cell == (elem, r, c))

                        if is_cell_clicked:
                            painter.setPen(QPen(QColor(52, 211, 153), 2.5))
                            painter.setBrush(QColor(52, 211, 153, 140))
                        elif is_cell_hov:
                            painter.setPen(QPen(QColor(255, 255, 255), 2))
                            painter.setBrush(QColor(0, 240, 255, 80))
                        else:
                            painter.setPen(QPen(QColor(0, 240, 255, 130), 1, Qt.DashLine))
                            painter.setBrush(QColor(15, 23, 42, 60))

                        painter.drawRect(cell_rect)

                        # Nhãn phím số (chuẩn 4x3) hoặc số thứ tự
                        if g_rows == 4 and g_cols == 3:
                            cell_text = KEYPAD_LABELS_4X3[r][c]
                        else:
                            cell_text = f"{r * g_cols + c + 1}"

                        if cell_text:
                            # Nút tròn giả lập bàn phím số
                            btn_radius = int(min(cw, ch) * 0.38)
                            btn_center = QPoint(cx1 + cw // 2, cy1 + ch // 2)
                            if not is_cell_clicked and not is_cell_hov:
                                painter.setPen(QPen(QColor(0, 240, 255, 120), 1.5))
                                painter.setBrush(QColor(20, 28, 42, 210))
                                painter.drawEllipse(btn_center, btn_radius, btn_radius)

                            if is_cell_clicked:
                                painter.setPen(QColor(255, 255, 255))
                            elif is_cell_hov:
                                painter.setPen(QColor(0, 255, 255))
                            else:
                                painter.setPen(QColor(240, 249, 255))

                            painter.drawText(cell_rect, Qt.AlignCenter, cell_text)

                painter.setFont(font_label)

            # ---------------------------------------------------------------
            # 4. VẼ NHÃN BADGE (TAG) PHÍA TRÊN MỖI PHẦN TỬ
            # ---------------------------------------------------------------
            label_text = elem["label"]
            if elem.get("grid"):
                label_text = f"⊞ [{elem['grid']['rows']}×{elem['grid']['cols']}] {label_text}"
            elif is_input and not label_text.startswith("⌨"):
                label_text = f"⌨ {label_text}"

            if label_text and box_w > 20 and box_h > 12:
                if len(label_text) > 26:
                    label_text = label_text[:23] + "..."

                metrics = painter.fontMetrics()
                text_w = metrics.horizontalAdvance(label_text) + 8
                text_h = metrics.height() + 3

                tag_x = box_x + 2
                tag_y = max(box_y - text_h - 2, int(off_y) + 2) if box_y < int(off_y) + text_h else box_y + 2
                tag_rect = QRect(tag_x, tag_y, text_w, text_h)

                if is_input:
                    painter.fillRect(tag_rect, QColor(76, 29, 149, 230))
                    painter.setPen(QPen(QColor(216, 180, 254), 1))
                    painter.drawRect(tag_rect)
                    painter.setPen(QColor(245, 243, 255))
                elif elem.get("grid"):
                    painter.fillRect(tag_rect, QColor(88, 28, 135, 240))
                    painter.setPen(QPen(QColor(0, 240, 255), 1))
                    painter.drawRect(tag_rect)
                    painter.setPen(QColor(0, 240, 255))
                else:
                    painter.fillRect(tag_rect, QColor(10, 24, 34, 230))
                    painter.setPen(QPen(QColor(0, 240, 255, 180), 1))
                    painter.drawRect(tag_rect)
                    painter.setPen(QColor(0, 240, 255))

                painter.drawText(tag_rect, Qt.AlignCenter, label_text)

        painter.end()

    # =======================================================================
    # ĐIỀU HƯỚNG CLICK CHUỘT: TÍCH HỢP CHIA LƯỚI & BẤM LIÊN TIẾP
    # =======================================================================

    def mouseMoveEvent(self, event):
        """Hover chuột qua các Bounding Box và từng ô trong lưới bàn phím ảo."""
        if not self.is_scanning:
            return

        mouse_pos = event.pos()
        old_hover = self.hovered_element
        old_cell = self.hovered_grid_cell
        self.hovered_element = None
        self.hovered_grid_cell = None

        smallest_area = float("inf")
        for elem in self.elements:
            pc_rect = elem.get("pc_rect")
            if pc_rect and pc_rect.contains(mouse_pos):
                if elem["area"] < smallest_area:
                    smallest_area = elem["area"]
                    self.hovered_element = elem

        if self.hovered_element and self.hovered_element.get("grid"):
            g = self.hovered_element["grid"]
            box_rect = self.hovered_element["pc_rect"]
            cols = g["cols"]
            rows = g["rows"]
            c = max(0, min(cols - 1, int((mouse_pos.x() - box_rect.x()) / (box_rect.width() / cols))))
            r = max(0, min(rows - 1, int((mouse_pos.y() - box_rect.y()) / (box_rect.height() / rows))))
            self.hovered_grid_cell = (self.hovered_element, r, c)

        if old_hover != self.hovered_element or old_cell != self.hovered_grid_cell:
            self.update()

    def mousePressEvent(self, event):
        """
        Xử lý sự kiện click chuột:
          - Click chuột phải: Mở công cụ kéo thả chia lưới bàn phím phong cách Word.
          - Click chuột trái: Bấm nút trên điện thoại hoặc ô trong lưới bàn phím ảo.
          - KHÔNG TỰ ĐỘNG TẮT OVERLAY để người dùng nhập liên tiếp mã PIN.
        """
        if not self.is_scanning:
            return

        if self.bottom_container.geometry().contains(event.pos()):
            super().mousePressEvent(event)
            return

        # Bấm chuột phải: Mở công cụ chia lưới bàn phím ảo phong cách Word
        if event.button() == Qt.RightButton:
            click_pos = event.pos()
            target_elem = None
            smallest_area = float("inf")
            for elem in self.elements:
                pc_rect = elem.get("pc_rect")
                if pc_rect and pc_rect.contains(click_pos):
                    if elem["area"] < smallest_area:
                        smallest_area = elem["area"]
                        target_elem = elem

            if not target_elem:
                target_elem = self.hovered_element

            if target_elem:
                self.open_table_picker_for_element(target_elem)
            return

        if event.button() == Qt.LeftButton:
            click_pos = event.pos()
            scale, off_x, off_y, vid_w, vid_h = self.calculate_scale_and_offsets()

            target_elem = None
            smallest_area = float("inf")
            for elem in self.elements:
                pc_rect = elem.get("pc_rect")
                if pc_rect and pc_rect.contains(click_pos):
                    if elem["area"] < smallest_area:
                        smallest_area = elem["area"]
                        target_elem = elem

            if target_elem:
                if target_elem.get("grid"):
                    # Click vào một ô trong lưới bàn phím ảo
                    g = target_elem["grid"]
                    box_rect = target_elem["pc_rect"]
                    cols = g["cols"]
                    rows = g["rows"]
                    c = max(0, min(cols - 1, int((click_pos.x() - box_rect.x()) / (box_rect.width() / cols))))
                    r = max(0, min(rows - 1, int((click_pos.y() - box_rect.y()) / (box_rect.height() / rows))))

                    cell_w_phone = target_elem["width"] / cols
                    cell_h_phone = target_elem["height"] / rows
                    phone_click_x = int(target_elem["x1"] + (c + 0.5) * cell_w_phone)
                    phone_click_y = int(target_elem["y1"] + (r + 0.5) * cell_h_phone)

                    if rows == 4 and cols == 3:
                        cell_label = KEYPAD_LABELS_4X3[r][c] or f"Ô ({r+1},{c+1})"
                    else:
                        cell_label = f"Ô {r * cols + c + 1} ({r+1},{c+1})"

                    label_info = f"phím ảo '{cell_label}'"
                    self.click_effect_cell = (target_elem, r, c)
                    self.click_effect_box = None
                else:
                    phone_click_x = target_elem["center_x"]
                    phone_click_y = target_elem["center_y"]
                    label_info = f"'{target_elem['label']}'"
                    self.click_effect_box = target_elem
                    self.click_effect_cell = None
            else:
                phone_click_x = int((click_pos.x() - off_x) / scale)
                phone_click_y = int((click_pos.y() - off_y) / scale)
                phone_click_x = max(0, min(phone_click_x, self.phone_width - 1))
                phone_click_y = max(0, min(phone_click_y, self.phone_height - 1))
                label_info = f"({phone_click_x}, {phone_click_y})"
                self.click_effect_box = None
                self.click_effect_cell = None

            print(f"[CLICK] Đang gửi click: {label_info} tại ({phone_click_x}, {phone_click_y})")
            self.lbl_status.setText(f"✅ Đã bấm: {label_info}")

            self.click_effect_timer.start(180)
            self.update()

            if self.device or self.demo_mode:
                Thread(target=self._send_click_async, args=(phone_click_x, phone_click_y), daemon=True).start()

    def _send_click_async(self, x, y):
        """Thực thi click trên background thread."""
        if self.demo_mode:
            print(f"[DEMO ADB] Giả lập click thành công tại ({x}, {y})")
            return

        try:
            self.device.click(x, y)
            print(f"[ADB] Click thành công tại ({x}, {y})")
        except Exception as e:
            print(f"[ADB LỖI] Click thất bại: {str(e)}")

    def keyPressEvent(self, event):
        """
        Phím tắt:
          - ESC: Tắt chế độ Soi XML thủ công.
          - F5: Quét lại cây giao diện XML.
          - 0-9 & Numpad: Bấm số tương ứng (ưu tiên lưới bàn phím 4x3 nếu có).
          - Backspace: Bấm nút Xóa trên bàn phím số.
          - Enter: Bấm nút OK / Xác nhận.
        """
        if (event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_S) or event.key() == Qt.Key_F6:
            self.export_xml_hierarchy()
            return
        elif event.key() == Qt.Key_F7:
            self.open_adb_terminal()
            return
        elif event.key() == Qt.Key_Escape:
            if self.is_scanning:
                self.exit_scan_mode()
        elif event.key() == Qt.Key_F5:
            if self.is_scanning:
                self.enter_scan_mode()
        elif self.is_scanning and ((Qt.Key_0 <= event.key() <= Qt.Key_9) or (event.text().isdigit() and len(event.text()) == 1)):
            digit_char = event.text() if event.text().isdigit() else chr(event.key())

            # 1. Ưu tiên tìm trong phần tử đã chia lưới 4x3 (bàn phím ảo mô phỏng)
            for elem in self.elements:
                if elem.get("grid") and elem["grid"]["rows"] == 4 and elem["grid"]["cols"] == 3:
                    key_map = {
                        "1": (0, 0), "2": (0, 1), "3": (0, 2),
                        "4": (1, 0), "5": (1, 1), "6": (1, 2),
                        "7": (2, 0), "8": (2, 1), "9": (2, 2),
                        "0": (3, 1),
                    }
                    if digit_char in key_map:
                        r, c = key_map[digit_char]
                        cw_phone = elem["width"] / 3
                        ch_phone = elem["height"] / 4
                        px = int(elem["x1"] + (c + 0.5) * cw_phone)
                        py = int(elem["y1"] + (r + 0.5) * ch_phone)
                        self.lbl_status.setText(f"✅ Bàn phím ảo: [{digit_char}]")
                        self.click_effect_cell = (elem, r, c)
                        self.click_effect_timer.start(180)
                        self.update()
                        if self.device or self.demo_mode:
                            Thread(target=self._send_click_async, args=(px, py), daemon=True).start()
                        return

            # 2. Nếu không có lưới, tìm nút số trong các node XML thật
            for elem in self.elements:
                short_id = elem.get("short_id", "").lower()
                desc = elem.get("desc", "").strip()
                text = elem.get("text", "").strip()
                if short_id == f"key{digit_char}" or desc == digit_char or text == digit_char:
                    self.lbl_status.setText(f"✅ Phím số: [{digit_char}]")
                    self.click_effect_box = elem
                    self.click_effect_timer.start(180)
                    self.update()
                    if self.device or self.demo_mode:
                        Thread(target=self._send_click_async, args=(elem["center_x"], elem["center_y"]), daemon=True).start()
                    break
        elif self.is_scanning and event.key() == Qt.Key_Backspace:
            # 1. Ưu tiên nút Xóa trong lưới 4x3
            for elem in self.elements:
                if elem.get("grid") and elem["grid"]["rows"] == 4 and elem["grid"]["cols"] == 3:
                    r, c = 3, 2  # Phím ⌫
                    cw_phone = elem["width"] / 3
                    ch_phone = elem["height"] / 4
                    px = int(elem["x1"] + (c + 0.5) * cw_phone)
                    py = int(elem["y1"] + (r + 0.5) * ch_phone)
                    self.lbl_status.setText("✅ Bàn phím ảo: [⌫ Xóa]")
                    self.click_effect_cell = (elem, r, c)
                    self.click_effect_timer.start(180)
                    self.update()
                    if self.device or self.demo_mode:
                        Thread(target=self._send_click_async, args=(px, py), daemon=True).start()
                    return

            # 2. Tìm nút Xóa trong XML thật
            for elem in self.elements:
                short_id = elem.get("short_id", "").lower()
                desc = elem.get("desc", "").lower()
                if any(k in short_id or k in desc for k in ["delete", "del", "xóa", "backspace"]):
                    self.lbl_status.setText(f"✅ Đã bấm: {elem['label']}")
                    self.click_effect_box = elem
                    self.click_effect_timer.start(180)
                    self.update()
                    if self.device or self.demo_mode:
                        Thread(target=self._send_click_async, args=(elem["center_x"], elem["center_y"]), daemon=True).start()
                    break
        elif self.is_scanning and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            for elem in self.elements:
                short_id = elem.get("short_id", "").lower()
                desc = elem.get("desc", "").lower()
                text = elem.get("text", "").lower()
                if any(k in short_id or k in desc or k in text for k in ["enter", "ok", "xác nhận", "confirm"]):
                    self.lbl_status.setText(f"✅ Đã bấm: {elem['label']}")
                    self.click_effect_box = elem
                    self.click_effect_timer.start(180)
                    self.update()
                    if self.device or self.demo_mode:
                        Thread(target=self._send_click_async, args=(elem["center_x"], elem["center_y"]), daemon=True).start()
                    break
        else:
            super().keyPressEvent(event)


# ===========================================================================
# CỬA SỔ GIẢ LẬP QTSCRCPY (CHO PHÉP TEST NHẬP PIN & CHIA LƯỚI DEMO)
# ===========================================================================

class MockQtScrcpyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phone-R3CT104B80P")
        self.resize(380, 800)
        self.setStyleSheet("""
            QWidget {
                background-color: #0B0F19;
                color: #FFFFFF;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 30, 25, 30)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("📱 MÔ PHỎNG PHONE-R3CT104B80P", self)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38BDF8; margin-bottom: 12px;")
        layout.addWidget(title)

        desc = QLabel(
            "🔒 Màn hình ShopeePay / Bàn phím bảo mật.\n\n"
            "👉 Bấm [🔍 Soi XML] để hiển thị khung.\n"
            "👉 Chuột phải vào ô 'Bàn phím bảo mật ShopeePay' để chia lưới 4×3 kéo thả như Word!\n"
            "👉 Bấm liên tiếp các số để nhập PIN.\n"
            "👉 Bấm [⏻ Thoát ứng dụng] ngay bên dưới để đóng hoàn toàn.",
            self
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("font-size: 12px; color: #94A3B8; line-height: 1.6;")
        layout.addWidget(desc)


# ===========================================================================
# ĐIỂM KHỞI CHẠY CHƯƠNG TRÌNH (MAIN ENTRY POINT)
# ===========================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="QtScrcpy Transparent Overlay Bypass FLAG_SECURE")
    parser.add_argument("--title", default="QtScrcpy", help="Từ khóa tiêu đề hoặc thiết bị (Mặc định: QtScrcpy)")
    parser.add_argument("--serial", default=None, help="Serial thiết bị ADB (Mặc định: tự động quét)")
    parser.add_argument("--demo", action="store_true", help="Chạy chế độ thử nghiệm (mô phỏng nhập mã PIN)")
    args = parser.parse_args()

    print("==================================================================")
    print(" 🚀 KHỞI ĐỘNG OVERLAY TRỢ LÝ QTSCRCPY (FLAG_SECURE BYPASS) ")
    print("==================================================================")
    print(f" * Backend GUI: {QT_BACKEND}")
    print(f" * Windows API: {'win32gui' if HAVE_WIN32GUI else 'ctypes native'}")
    print(f" * Đường dẫn ADB: {REAL_ADB_PATH or 'Mặc định trên PATH'}")
    print(f" * Thiết bị ADB: {args.serial or 'Tự động quét thiết bị kết nối'}")
    print(f" * Chế độ Demo: {'BẬT (Mô phỏng nhập PIN 6 số)' if args.demo else 'TẮT (Chế độ thật qua ADB)'}")
    print(" * Mẹo: Bấm chuột phải vào bất kỳ khung nào để chia lưới bàn phím!")
    print("==================================================================")
    app = QApplication(sys.argv)

    mock_win = None
    if args.demo:
        mock_win = MockQtScrcpyWindow()
        mock_win.show()

    overlay = TransparentOverlay(target_title=args.title, device_serial=args.serial, demo_mode=args.demo)
    overlay.show()

    sys.exit(app.exec_() if hasattr(app, "exec_") else app.exec())


if __name__ == "__main__":
    main()
