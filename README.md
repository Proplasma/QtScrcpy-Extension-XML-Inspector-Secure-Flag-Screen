# ScrcpySecureOverlay (QtScrcpy XML Reader & Interactive Overlay)

ScrcpySecureOverlay là một công cụ mã nguồn mở chạy trên nền tảng Windows, cung cấp lớp phủ tương tác trong suốt (transparent interactive overlay) bám dính tự động theo cửa sổ truyền hình ảnh của QtScrcpy hoặc Scrcpy. 

Công cụ giải quyết triệt để hạn chế màn hình đen do cơ chế bảo mật `FLAG_SECURE` của hệ điều hành Android (thường gặp trên các ứng dụng ngân hàng, ví điện tử, màn hình nhập mã PIN, mật khẩu và OTP), cho phép người dùng quan sát cấu trúc giao diện, nhập liệu liên tục và trích xuất dữ liệu XML phân cấp một cách trực quan.

---

## Mục lục

1. Giới thiệu tổng quan
2. Tính năng cốt lõi
3. Kiến trúc hoạt động
4. Yêu cầu hệ thống
5. Hướng dẫn cài đặt
6. Hướng dẫn sử dụng
7. Bảng phím tắt điều khiển
8. Cơ chế trích xuất dữ liệu XML
9. Cơ chế cô lập lệnh ADB (Target Device Isolation)
10. Cấu hình tham số dòng lệnh
11. Xử lý sự cố thường gặp (Troubleshooting)
12. Giấy phép sử dụng

---

## 1. Giới thiệu tổng quan

Khi điều khiển điện thoại Android từ xa qua giao thức truyền màn hình (như Scrcpy hoặc QtScrcpy), các ứng dụng có cài đặt cờ `WindowManager.LayoutParams.FLAG_SECURE` sẽ chặn luồng xuất video, khiến cửa sổ máy tính chỉ nhận được một màn hình đen hoặc khung hình trống.

ScrcpySecureOverlay giải quyết bài toán này mà không yêu cầu can thiệp sâu vào firmware hệ điều hành (không cần root thiết bị). Ứng dụng đọc trực tiếp cấu trúc cây giao diện (UI Hierarchy) thông qua dịch vụ trợ năng và giao thức ADB, sau đó dựng lại lớp phủ đồ họa chuẩn xác đến từng pixel đè ngay trên cửa sổ QtScrcpy. Người dùng có thể quan sát vị trí các nút, bấm trực tiếp bằng chuột, gõ phím số trên bàn phím máy tính hoặc chia lưới mô phỏng bàn phím ảo bảo mật.



<img width="984" height="605" alt="image" src="https://github.com/user-attachments/assets/4c3005eb-404b-4c10-8c03-a886dbabcf67" />

Hình 1: Giao diện tổng quan lớp phủ đè lên cửa sổ QtScrcpy khi soi XML màn hình bảo mật

---

## 2. Tính năng cốt lõi

### Bám dính cửa sổ thông minh (Sticky Window Tracking)
- Tự động nhận diện cửa sổ phát hình ảnh của QtScrcpy thông qua tiêu đề dạng `Phone-<serial>` (ví dụ: `Phone-R3CT104B80P`).
- Lọc bỏ hoàn toàn các cửa sổ không liên quan như trình duyệt web (Chrome, Edge, Thorium), trình quản lý tệp (Windows Explorer) hoặc thanh công cụ dọc phụ.
- Liên tục đồng bộ vị trí, kích thước và trạng thái thu nhỏ/phóng to của cửa sổ mục tiêu với tần suất 50ms, đảm bảo lớp phủ luôn bám khít tuyệt đối.

