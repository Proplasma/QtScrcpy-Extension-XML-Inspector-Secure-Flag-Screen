"""
========================================================================================
DỰ ÁN: TRỢ LÝ OVERLAY TRONG SUỐT CHO QTSCRCPY (BYPASS FLAG_SECURE QUA UIAUTOMATOR2)
========================================================================================
Mô tả:
  - Script tạo một cửa sổ Overlay trong suốt (PyQt5 / PySide6) tự động bám dính (track)
    vào cửa sổ QtScrcpy trên Windows.
  - Khi mở các ứng dụng bảo mật (ngân hàng, ví điện tử) có cờ FLAG_SECURE, màn hình
    QtScrcpy bị đen (luồng video bị cắt bởi hệ điều hành Android).
  - Script cho phép bấm "🔍 Soi XML" để quét cây giao diện từ uiautomator2 qua ADB,
    tính toán tỉ lệ khung hình (Aspect Ratio & Scaling) và vẽ đè các Bounding Box đỏ
    lên màn hình đen của PC.
  - Khi click vào phần tử trên PC, script tự động dịch ngược tọa độ và gọi d.click()
    trên điện thoại thật.
========================================================================================
"""

import sys
import os
import io

# Tự động chuyển mã hóa console sang UTF-8 trên Windows để in tiếng Việt không lỗi charmap
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

import re
import time
import xml.etree.ElementTree as ET
from threading import Thread

# ---------------------------------------------------------------------------
# 1. HỖ TRỢ ĐA NỀN TẢNG QT (Tương thích cả PyQt5 và PySide6)
# ---------------------------------------------------------------------------
try:
    from PyQt5.QtWidgets import (
        QApplication, QWidget, QPushButton, QLabel, QHBoxLayout, QVBoxLayout,
        QGraphicsDropShadowEffect, QFrame
    )
    from PyQt5.QtCore import Qt, QTimer, QRect, QPoint, pyqtSignal as Signal, QThread
    from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush, QRegion, QCursor
    QT_BACKEND = "PyQt5"
except ImportError:
    from PySide6.QtWidgets import (
        QApplication, QWidget, QPushButton, QLabel, QHBoxLayout, QVBoxLayout,
        QGraphicsDropShadowEffect, QFrame
    )
    from PySide6.QtCore import Qt, QTimer, QRect, QPoint, Signal, QThread
    from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush, QRegion, QCursor
    QT_BACKEND = "PySide6"

# ---------------------------------------------------------------------------
# 2. HỖ TRỢ WINDOWS API (win32gui hoặc ctypes dự phòng không cần cài pywin32)
# ---------------------------------------------------------------------------
try:
    import win32gui
    import win32con
    HAVE_WIN32GUI = True
except ImportError:
    HAVE_WIN32GUI = False

import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
# 3. KẾT NỐI UIAUTOMATOR2
# ---------------------------------------------------------------------------
try:
    import uiautomator2 as u2
    HAVE_U2 = True
except ImportError:
    HAVE_U2 = False


# ===========================================================================
# HÀM BỔ TRỢ: TÌM KIẾM VÀ ĐO ĐẠC CỬA SỔ WINDOWS (WINDOW TRACKING ENGINE)
# ===========================================================================

def find_target_window(title_keyword="QtScrcpy"):
    """
    Tìm handle (HWND) của cửa sổ có tiêu đề chứa title_keyword.
    Hỗ trợ cả win32gui và ctypes dự phòng.
    """
    found_hwnds = []

    if HAVE_WIN32GUI:
        def enum_callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and title_keyword.lower() in title.lower():
                    found_hwnds.append(hwnd)
            return True
        win32gui.EnumWindows(enum_callback, None)
    else:
        # Fallback dùng ctypes nếu chưa cài pywin32
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_callback_ctypes(hwnd, lparam):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                    if title_keyword.lower() in buff.value.lower():
                        found_hwnds.append(hwnd)
            return True
        cb = WNDENUMPROC(enum_callback_ctypes)
        ctypes.windll.user32.EnumWindows(cb, 0)

    return found_hwnds[0] if found_hwnds else None


