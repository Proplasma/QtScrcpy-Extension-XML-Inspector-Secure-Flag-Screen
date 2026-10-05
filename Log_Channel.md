07:00 05/10/2026

Cập nhật tính năng:
- Thêm nút [💻 Lệnh ADB] (phông màu xanh lá cmd hacker) ngay sau nút [Soi XML].
- Tích hợp cửa sổ dòng lệnh AdbCommandDialog phong cách Hacker Terminal:
  + Cơ chế cô lập thiết bị đích (Target Device Isolation): Tự động ép buộc cờ '-s <device_serial>' gắn với cửa sổ đang soi, dù người dùng gõ lệnh chung hay gõ '-s' của máy khác.
  + Tránh triệt để lỗi 'more than one device/emulator' khi cắm nhiều máy cùng lúc.
  + Bổ sung phím tắt nhanh F7, bộ nút thao tác nhanh (Home, Back, Power, Menu, wm size, IP Wi-Fi, Reboot) và duyệt lịch sử lệnh bằng phím Mũi tên Lên/Xuống.
- Đồng bộ toàn bộ mã nguồn đầy đủ sang cả 2 file: qtscrcpy_overlay.py và batchFileFastCalling/showxml001_qtscrcpy_overlay.py.
- Bổ sung tài liệu cơ chế cô lập thiết bị và cập nhật README.md.

---

19:34 02/10/2026

Upload First Commit Tools

To Do Next:
- Thêm ảnh minh họa cho README
- Thêm chức năng log lại những gì đã bấm, số chẳng hạn
- Hướng dẫn add nhanh vào batch file, system32 gọi tool nhanh khi cần