### Hiển thị trực quan và phân loại phần tử
- Khung phần tử thông thường (Button, TextView, View): Hiển thị viền màu Cyan (xanh lơ sáng).
- Khu vực ô nhập liệu (EditText, ô PIN, mật khẩu, trường tìm kiếm): Hiển thị màu Tím Neon (Purple) kèm biểu tượng con trỏ chữ (I-Beam Cursor) nhấp nháy chậm với chu kỳ 700ms.
- Nhãn định danh (Badge Tag): Hiển thị tên text, content-desc hoặc resource-id ngắn gọn phía trên mỗi khung.

### Duy trì tương tác liên tục (Manual Toggle Mode)
- Khắc phục nhược điểm tự đóng sau mỗi lần click của các công cụ soi XML thông thường.
- Lớp phủ giữ nguyên trạng thái mở khi người dùng click chuột liên tiếp, cho phép nhập mượt mà mã PIN 6 số hoặc thực hiện chuỗi thao tác phức tạp mà không cần quét lại giao diện sau mỗi lần nhấn.
- Chỉ thoát chế độ hiển thị khi người dùng chủ động nhấn nút hoặc phím tắt ESC.

### Bộ tạo lưới bàn phím ảo kiểu Word (Word-Style Table Grid Creator)
- Đối với các bàn phím bảo mật vẽ bằng Canvas tùy biến (không thể trích xuất từng nút số riêng lẻ qua XML), người dùng chỉ cần click chuột phải vào khung bàn phím tổng để mở bảng chọn lưới.
- Giao diện kéo thả chọn số hàng và số cột trực quan tương tự chức năng chèn bảng của Microsoft Word.
- Hỗ trợ cấu hình nhanh chuẩn bàn phím số 4 hàng x 3 cột (phím 1 đến 9, phím 0 và phím Xóa). Click vào từng ô hoặc bấm phím số từ máy tính sẽ tự động tính toán tọa độ tâm và gửi lệnh click chính xác vào điện thoại.

Hình 2: Công cụ kéo thả tạo bảng chia lưới bàn phím số 4x3 trên khung Canvas bảo mật

### Nhận diện và chuyển tiếp bàn phím phần cứng
- Bấm trực tiếp các phím số `0` đến `9` (kể cả cụm Numpad) trên bàn phím máy tính để nhập số.
- Phím `Backspace` tự động chuyển tiếp lệnh xóa (ưu tiên nút xóa trên lưới ảo hoặc node có resource-id chứa từ khóa delete/xóa).
- Phím `Enter` tự động kích hoạt nút xác nhận hoặc gửi biểu mẫu.

### Trích xuất file XML đầy đủ layout và text
- Tích hợp nút chức năng trích xuất toàn bộ cấu trúc giao diện điện thoại ra file XML chuẩn trên máy tính.
- Đường dẫn lưu trữ mặc định: `%USERPROFILE%\Downloads\XMlExtracted\window_dump.xml`.
- Tự động lưu kèm một bản sao có gắn dấu thời gian (timestamp) để phục vụ việc lưu trữ lịch sử kiểm thử.

Hình 3: Giao diện thanh điều khiển đáy tích hợp nút trích xuất XML và các thao tác nhanh

### Cửa sổ dòng lệnh ADB nhanh và cơ chế cô lập thiết bị (Target Device Isolation)
- Nút bấm `[Lenh ADB]` màu xanh lá cây đặc trưng (cmd hacker font) được bố trí ngay sau nút `[Soi XML]`.
- Mở cửa sổ dòng lệnh độc lập phong cách Matrix/Hacker Terminal với phông chữ Consolas xanh neon trên nền đen, có thể giữ mở song song với màn hình điện thoại mà không gây cản trở thao tác.
- Cơ chế cô lập thiết bị đích (Device Isolation): Bất kể người dùng gõ lệnh chung (ví dụ: `shell input keyevent 3`, `shell getprop`), có tiền tố `adb`, hay vô tình gõ cờ `-s <serial khác>`, bộ lọc tự động chuẩn hóa và gán cứng tham số `-s <device_serial>` của chính cửa sổ đang soi.
- Khắc phục triệt để lỗi xung đột đa thiết bị `error: more than one device/emulator` khi máy tính cắm đồng thời nhiều điện thoại qua cổng USB hoặc mạng không dây.
- Tích hợp phím bấm tác vụ nhanh: Home (phím 3), Back (phím 4), Power (phím 26), Menu (phím 187), kích thước màn hình (wm size), địa chỉ IP Wi-Fi và xóa màn hình.
- Hỗ trợ lưu trữ lịch sử dòng lệnh, duyệt lại các câu lệnh trước đó bằng phím Mũi tên Lên / Xuống như terminal chuyên nghiệp.