def get_client_rect_screen(hwnd):
    """
    Lấy tọa độ tuyệt đối trên màn hình PC của vùng hiển thị nội dung (Client Area),
    loại bỏ thanh tiêu đề và đường viền ngoài của cửa sổ QtScrcpy.
    Trả về: (x, y, width, height)
    """
    if not hwnd:
        return None

    # Kiểm tra xem cửa sổ có bị Minimize không
    if HAVE_WIN32GUI:
        if win32gui.IsIconic(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return None
        client_rect = win32gui.GetClientRect(hwnd)
        pt = win32gui.ClientToScreen(hwnd, (0, 0))
        return pt[0], pt[1], client_rect[2], client_rect[3]
    else:
        if ctypes.windll.user32.IsIconic(hwnd) or not ctypes.windll.user32.IsWindowVisible(hwnd):
            return None
        rect = wintypes.RECT()
        ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
        pt = wintypes.POINT(0, 0)
        ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
        return pt.x, pt.y, rect.right, rect.bottom


# ===========================================================================
# LUỒNG PHỤ (QThread): QUÉT VÀ PHÂN TÍCH XML TRÁNH TREO ĐỠ GUI
# ===========================================================================

class XMLScannerWorker(QThread):
    """
    Worker Thread chạy ngầm:
    Gọi dump_hierarchy() qua uiautomator2 và parse dữ liệu XML,
    giúp giao diện PyQt5 luôn mượt mà 60 FPS, không bao giờ bị đơ (Not Responding).
    """
    scan_success = Signal(list, int, int)  # elements, phone_w, phone_h
    scan_failed = Signal(str)

    def __init__(self, device, demo=False):
        super().__init__()
        self.device = device
        self.demo = demo

    def run(self):
        try:
            if self.demo:
                # Mô phỏng quét XML của app Ngân hàng có FLAG_SECURE
                time.sleep(0.3)  # Giả lập độ trễ mạng ADB
                phone_w, phone_h = 1080, 2400
                xml_text = """<hierarchy rotation="0">
                  <node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">
                    <node class="android.widget.TextView" text="Ngân Hàng Số SmartBanking" bounds="[0,80][1080,220]" />
                    <node class="android.widget.TextView" text="Số dư khả dụng: 15,250,000 đ" bounds="[60,260][1020,440]" />
                    <node class="android.widget.Button" text="Chuyển tiền" bounds="[60,500][490,680]" clickable="true" resource-id="com.bank:id/btn_transfer" />
                    <node class="android.widget.Button" text="Nạp tiền ĐT" bounds="[590,500][1020,680]" clickable="true" resource-id="com.bank:id/btn_topup" />
                    <node class="android.widget.Button" text="Quét QR Code" bounds="[60,730][490,910]" clickable="true" resource-id="com.bank:id/btn_qr" />
                    <node class="android.widget.Button" text="Lịch sử giao dịch" bounds="[590,730][1020,910]" clickable="true" resource-id="com.bank:id/btn_history" />
                    <node class="android.widget.EditText" text="Nhập số tài khoản thụ hưởng" bounds="[60,1050][1020,1220]" clickable="true" resource-id="com.bank:id/edt_account" />
                    <node class="android.widget.EditText" text="Nhập số tiền cần chuyển" bounds="[60,1280][1020,1450]" clickable="true" resource-id="com.bank:id/edt_amount" />
                    <node class="android.widget.Button" text="TIẾP TỤC" bounds="[60,1600][1020,1760]" clickable="true" resource-id="com.bank:id/btn_continue" />
                    <node class="android.widget.Button" text="XÁC NHẬN CHUYỂN KHOẢN" bounds="[60,1820][1020,1980]" clickable="true" resource-id="com.bank:id/btn_confirm" />
                  </node>
                </hierarchy>"""
            else:
                if not self.device:
                    self.scan_failed.emit("Chưa kết nối được thiết bị Android qua ADB!")
                    return

                # 1. Lấy độ phân giải thực của điện thoại (VD: 1080 x 2400)
                window_size = self.device.window_size()
                phone_w, phone_h = window_size[0], window_size[1]

                # 2. Dump toàn bộ cây giao diện dạng chuỗi XML qua uiautomator2
                # dump_hierarchy() là phương thức nhanh nhất, trả về cây Node đầy đủ
                xml_text = self.device.dump_hierarchy()
                if not xml_text:
                    self.scan_failed.emit("Không lấy được dữ liệu XML từ điện thoại!")
                    return

            # 3. Phân tích cú pháp XML
            root = ET.fromstring(xml_text.encode("utf-8"))
            elements = []

            for node in root.iter():
                bounds_str = node.attrib.get("bounds", "")
                if not bounds_str:
                    continue

                # Phân tích bounds: dạng "[x1,y1][x2,y2]"
                coords = re.findall(r"\d+", bounds_str)
                if len(coords) < 4:
                    continue

                x1, y1, x2, y2 = map(int, coords[:4])
                bw = x2 - x1
                bh = y2 - y1

                # Bỏ qua các phần tử kích thước 0 hoặc âm
                if bw <= 0 or bh <= 0:
                    continue

                clickable = node.attrib.get("clickable", "false").lower() == "true"
                text = node.attrib.get("text", "").strip()
                desc = node.attrib.get("content-desc", "").strip()
                res_id = node.attrib.get("resource-id", "").strip()
                cls_name = node.attrib.get("class", "").strip()

                # Chỉ giữ lại phần tử có thể tương tác hoặc có thông tin hiển thị
                area = bw * bh
                is_full_screen = (bw >= phone_w and bh >= phone_h)

                if (clickable or text or desc or res_id) and not (is_full_screen and not text and not desc):
                    # Rút gọn resource-id để hiển thị gọn gàng (VD: com.bank.app:id/btn_login -> btn_login)
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
                        "label": display_label,
                        "class": cls_name
                    })

            self.scan_success.emit(elements, phone_w, phone_h)

        except Exception as e:
            self.scan_failed.emit(f"Lỗi khi quét XML: {str(e)}")


# ===========================================================================
# LỚP GIAO DIỆN CHÍNH: OVERLAY TRONG SUỐT (TRANSPARENT OVERLAY)
# ===========================================================================

class TransparentOverlay(QWidget):
    def __init__(self, target_title="QtScrcpy", device_serial=None, demo_mode=False):
        super().__init__()
        self.target_title = target_title
        self.device_serial = device_serial
        self.demo_mode = demo_mode

        # Trạng thái ứng dụng
        self.is_scanning = False
        self.elements = []
        self.phone_width = 1080
        self.phone_height = 2400
        self.status_message = "Sẵn sàng"
        self.hovered_element = None

        # Biến tính toán Scale (Lưu lại để tái sử dụng khi click chuột)
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.video_w = 0.0
        self.video_h = 0.0

        # Khởi tạo kết nối Android & Cửa sổ
        self.device = None
        self.init_android_device()
        self.init_window_flags()
        self.init_ui_components()

        # Timer bám đuôi cửa sổ QtScrcpy (Tracking Timer ~ 50ms/lần)
        self.track_timer = QTimer(self)
        self.track_timer.timeout.connect(self.track_qtscrcpy)
        self.track_timer.start(50)

        # Worker quét ngầm
        self.scanner_worker = None

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
            if self.device_serial:
                self.device = u2.connect(self.device_serial)
            else:
                self.device = u2.connect()  # Tự động bắt máy đầu tiên qua ADB
            
            # Lấy trước kích thước màn hình
            w, h = self.device.window_size()
            self.phone_width = w
            self.phone_height = h
            self.status_message = f"Đã kết nối điện thoại: {w}x{h}"
            print(f"[ADB] Kết nối thành công! Độ phân giải điện thoại: {w}x{h}")
        except Exception as e:
            self.status_message = f"Chưa kết nối ADB: {str(e)}"
            print(f"[ADB LỖI] {self.status_message}")

    def init_window_flags(self):
        """Thiết lập các thuộc tính cửa sổ không viền, trong suốt, luôn trên cùng."""
        # 1. FramelessWindowHint: Bỏ toàn bộ viền và thanh tiêu đề của Windows
        # 2. WindowStaysOnTopHint: Luôn nằm đè lên trên các cửa sổ khác
        # 3. Tool: Không hiển thị icon riêng rẽ trên Taskbar
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )

        # 4. WA_TranslucentBackground: Nền trong suốt 100%
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Bật Mouse Tracking để bắt hiệu ứng rê chuột (Hover) qua các Bounding Box
        self.setMouseTracking(True)

    def init_ui_components(self):
        """Tạo các nút bấm điều khiển (Control Bar)."""
        # Layout tổng
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.addStretch()  # Đẩy thanh công cụ xuống đáy

        # Container chứa các nút bấm ở đáy
        self.bottom_bar = QFrame(self)
        self.bottom_bar.setObjectName("BottomBar")
        self.bottom_bar.setStyleSheet("""
            #BottomBar {
                background-color: rgba(20, 24, 30, 220);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 8px;
            }
            QPushButton {
                background-color: #007ACC;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0098FF;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
            #BtnCancel {
                background-color: #D32F2F;
            }
            #BtnCancel:hover {
                background-color: #F44336;
            }
            #StatusLabel {
                color: #B0BEC5;
                font-size: 11px;
                margin-left: 8px;
            }
        """)

        bar_layout = QHBoxLayout(self.bottom_bar)
        bar_layout.setContentsMargins(8, 6, 8, 6)
        bar_layout.setSpacing(8)

        # Nút kích hoạt chính: "🔍 Soi XML"
        self.btn_scan = QPushButton("🔍 Soi XML", self.bottom_bar)
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        self.btn_scan.clicked.connect(self.toggle_scan_mode)
        bar_layout.addWidget(self.btn_scan)

        # Nút Hủy / Đóng quét
        self.btn_cancel = QPushButton("❌ Tắt XML", self.bottom_bar)
        self.btn_cancel.setObjectName("BtnCancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.exit_scan_mode)
        self.btn_cancel.setVisible(False)
        bar_layout.addWidget(self.btn_cancel)

        # Label hiển thị trạng thái
        self.lbl_status = QLabel(self.status_message, self.bottom_bar)
        self.lbl_status.setObjectName("StatusLabel")
        bar_layout.addWidget(self.lbl_status)
        bar_layout.addStretch()

        self.main_layout.addWidget(self.bottom_bar)

        # Áp dụng hiệu ứng bóng đổ cho thanh công cụ
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 2)
        self.bottom_bar.setGraphicsEffect(shadow)

        # Ban đầu ở chế độ Xuyên Thấu (Không chặn click của QtScrcpy)
        self.update_click_through_mask()

    # =======================================================================
    # 1. TÍNH NĂNG KẺ BÁM ĐUÔI (WINDOW TRACKING LOGIC)
    # =======================================================================

    def track_qtscrcpy(self):
        """
        Được gọi liên tục mỗi 50ms bởi QTimer.
        Tìm kiếm cửa sổ QtScrcpy trên Windows và đồng bộ vị trí, kích thước
        của Overlay khớp từng pixel với vùng hiển thị video của QtScrcpy.
        """
        hwnd = find_target_window(self.target_title)

        if not hwnd:
            # Không tìm thấy cửa sổ QtScrcpy -> Tạm thời ẩn Overlay
            if self.isVisible():
                self.hide()
            return

        rect = get_client_rect_screen(hwnd)
        if not rect:
            # Cửa sổ bị thu nhỏ (Minimize) -> Ẩn Overlay
            if self.isVisible():
                self.hide()
            return

        target_x, target_y, target_w, target_h = rect

        # Nếu vị trí hoặc kích thước thay đổi -> Cập nhật setGeometry
        current_geo = self.geometry()
        if (current_geo.x() != target_x or current_geo.y() != target_y or
                current_geo.width() != target_w or current_geo.height() != target_h):
            self.setGeometry(target_x, target_y, target_w, target_h)
            self.update_click_through_mask()

        if not self.isVisible():
            self.show()

    # =======================================================================
    # CƠ CHẾ CLICK-THROUGH (XUYÊN THẤU CHUỘT)
    # =======================================================================

    def update_click_through_mask(self):
        """
        Kỹ thuật Masking vùng chuột:
        - Khi is_scanning = False: Dùng setMask() giới hạn vùng bấm chuột CHỈ NẰM Ở
          thanh bottom_bar. Toàn bộ vùng màn hình còn lại của QtScrcpy KHÔNG bị chặn,
          người dùng vẫn lướt chạm, gõ phím trên QtScrcpy bình thường!
        - Khi is_scanning = True: Dùng clearMask() để toàn bộ cửa sổ Overlay hứng
          sự kiện chuột, cho phép bấm chọn các Bounding Box XML.
        """
        if self.is_scanning:
            # Cho phép toàn màn hình nhận click
            self.clearMask()
        else:
            # Chỉ cho phép thanh Bottom Bar nhận click
            bar_geo = self.bottom_bar.geometry()
            if not bar_geo.isEmpty():
                self.setMask(QRegion(bar_geo))

    # =======================================================================
    # 2. XỬ LÝ NÚT BẤM & QUÉT GIAO DIỆN XML
    # =======================================================================

    def toggle_scan_mode(self):
        """Bật/tắt chế độ Soi XML."""
        if self.is_scanning:
            self.exit_scan_mode()
        else:
            self.enter_scan_mode()

    def enter_scan_mode(self):
        """Bật chế độ soi XML: Kích hoạt chặn click và gọi luồng quét uiautomator2."""
        self.is_scanning = True
        self.btn_scan.setText("🔄 Đang quét...")
        self.btn_scan.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.lbl_status.setText("Đang trích xuất cấu trúc giao diện từ điện thoại...")
        self.update_click_through_mask()
        self.update()

        # Tạo và chạy luồng quét ngầm
        self.scanner_worker = XMLScannerWorker(self.device, demo=self.demo_mode)
        self.scanner_worker.scan_success.connect(self.on_scan_success)
        self.scanner_worker.scan_failed.connect(self.on_scan_failed)
        self.scanner_worker.start()

    def exit_scan_mode(self):
        """Thoát chế độ soi XML, xóa các bounding box và trả lại quyền click cho QtScrcpy."""
        self.is_scanning = False
        self.elements = []
        self.hovered_element = None
        self.btn_scan.setText("🔍 Soi XML")
        self.btn_scan.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.lbl_status.setText("Đã tắt soi XML. QtScrcpy hoạt động bình thường.")
        self.update_click_through_mask()
        self.update()

    def on_scan_success(self, elements, phone_w, phone_h):
        """Callback khi quét XML thành công."""
        self.elements = elements
        self.phone_width = phone_w
        self.phone_height = phone_h

        self.btn_scan.setText("🔄 Quét lại")
        self.btn_scan.setEnabled(True)
        self.lbl_status.setText(f"Tìm thấy {len(elements)} phần tử. Bấm vào khung để gửi click!")
        self.update()

    def on_scan_failed(self, error_msg):
        """Callback khi quét XML thất bại."""
        self.btn_scan.setText("🔍 Soi XML")
        self.btn_scan.setEnabled(True)
        self.lbl_status.setText(f"❌ {error_msg}")
        self.update()

    # =======================================================================
    # 3. THUẬT TOÁN TÍNH TOÁN TỈ LỆ (SCALING MATH & ASPECT RATIO)
    # =======================================================================

    def calculate_scale_and_offsets(self):
        """
        ======================================================================
        GIẢI THÍCH CHI TIẾT THUẬT TOÁN SCALE TỌA ĐỘ:
        ======================================================================
        QtScrcpy luôn bảo toàn tỉ lệ khung hình (Aspect Ratio) của điện thoại
        khi người dùng phóng to/thu nhỏ cửa sổ trên PC. Do đó sẽ xuất hiện
        2 dải đen (Letterbox/Pillarbox):
          - Trường hợp 1 (Pillarbox): Cửa sổ PC bè hơn tỉ lệ điện thoại -> 2 dải đen ở Trái & Phải.
          - Trường hợp 2 (Letterbox): Cửa sổ PC dài hơn tỉ lệ điện thoại -> 2 dải đen ở Trên & Dưới.

        Công thức:
          1. aspect_phone = phone_w / phone_h
          2. aspect_pc    = pc_w / pc_h
          3. Nếu aspect_pc > aspect_phone:
               video_h = pc_h
               video_w = pc_h * aspect_phone
               offset_x = (pc_w - video_w) / 2
               offset_y = 0
               scale = video_h / phone_h
             Ngược lại:
               video_w = pc_w
               video_h = pc_w / aspect_phone
               offset_x = 0
               offset_y = (pc_h - video_h) / 2
               scale = video_w / phone_w

        Chuyển đổi Phone -> PC:
          pc_x = offset_x + phone_x * scale
          pc_y = offset_y + phone_y * scale
          pc_w = phone_w * scale
          pc_h = phone_h * scale

        Chuyển đổi ngược PC -> Phone (khi người dùng click chuột):
          phone_x = (click_pc_x - offset_x) / scale
          phone_y = (click_pc_y - offset_y) / scale
        ======================================================================
        """
        pc_w = self.width()
        pc_h = self.height()
        phone_w = self.phone_width
        phone_h = self.phone_height

        if phone_w <= 0 or phone_h <= 0 or pc_w <= 0 or pc_h <= 0:
            return 1.0, 0.0, 0.0, pc_w, pc_h

        aspect_phone = float(phone_w) / float(phone_h)
        aspect_pc = float(pc_w) / float(pc_h)

        if aspect_pc > aspect_phone:
            # Cửa sổ PC rộng hơn màn hình điện thoại -> Có 2 dải đen bên hông
            self.video_h = float(pc_h)
            self.video_w = float(pc_h) * aspect_phone
            self.offset_x = (pc_w - self.video_w) / 2.0
            self.offset_y = 0.0
            self.scale = self.video_h / float(phone_h)
        else:
            # Cửa sổ PC hẹp/cao hơn -> Có 2 dải đen trên và dưới
            self.video_w = float(pc_w)
            self.video_h = float(pc_w) / aspect_phone
            self.offset_x = 0.0
            self.offset_y = (pc_h - self.video_h) / 2.0
            self.scale = self.video_w / float(phone_w)

        return self.scale, self.offset_x, self.offset_y, self.video_w, self.video_h

    # =======================================================================
    # 4. VẼ GIAO DIỆN BOUNDING BOX (PAINT EVENT)
    # =======================================================================

    def paintEvent(self, event):
        """Vẽ lớp phủ sương mờ và các khung Bounding Box lên trên QtScrcpy."""
        if not self.is_scanning:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Tính toán tỉ lệ Scale hiện tại
        scale, off_x, off_y, vid_w, vid_h = self.calculate_scale_and_offsets()

        # 2. Phủ lớp nền đen mờ (rgba 0, 0, 0, 130) lên vùng hiển thị video
        video_rect = QRect(int(off_x), int(off_y), int(vid_w), int(vid_h))
        painter.fillRect(video_rect, QColor(0, 0, 0, 130))

        # 3. Vẽ các Bounding Box từ dữ liệu XML
        # Sắp xếp vẽ các box to trước, box nhỏ đè lên trên
        sorted_elements = sorted(self.elements, key=lambda e: e["area"], reverse=True)

        font_label = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(font_label)

        for elem in sorted_elements:
            # Tính toán tọa độ hiển thị trên PC
            box_x = int(off_x + elem["x1"] * scale)
            box_y = int(off_y + elem["y1"] * scale)
            box_w = int(elem["width"] * scale)
            box_h = int(elem["height"] * scale)
            rect = QRect(box_x, box_y, box_w, box_h)
            elem["pc_rect"] = rect  # Lưu lại để phục vụ bắt sự kiện click

            is_hovered = (elem == self.hovered_element)

            # Thiết lập màu viền:
            # - Đang hover chuột: Viền Xanh Ngọc (Cyan) sáng rực
            # - Có thể click: Viền Đỏ tươi
            # - Chỉ xem (text không clickable): Viền Vàng cam nhạt
            if is_hovered:
                pen = QPen(QColor(0, 255, 200, 255), 3)
                painter.setPen(pen)
                painter.setBrush(QColor(0, 255, 200, 45))  # Highlight mờ bên trong
            elif elem["clickable"]:
                pen = QPen(QColor(255, 60, 60, 220), 2)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
            else:
                pen = QPen(QColor(255, 180, 0, 150), 1, Qt.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)

            painter.drawRect(rect)

            # Vẽ nhãn Text (màu vàng) trên nền đen nhỏ ở góc trên box
            label_text = elem["label"]
            if label_text and box_w > 20 and box_h > 12:
                # Cắt bớt nếu chữ quá dài
                if len(label_text) > 25:
                    label_text = label_text[:22] + "..."

                # Đo kích thước chữ để vẽ nền đen làm nổi bật text
                metrics = painter.fontMetrics()
                text_w = metrics.horizontalAdvance(label_text) + 6
                text_h = metrics.height() + 2

                tag_x = box_x + 2
                tag_y = max(box_y - text_h - 2, int(off_y) + 2) if box_y < int(off_y) + text_h else box_y + 2
                tag_rect = QRect(tag_x, tag_y, text_w, text_h)

                # Nền đen cho chữ
                painter.fillRect(tag_rect, QColor(20, 20, 20, 200))

                # Chữ màu vàng rực
                painter.setPen(QColor(255, 235, 59))
                painter.drawText(tag_rect, Qt.AlignCenter, label_text)

        painter.end()

    # =======================================================================
    # 5. ĐIỀU HƯỚNG CLICK CHUỘT: PC -> ĐIỆN THOẠI (REDIRECT CLICKS)
    # =======================================================================

    def mouseMoveEvent(self, event):
        """Xử lý hiệu ứng hover chuột qua các Bounding Box."""
        if not self.is_scanning:
            return

        mouse_pos = event.pos()
        old_hover = self.hovered_element
        self.hovered_element = None

        # Tìm box nhỏ nhất (ưu tiên phần tử con) mà chuột đang nằm bên trong
        smallest_area = float("inf")
        for elem in self.elements:
            pc_rect = elem.get("pc_rect")
            if pc_rect and pc_rect.contains(mouse_pos):
                if elem["area"] < smallest_area:
                    smallest_area = elem["area"]
                    self.hovered_element = elem

        if old_hover != self.hovered_element:
            self.update()

    def mousePressEvent(self, event):
        """
        Bắt sự kiện click chuột trái trên PC, tìm kiếm phần tử và gửi
        lệnh d.click() xuống điện thoại qua uiautomator2.
        """
        if not self.is_scanning:
            return

        # Nếu người dùng click vào thanh công cụ ở đáy -> Không làm gì (để nút bấm tự xử lý)
        if self.bottom_bar.geometry().contains(event.pos()):
            super().mousePressEvent(event)
            return

        if event.button() == Qt.LeftButton:
            click_pos = event.pos()
            scale, off_x, off_y, vid_w, vid_h = self.calculate_scale_and_offsets()

            # 1. Tìm phần tử nhỏ nhất (leaf element) được click trúng
            target_elem = None
            smallest_area = float("inf")
            for elem in self.elements:
                pc_rect = elem.get("pc_rect")
                if pc_rect and pc_rect.contains(click_pos):
                    if elem["area"] < smallest_area:
                        smallest_area = elem["area"]
                        target_elem = elem

            # 2. Xác định tọa độ thực trên điện thoại cần click
            if target_elem:
                phone_click_x = target_elem["center_x"]
                phone_click_y = target_elem["center_y"]
                label_info = f"'{target_elem['label']}' tại ({phone_click_x}, {phone_click_y})"
            else:
                # Nếu click vào khoảng trống trong video -> Dịch ngược tọa độ PC -> Phone
                phone_click_x = int((click_pos.x() - off_x) / scale)
                phone_click_y = int((click_pos.y() - off_y) / scale)
                phone_click_x = max(0, min(phone_click_x, self.phone_width - 1))
                phone_click_y = max(0, min(phone_click_y, self.phone_height - 1))
                label_info = f"tọa độ tự do ({phone_click_x}, {phone_click_y})"

            print(f"[CLICK] Đang gửi click xuống điện thoại: {label_info}")
            self.lbl_status.setText(f"Đã click: {label_info}")

            # 3. Gửi lệnh click qua uiautomator2 trong luồng riêng để tránh giật lag
            if self.device or self.demo_mode:
                Thread(target=self._send_click_async, args=(phone_click_x, phone_click_y), daemon=True).start()

            # 4. Tự động tắt giao diện soi XML sau khi click (như yêu cầu trong SRS)
            self.exit_scan_mode()

    def _send_click_async(self, x, y):
        """Thực thi d.click(x, y) trên luồng background."""
        if self.demo_mode:
            print(f"[DEMO ADB] Giả lập click thành công tại ({x}, {y}) trên màn hình điện thoại!")
            return

        try:
            self.device.click(x, y)
            print(f"[ADB] Click thành công tại ({x}, {y})")
        except Exception as e:
            print(f"[ADB LỖI] Click thất bại: {str(e)}")

    def keyPressEvent(self, event):
        """Phím tắt: Bấm ESC để đóng chế độ Soi XML."""
        if event.key() == Qt.Key_Escape and self.is_scanning:
            self.exit_scan_mode()
        else:
            super().keyPressEvent(event)