Hình 4: Cửa sổ dòng lệnh ADB nhanh với giao diện Hacker Terminal và cơ chế cô lập thiết bị

---

## 3. Kiến trúc hoạt động

Hệ thống hoạt động theo mô hình lớp phủ đa luồng (Multi-threaded Transparent Overlay Architecture):

```
+-------------------------------------------------------------+
|                     Windows Desktop                         |
|                                                             |
|  +---------------------+      +--------------------------+  |
|  |   Cửa sổ QtScrcpy   | <=== |  TransparentOverlay      |  |
|  |  (Màn hình hiển thị | Đồng |  (Cửa sổ PyQt không viền |  |
|  |   Android bị đen)   | bộ vị|   trong suốt bám dính)   |  |
|  +---------------------+ trí  +--------------------------+  |
|            ^                                |               |
+------------|--------------------------------|---------------+
             |                                | Gửi click / phím
       Truyền video                     +-----v---------------+
             |                          | Luồng nền (Thread)  |
+------------v--------------------------|- uiautomator2 / adb |
|             Thiết bị Android          | shell uiautomator   |
|                                       +---------------------+
|  - Ứng dụng ngân hàng / ShopeePay               |           |
|  - FLAG_SECURE kích hoạt                        v           |
|  - Trích xuất XML hierarchy <-------------------+           |
+-------------------------------------------------------------+
```

1. **Khối phát hiện cửa sổ (Window Enumerator):** Sử dụng các hàm Windows API native (`EnumDesktopWindows`, `GetClientRect`, `ClientToScreen`) kết hợp kiểm tra Process ID để định vị chính xác vùng hiển thị video của QtScrcpy.
2. **Khối chuẩn hóa tỷ lệ (Geometry & Aspect Ratio Engine):** Tính toán độ co giãn giữa kích cỡ pixel thực của điện thoại (ví dụ: 1080x2316) và kích cỡ cửa sổ hiển thị trên PC, tự động áp dụng dung sai 0.8% để loại bỏ hiện tượng giật viền sub-pixel.
3. **Khối quét dữ liệu ngầm (XML Worker Thread):** Chạy tác vụ lấy dữ liệu XML qua luồng `QThread` độc lập, tránh hiện tượng đóng băng giao diện người dùng (GUI freeze) trong 200–400ms trích xuất dữ liệu.
4. **Khối hiển thị đồ họa (QPainter Rendering):** Vẽ lớp nền đen mờ (translucent background), hệ thống khung Cyan/Tím, con trỏ văn bản nhấp nháy và lưới bàn phím số ảo.
5. **Khối chuyển tiếp sự kiện (Input Forwarder):** Chuyển đổi tọa độ click trên màn hình máy tính thành tọa độ tương ứng trên điện thoại và gửi lệnh qua ADB daemon trong luồng nền.

---

## 4. Yêu cầu hệ thống

- **Hệ điều hành:** Microsoft Windows 10 hoặc Windows 11 (64-bit).
- **Môi trường Python:** Python 3.8 trở lên.
- **Phần mềm trình chiếu:** QtScrcpy (phiên bản v3.x hoặc v4.x) hoặc Scrcpy tiêu chuẩn.
- **Thiết bị Android:** Chạy Android 5.0 trở lên, đã kích hoạt chế độ **Gỡ lỗi USB (USB Debugging)**.
- **Kết nối cáp:** Cáp USB truyền dữ liệu hoặc kết nối ADB qua mạng không dây (ADB Wireless).