# ===========================================================================
# CỬA SỔ GIẢ LẬP QTSCRCPY (CHO PHÉP TEST THỬ NGHIỆM TRỰC TIẾP KHÔNG CẦN MÁY THẬT)
# ===========================================================================

class MockQtScrcpyWindow(QWidget):
    """
    Cửa sổ mô phỏng QtScrcpy để người dùng có thể chạy thử nghiệm
    ngay lập tức mà không cần mở QtScrcpy thật hay cắm điện thoại.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QtScrcpy - [Demo Device 1080x2400]")
        self.resize(450, 950)
        self.setStyleSheet("""
            QWidget {
                background-color: #0A0E17;
                color: #FFFFFF;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 40, 30, 40)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("📱 MÔ PHỎNG QTSCRCPY", self)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00E676; margin-bottom: 10px;")
        layout.addWidget(title)

        desc = QLabel(
            "⚠️ Màn hình này đang bị ĐEN hoàn toàn do app bật cờ FLAG_SECURE.\n\n"
            "👉 Hãy bấm vào nút [🔍 Soi XML] trên thanh công cụ Overlay\n"
            "để quét các Bounding Box màu đỏ và gửi click thử nghiệm!",
            self
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("font-size: 13px; color: #90A4AE; line-height: 1.6;")
        layout.addWidget(desc)


# ===========================================================================
# ĐIỂM KHỞI CHẠY CHƯƠNG TRÌNH (MAIN ENTRY POINT)
# ===========================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="QtScrcpy Transparent Overlay Bypass FLAG_SECURE")
    parser.add_argument("--title", default="QtScrcpy", help="Từ khóa tiêu đề cửa sổ cần bám (Mặc định: QtScrcpy)")
    parser.add_argument("--serial", default=None, help="Serial thiết bị ADB (nếu cắm nhiều máy)")
    parser.add_argument("--demo", action="store_true", help="Chạy chế độ thử nghiệm (mô phỏng cửa sổ QtScrcpy và app ngân hàng)")
    args = parser.parse_args()

    print("==================================================================")
    print(" 🚀 KHỞI ĐỘNG OVERLAY TRỢ LÝ QTSCRCPY (FLAG_SECURE BYPASS) ")
    print("==================================================================")
    print(f" * Backend GUI: {QT_BACKEND}")
    print(f" * Windows API: {'win32gui' if HAVE_WIN32GUI else 'ctypes fallback'}")
    print(f" * Đang theo dõi cửa sổ chứa từ khóa: '{args.title}'")
    print(f" * Chế độ Demo: {'BẬT (Mô phỏng app ngân hàng)' if args.demo else 'TẮT (Chế độ thật qua ADB)'}")
    print(" * Mẹo: Bấm '🔍 Soi XML' để quét cây giao diện.")
    print(" * Bấm phím ESC để hủy chế độ soi XML bất kỳ lúc nào.")
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