---

## 5. Hướng dẫn cài đặt

### Bước 1: Clone kho mã nguồn về máy tính
```bash
git clone https://github.com/your-username/ScrcpySecureOverlay.git
cd ScrcpySecureOverlay
```

### Bước 2: Cài đặt các thư viện phụ thuộc
Cài đặt các gói thư viện Python cần thiết thông qua pip:
```bash
pip install PyQt5 uiautomator2
```
*Lưu ý: Nếu môi trường của bạn sử dụng PySide6 thay cho PyQt5, ứng dụng sẽ tự động chuyển đổi backend tương thích mà không cần sửa code.*

### Bước 3: Cài đặt khởi tạo uiautomator2 trên điện thoại (chỉ cần làm lần đầu)
Kết nối điện thoại với máy tính qua cổng USB, mở terminal và chạy:
```bash
python -m uiautomator2 init
```
Lệnh này sẽ tự động cài đặt gói hỗ trợ tương tác lên thiết bị Android.

---

## 6. Hướng dẫn sử dụng

### Quy trình sử dụng thực tế

1. **Khởi chạy QtScrcpy:**
   - Mở phần mềm QtScrcpy và kết nối với điện thoại của bạn.
   - Cửa sổ truyền hình ảnh sẽ xuất hiện với tiêu đề dạng `Phone-<serial>` (ví dụ: `Phone-R3CT104B80P`).
    <img width="682" height="464" alt="image" src="https://github.com/user-attachments/assets/4624c07c-5ea8-4ade-9dd5-01714632a28c" />

    
2. **Khởi chạy ứng dụng lớp phủ:**
   ```bash
   python qtscrcpy_overlay.py
   ```
   Lớp phủ sẽ tự động tìm thấy cửa sổ QtScrcpy và hiển thị thanh điều khiển màu đen viền xanh bám dính ở đáy màn hình.
    <img width="990" height="600" alt="image" src="https://github.com/user-attachments/assets/2cdc4773-6371-4928-9839-046afc1b243a" />

3. **Kích hoạt chế độ soi XML:**
   - Bấm nút **[Soi XML]** trên thanh công cụ hoặc ấn phím **F5**.
   - Màn hình sẽ chuyển sang chế độ phân tích, hiển thị đầy đủ các phần tử giao diện dưới dạng khung viền Cyan và ô nhập liệu màu Tím.
  
     
    <img width="275" height="605" alt="image" src="https://github.com/user-attachments/assets/230b7dc0-181d-4a51-bd4d-064a02df999b" />

Hình 4: Trạng thái hiển thị các khung giao diện sau khi phân tích cây XML thành công


<img width="271" height="602" alt="image" src="https://github.com/user-attachments/assets/d8809db6-36e5-44ce-adc7-151fd77cbef8" />

4. **Tương tác trên màn hình bảo mật:**
   - Click chuột trái vào các khung để tương tác bình thường.
   - Khi gặp ô nhập mã PIN hoặc mật khẩu, gõ trực tiếp các số `0` đến `9` trên bàn phím máy tính.

5. **Chia lưới bàn phím ảo (áp dụng cho bàn phím vẽ bằng Canvas):**
   - Click chuột phải vào khung chứa bàn phím bảo mật.
   - Một bảng chọn kích thước sẽ hiện lên. Di chuột để chọn **4 hàng x 3 cột** rồi click chuột trái để xác nhận.
   - Khung sẽ lập tức được chia thành 12 nút phím bấm ảo với đầy đủ số từ 1 đến 9, phím 0 và phím Xóa.

6. **Trích xuất dữ liệu XML:**
   - Bấm nút **[Xuat XML]** hoặc ấn tổ hợp phím **Ctrl + S** (hoặc **F6**).
   - File cấu trúc giao diện sẽ lập tức được lưu vào máy tính.

7. **Thực thi lệnh ADB nhanh với thiết bị đích:**
   - Bấm nút **[Lenh ADB]** màu xanh lá cây hoặc ấn phím **F7**.
   - Cửa sổ ADB Terminal sẽ mở ra với dòng trạng thái xác nhận đã khóa cứng thiết bị đích (ví dụ: `Phone-R3CT104B80P`).
   - Nhập lệnh cần chạy (hoặc bấm các nút tác vụ nhanh như Home, Back, Power, wm size, IP Wi-Fi) rồi nhấn **Enter**.
   - Toàn bộ kết quả đầu ra và mã lỗi được hiển thị trực tiếp trong khung terminal mà không làm ảnh hưởng đến các thao tác trên màn hình điện thoại.

8. **Tắt chế độ soi:**
   - Bấm nút **[Tat XML (ESC)]** hoặc ấn phím **ESC** để tắt lớp phủ khi không cần soi, trả lại khả năng tương tác trực tiếp cho cửa sổ QtScrcpy.
   - Bấm nút **[Thoat]** màu đỏ ở góc dưới để tắt hoàn toàn ứng dụng.

---

## 7. Bảng phím tắt điều khiển

| Phím tắt | Phạm vi hoạt động | Chức năng chi tiết |
| :--- | :--- | :--- |
| **F5** | Chế độ Soi XML | Quét và tải lại cây phân cấp giao diện mới nhất từ điện thoại |
| **F7** | Mọi chế độ | Mở / kích hoạt cửa sổ dòng lệnh ADB nhanh (Hacker Terminal) |
| **ESC** | Chế độ Soi XML | Thoát chế độ soi XML (chuyển sang chế độ click-through trong suốt) |
| **Ctrl + S** | Mọi chế độ | Trích xuất file XML đầy đủ layout & text ra thư mục Downloads mặc định |
| **F6** | Mọi chế độ | Phím tắt phụ tương đương với Ctrl + S để trích xuất XML |
| **Chuột phải** | Chế độ Soi XML | Mở bảng kéo thả chia lưới bàn phím ảo cho khung đang trỏ chuột |
| **0 - 9 / Numpad** | Chế độ Soi XML | Bấm số tương ứng (ưu tiên lưới ảo 4x3 hoặc node số thực tế) |
| **Backspace** | Chế độ Soi XML | Kích hoạt nút xóa ký tự trên bàn phím ảo hoặc nút xóa XML |
| **Enter / Return** | Chế độ Soi XML | Kích hoạt nút xác nhận, đồng ý hoặc gửi dữ liệu |
| **Mũi tên Lên / Xuống** | ADB Terminal | Duyệt lại lịch sử các câu lệnh ADB đã thực thi trước đó |

---

## 8. Cơ chế trích xuất dữ liệu XML

Khi người dùng kích hoạt lệnh trích xuất XML (bấm nút hoặc dùng phím tắt), ứng dụng thực hiện quy trình tự động hai tầng:

```
[Người dùng bấm Xuất XML / Ctrl+S]
                 |
                 v
[Bước 1: Thực thi lệnh ADB trên thiết bị]
adb shell uiautomator dump /sdcard/window_dump.xml
                 |
                 v
[Bước 2: Kéo file dữ liệu về máy tính]
adb pull /sdcard/window_dump.xml %USERPROFILE%\Downloads\XMlExtracted\window_dump.xml
                 |
          +------+------+
          |             |
      (Thành công)   (Thất bại / Bị chiếm quyền)
          |             |
          |             v
          |      [Cơ chế dự phòng]
          |      Trích xuất trực tiếp qua uiautomator2 (compressed=False)
          |      Ghi file trực tiếp ra máy tính và đẩy lên /sdcard/
          |             |
          +------+------+
                 |
                 v
[Bước 3: Tạo bản sao lưu lịch sử có timestamp]
window_dump_YYYYMMDD_HHMMSS.xml
```

### Cấu trúc thư mục xuất ra
```text
C:\Users\<Tên_người_dùng>\Downloads\XMlExtracted\
|-- window_dump.xml                  <- Luôn chứa dữ liệu của lần trích xuất mới nhất
|-- window_dump_20261002_110632.xml  <- Bản sao lịch sử kiểm thử
|-- window_dump_20261002_111540.xml  <- Bản sao lịch sử kiểm thử
```

Tệp XML được trích xuất ở định dạng đầy đủ (không nén), giữ nguyên vẹn toàn bộ thuộc tính của từng node:
- Tọa độ khung hình: `bounds="[x1,y1][x2,y2]"`
- Nội dung văn bản: `text="..."`
- Mô tả trợ năng: `content-desc="..."`
- Mã định danh tài nguyên: `resource-id="..."`
- Tên lớp giao diện: `class="android.widget.EditText"`, `FrameLayout`, v.v.
- Trạng thái điều khiển: `clickable`, `focused`, `password`, `enabled`, `scrollable`.

---

## 9. Cơ chế cô lập lệnh ADB (Target Device Isolation)

Khi người dùng làm việc trong môi trường đa thiết bị (cắm nhiều điện thoại Android hoặc mở đồng thời nhiều giả lập), việc gửi lệnh ADB thông thường rất dễ gặp lỗi nghiêm trọng:
```text
adb: error: more than one device/emulator
```
Hoặc nghiêm trọng hơn là người dùng gửi nhầm lệnh can thiệp (ví dụ gỡ ứng dụng, reboot, nhập keyevent) sang thiết bị khác ngoài ý muốn.

ScrcpySecureOverlay giải quyết triệt để vấn đề này thông qua cơ chế **Cô lập thiết bị đích (Target Device Isolation Engine)** hoạt động theo quy trình 3 bước:

```text
[Lệnh người dùng nhập] (VD: adb -s OTHER_PHONE shell getprop ro.product.model)
                       |
                       v
[Bước 1: Bộ lọc Command Sanitizer]
- Tách tham số dòng lệnh an toàn với shlex (bảo toàn nháy đơn, nháy kép)
- Loại bỏ tiền tố 'adb', 'adb.exe' nếu người dùng gõ thừa
- Lọc bỏ triệt để mọi cờ thiết bị: -s <id>, -s<id>, --serial <id>, --serial=<id>
                       |
                       v
[Bước 2: Gán cứng định danh thiết bị đích]
- Trích xuất serial độc quyền gắn với cửa sổ đang soi: self.device_serial
- Tự động tái cấu trúc lệnh thực thi:
  [adb_bin, "-s", "<device_serial>"] + <các tham số đã làm sạch>
                       |
                       v
[Bước 3: Thực thi luồng ngầm (QThread Worker)]
- Thực thi qua subprocess không mở cửa sổ cmd đen phụ
- Bắt trọn stdout, stderr và mã trả về (exit code) với cơ chế timeout 25s
- Xuất dữ liệu trực quan ra cửa sổ ADB Terminal phong cách hacker
```

### Các trường hợp xử lý mẫu của bộ lọc

| Lệnh người dùng gõ vào ô nhập | Lệnh thực tế được hệ thống thực thi | Kết quả bảo đảm |
| :--- | :--- | :--- |
| `shell input keyevent 3` | `adb -s R3CT104B80P shell input keyevent 3` | Không bị lỗi thiếu thiết bị |
| `adb shell wm size` | `adb -s R3CT104B80P shell wm size` | Tự động loại bỏ tiền tố adb |
| `adb -s DEVICE_KHAC shell getprop` | `adb -s R3CT104B80P shell getprop` | Ghi đè bắt buộc sang máy đang soi |
| `-s FAKE_SERIAL reboot` | `adb -s R3CT104B80P reboot` | Triệt tiêu cờ sai, chỉ tác động máy hiện tại |
| `shell "input text 'Hello World'"` | `adb -s R3CT104B80P shell "input text 'Hello World'"` | Bảo toàn khoảng trắng và dấu ngoặc kép |

---

## 10. Cấu hình tham số dòng lệnh

Ứng dụng hỗ trợ các tham số dòng lệnh phục vụ tự động hóa hoặc sử dụng trong môi trường đa thiết bị:

```bash
python qtscrcpy_overlay.py [TÙY_CHỌN]
```

### Danh sách tham số
- `--title <từ_khóa>`: Tùy chỉnh từ khóa tiêu đề cửa sổ cần bám dính (mặc định: `QtScrcpy`).
- `--serial <mã_serial>`: Chỉ định mã serial cụ thể của thiết bị ADB cần tương tác (ví dụ: `R3CT104B80P`). Mặc định ứng dụng tự động nhận diện thiết bị đầu tiên kết nối.
- `--demo`: Khởi chạy ở chế độ mô phỏng độc lập (không cần kết nối điện thoại và không cần mở QtScrcpy thật). Chế độ này dựng sẵn một cửa sổ giả lập giao diện ShopeePay để thử nghiệm chức năng chia lưới và nhập PIN 6 số.

### Ví dụ thực thi
```bash
# Chạy với thiết bị chỉ định
python qtscrcpy_overlay.py --serial R3CT104B80P

# Chạy chế độ demo để trải nghiệm giao diện
python qtscrcpy_overlay.py --demo
```

---

## 11. Xử lý sự cố thường gặp (Troubleshooting)

### Sự cố 1: Lớp phủ báo "Chưa kết nối được thiết bị Android qua ADB"
- **Nguyên nhân:** Máy tính chưa nhận diện được thiết bị hoặc chưa cấp quyền gỡ lỗi USB.
- **Cách khắc phục:**
  1. Mở terminal và kiểm tra bằng lệnh: `adb devices`.
  2. Đảm bảo trạng thái thiết bị hiển thị là `device` thay vì `unauthorized` hoặc `offline`.
  3. Mở khóa màn hình điện thoại và bấm **Đồng ý (Always allow from this computer)** khi hộp thoại gỡ lỗi hiện lên.

### Sự cố 2: Lớp phủ không tự dính vào cửa sổ QtScrcpy
- **Nguyên nhân:** Cửa sổ QtScrcpy đang bị thu nhỏ (minimized) hoặc tiêu đề cửa sổ không chứa định dạng chuẩn.
- **Cách khắc phục:**
  1. Đảm bảo cửa sổ truyền hình ảnh của QtScrcpy đang hiển thị trên màn hình máy tính (không bị thu nhỏ xuống thanh Taskbar).
  2. Kiểm tra tiêu đề cửa sổ có tiền tố `Phone-` (ví dụ: `Phone-R3CT104B80P`). Nếu tiêu đề khác, hãy chạy lệnh với cờ: `python qtscrcpy_overlay.py --title "Tên_Cửa_Sổ"`.

### Sự cố 3: Khung hiển thị lệch so với hình ảnh thực tế
- **Nguyên nhân:** Có thể do phiên bản cũ chưa cập nhật cơ chế gỡ bỏ ràng buộc kích thước tối thiểu.
- **Cách khắc phục:**
  1. Đảm bảo bạn đang sử dụng phiên bản mới nhất từ kho lưu trữ.
  2. Bấm phím **F5** để hệ thống đồng bộ lại kích thước và căn chỉnh lại tỷ lệ khung hình.

---

## 12. Giấy phép sử dụng

Dự án được phân phối dưới giấy phép mã nguồn mở **MIT License**. Bạn hoàn toàn có quyền sử dụng, sửa đổi, tích hợp vào các dự án tự động hóa cá nhân hoặc thương mại mà không có bất kỳ ràng buộc nào.

