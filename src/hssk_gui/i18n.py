"""Minimal two-language (Vietnamese / English) translation support."""

from __future__ import annotations

_lang = "vi"

_STRINGS: dict[str, dict[str, str]] = {
    # window / groups
    "window_title": {
        "en": "HSSK Tools v{version} — Health checkup uploader",
        "vi": "HSSK Tools v{version} — Tải lên dữ liệu khám sức khoẻ",
    },
    "msg_gui_already_running": {
        "en": "HSSK Tools is already running. Please use the window that is already open.",
        "vi": "HSSK Tools đang chạy. Vui lòng dùng cửa sổ đang mở.",
    },
    # -- safety-ladder stepper (components/stepper.py) --
    "step_login": {"en": "Login", "vi": "Đăng nhập"},
    "step_file": {"en": "File", "vi": "File"},
    "step_validated": {"en": "Validated", "vi": "Đã kiểm tra"},
    "step_dryrun": {"en": "Dry-run", "vi": "Chạy thử"},
    "step_commit": {"en": "Commit", "vi": "Gửi thật"},
    # -- engine event codes (hssk.events.MessageCode) rendered by hssk_gui/render.py --
    "msg_ROW_CREATED": {"en": "Created", "vi": "Đã tạo"},
    "msg_ROW_UPDATED": {"en": "Updated", "vi": "Đã cập nhật"},
    "msg_ROW_DELETED": {"en": "Deleted", "vi": "Đã xoá"},
    "msg_ROW_DRY_RUN": {"en": "Payload built (not sent)", "vi": "Đã dựng dữ liệu (chưa gửi)"},
    "msg_no_record_id": {"en": "no record id returned", "vi": "không nhận được mã hồ sơ"},
    "msg_ROW_ALREADY_PROCESSED": {"en": "Already processed", "vi": "Đã xử lý trước đó"},
    "msg_ROW_PENDING_VERIFY": {
        "en": (
            "Interrupted while sending previously — check on the website whether the record "
            "exists before re-sending"
        ),
        "vi": (
            "Lần gửi trước bị gián đoạn — kiểm tra trên website xem hồ sơ đã tồn tại chưa trước "
            "khi gửi lại"
        ),
    },
    "msg_ROW_ID_BLANK": {"en": "Identifier is blank", "vi": "Mã định danh trống"},
    "msg_ROW_RECORD_ID_BLANK": {"en": "medicalRecordId is blank", "vi": "medicalRecordId trống"},
    "msg_ROW_COERCE_ERROR": {"en": "Coercion error: ", "vi": "Lỗi chuyển đổi: "},
    "msg_ROW_FETCH_DETAIL_FAILED": {"en": "Fetch detail: ", "vi": "Lỗi lấy chi tiết: "},
    "msg_ROW_PAYLOAD_INVALID": {
        "en": "Payload failed validation: ",
        "vi": "Dữ liệu gửi không hợp lệ: ",
    },
    "msg_ROW_NO_PATIENT": {
        "en": "no patient found for {query}",
        "vi": "không tìm thấy bệnh nhân với {query}",
    },
    "msg_ROW_MULTI_MATCH": {
        "en": "{count} patients match {query}",
        "vi": "{count} bệnh nhân khớp với {query}",
    },
    "msg_multi_match_skip": {"en": "; skipping", "vi": "; bỏ qua"},
    "msg_ROW_MATCH_NO_PATIENT_ID": {
        "en": "match for {query} has no patientId field",
        "vi": "khớp với {query} không có trường patientId",
    },
    "msg_COERCE_CANNOT_PARSE": {
        "en": "{col}: cannot parse {value} as {type} ({detail})",
        "vi": "{col}: không thể đọc {value} thành {type} ({detail})",
    },
    "msg_COERCE_MISSING_REQUIRED": {
        "en": "missing required column {col}",
        "vi": "thiếu cột bắt buộc {col}",
    },
    "msg_COERCE_RANGE": {
        "en": "{target}={value} outside expected range {lo}–{hi}",
        "vi": "{target}={value} nằm ngoài phạm vi {lo}–{hi}",
    },
    "msg_COERCE_DATE_BEFORE": {
        "en": "finishExaminationDate ({finish}) is before examinationDate ({start})",
        "vi": "finishExaminationDate ({finish}) trước examinationDate ({start})",
    },
    "msg_FILE_MISSING_COLUMNS": {
        "en": "Excel {name} is missing required column(s): {cols} — use the Template button "
        "to generate a file for the selected mode.",
        "vi": "File {name} thiếu cột bắt buộc: {cols} — dùng nút 'Mẫu Excel…' để tạo file "
        "đúng chế độ đã chọn.",
    },
    "msg_FILE_DUPLICATE_COLUMNS": {
        "en": "Excel {name} has duplicate column header(s): {cols} — only the right-most copy "
        "would be read; rename or remove the duplicates.",
        "vi": "File {name} có tiêu đề cột bị trùng: {cols} — chỉ cột ngoài cùng bên phải được "
        "đọc; hãy đổi tên hoặc xoá cột trùng.",
    },
    "msg_LOG_UNMAPPED_COLUMNS": {
        "en": "ignoring {n} unmapped Excel column(s): {cols}",
        "vi": "bỏ qua {n} cột Excel không có trong file mapping: {cols}",
    },
    "msg_LOG_FIRST_SEARCH_SAVED": {
        "en": "Logged first search response for inspection.",
        "vi": "Đã ghi phản hồi tìm kiếm đầu tiên để kiểm tra.",
    },
    "msg_LOG_RETRY": {
        "en": "retry in {delay}s (attempt {attempt})",
        "vi": "thử lại sau {delay}s (lần {attempt})",
    },
    "msg_LOG_NO_RECORD_ID": {
        "en": "row {row}: no record id in server response",
        "vi": "dòng {row}: máy chủ không trả về mã hồ sơ",
    },
    "msg_LOG_LEDGER_CORRUPT": {
        "en": "{n} unreadable ledger line(s) — those rows may be re-sent",
        "vi": "{n} dòng nhật ký gửi (ledger) không đọc được — các hàng đó có thể bị gửi lại",
    },
    "msg_LOG_SEARCH_SAVED_ROW": {
        "en": "saved search response for row {row} ({filename})",
        "vi": "đã lưu phản hồi tìm kiếm cho dòng {row} ({filename})",
    },
    "msg_LOG_TOKEN_SHORT": {
        "en": "token may expire before this batch finishes "
        "(~{needed} min needed, ~{left} min left) — consider logging in again first",
        "vi": "⚠ Token có thể hết hạn trước khi chạy xong lô này "
        "(cần ~{needed} phút, còn ~{left} phút) — nên đăng nhập lại trước khi chạy",
    },
    "msg_LOG_DRIFT": {
        "en": "⚠ Server response from {endpoint} was not recognised — the website's API may have "
        "changed. Dry-run and check the results before committing.",
        "vi": "⚠ Phản hồi máy chủ từ {endpoint} không nhận dạng được — API của website có thể đã "
        "thay đổi. Hãy chạy thử và kiểm tra kết quả trước khi gửi thật.",
    },
    "msg_LOGIN_WAITING": {
        "en": "Please log in in the browser window…",
        "vi": "Vui lòng đăng nhập trong cửa sổ trình duyệt…",
    },
    "msg_LOGIN_TOKEN_CAPTURED": {"en": "Token captured.", "vi": "Đã lấy token."},
    "group_login": {"en": "1 · Login", "vi": "1 · Đăng nhập"},
    "group_data": {"en": "2 · Data", "vi": "2 · Dữ liệu"},
    "group_run": {"en": "3 · Run", "vi": "3 · Chạy"},
    "group_results": {"en": "Results", "vi": "Kết quả"},
    # login box
    "btn_login": {
        "en": "Open website && log in",
        "vi": "Mở website && đăng nhập",
    },
    "lbl_not_logged_in": {"en": "Not logged in", "vi": "Chưa đăng nhập"},
    "lbl_opening_browser": {
        "en": "Opening browser… log in in the window that appears.",
        "vi": "Đang mở trình duyệt… đăng nhập trong cửa sổ hiện ra.",
    },
    "lbl_login_waiting": {
        "en": "Please log in in the browser window…",
        "vi": "Vui lòng đăng nhập trong cửa sổ trình duyệt…",
    },
    "lbl_login_captured": {"en": "Token captured.", "vi": "Đã lấy token."},
    "lbl_token_expired": {
        "en": "Token expired — please log in again",
        "vi": "Token đã hết hạn — vui lòng đăng nhập lại",
    },
    "lbl_logged_in": {
        "en": "Logged in ✓{identity}",
        "vi": "Đã đăng nhập ✓{identity}",
    },
    "lbl_logged_in_ttl": {
        "en": "Logged in ✓{identity}  (valid ~{m}m {s}s)",
        "vi": "Đã đăng nhập ✓{identity}  (còn ~{m}m {s}s)",
    },
    # data box
    "btn_choose_excel": {"en": "Choose Excel…", "vi": "Chọn file Excel…"},
    "lbl_no_file": {"en": "No file selected", "vi": "Chưa chọn file"},
    "btn_template": {"en": "Template…", "vi": "Mẫu Excel…"},
    "btn_open_mapping": {"en": "Open mapping", "vi": "Mở file mapping"},
    "btn_validate": {"en": "Validate", "vi": "Kiểm tra"},
    # run box
    "lbl_delay": {"en": "Delay (s):", "vi": "Độ trễ (s):"},
    "lbl_limit": {"en": "Limit (0 = all):", "vi": "Giới hạn (0 = tất cả):"},
    "chk_dryrun": {"en": "Dry-run (don't send)", "vi": "Chạy thử (không gửi)"},
    "btn_start_dryrun": {"en": "Start dry-run", "vi": "Bắt đầu chạy thử"},
    "btn_start_live": {"en": "⚠  PUSH live records", "vi": "⚠  ĐẨY DỮ LIỆU THẬT"},
    "btn_stop": {"en": "Stop", "vi": "Dừng"},
    "banner_production": {
        "en": "⚠️  PRODUCTION — this sends LIVE medical records",
        "vi": "⚠️  PRODUCTION — đang gửi hồ sơ y tế THẬT",
    },
    # results box
    "btn_open_results": {"en": "Open results spreadsheet", "vi": "Mở bảng kết quả"},
    "btn_open_report": {"en": "Open report folder", "vi": "Mở thư mục báo cáo"},
    "log_placeholder": {"en": "Engine log…", "vi": "Nhật ký…"},
    # table columns
    "col_row": {"en": "Row", "vi": "Hàng"},
    "col_identifier": {"en": "Identifier", "vi": "Mã định danh"},
    "col_status": {"en": "Status", "vi": "Trạng thái"},
    "col_patient_id": {"en": "PatientId", "vi": "Mã BN"},
    "col_record_id": {"en": "RecordId", "vi": "Mã hồ sơ"},
    "col_message": {"en": "Message", "vi": "Ghi chú"},
    # menu
    "menu_file": {"en": "File", "vi": "Tệp"},
    "menu_open_recent": {"en": "Open recent", "vi": "Mở gần đây"},
    "menu_recent_empty": {"en": "(no recent files)", "vi": "(chưa có file nào)"},
    "menu_open_reports_root": {
        "en": "Open reports folder (all runs)",
        "vi": "Mở thư mục báo cáo (tất cả các lần chạy)",
    },
    "menu_purge_reports": {"en": "Purge old reports…", "vi": "Xoá báo cáo cũ…"},
    "dlg_purge_title": {"en": "Purge old reports", "vi": "Xoá báo cáo cũ"},
    "msg_purge_confirm": {
        "en": "Delete {n} report folder(s) older than {days} days?\nThis cannot be undone.",
        "vi": "Xoá {n} thư mục báo cáo cũ hơn {days} ngày?\nThao tác này không thể hoàn tác.",
    },
    "msg_purge_none": {
        "en": "No report folders are older than {days} days.",
        "vi": "Không có thư mục báo cáo nào cũ hơn {days} ngày.",
    },
    "msg_purge_done": {
        "en": "Deleted {n} old report folder(s).",
        "vi": "Đã xoá {n} thư mục báo cáo cũ.",
    },
    "msg_recent_missing": {
        "en": "File no longer exists: {path}",
        "vi": "File không còn tồn tại: {path}",
    },
    "menu_settings": {"en": "Settings", "vi": "Cài đặt"},
    "menu_settings_action": {"en": "Settings…", "vi": "Cài đặt…"},
    "menu_help": {"en": "Help", "vi": "Trợ giúp"},
    "menu_user_guide": {"en": "User Guide", "vi": "Hướng dẫn sử dụng"},
    "menu_support_bundle": {"en": "Export support bundle…", "vi": "Xuất gói hỗ trợ…"},
    "dlg_support_title": {"en": "Export support bundle", "vi": "Xuất gói hỗ trợ"},
    "msg_support_intro": {
        "en": (
            "Creates a zip with the app logs, your mapping, and version info to send to support. "
            "Your saved login token is never included."
        ),
        "vi": (
            "Tạo tệp zip gồm nhật ký ứng dụng, cấu hình ánh xạ và thông tin phiên bản để gửi cho "
            "bộ phận hỗ trợ. Mã đăng nhập đã lưu sẽ không bao giờ được đưa vào."
        ),
    },
    "chk_support_events": {
        "en": "Include latest run's event log (may contain patient identifiers)",
        "vi": "Kèm nhật ký sự kiện của lần chạy gần nhất (có thể chứa mã bệnh nhân)",
    },
    "msg_support_done": {
        "en": "Support bundle saved: {path}",
        "vi": "Đã lưu gói hỗ trợ: {path}",
    },
    "guide_title": {
        "en": "HSSK Tools — User Guide",
        "vi": "HSSK Tools — Hướng dẫn sử dụng",
    },
    "menu_terms": {"en": "Terms of Use", "vi": "Điều khoản sử dụng"},
    "menu_privacy": {"en": "Privacy Policy", "vi": "Chính sách bảo mật"},
    "menu_security": {"en": "Security", "vi": "Bảo mật"},
    "menu_about": {"en": "About HSSK Tools", "vi": "Về HSSK Tools"},
    # sponsor / support dialog
    "menu_sponsor": {"en": "Support the Developer…", "vi": "Ủng hộ nhà phát triển…"},
    "footer_sponsor": {"en": "Support the developer", "vi": "Ủng hộ nhà phát triển"},
    "sponsor_title": {"en": "Support HSSK Tools", "vi": "Ủng hộ HSSK Tools"},
    "sponsor_intro": {
        "en": "If HSSK Tools saves you time, a small donation keeps it maintained and free.",
        "vi": "Nếu HSSK Tools giúp ích cho bạn, một chút ủng hộ sẽ giúp duy trì và phát triển.",
    },
    "sponsor_vietqr_caption": {
        "en": "Bank transfer (VietQR)",
        "vi": "Chuyển khoản ngân hàng (VietQR)",
    },
    "sponsor_momo_caption": {"en": "MoMo wallet", "vi": "Ví MoMo"},
    "sponsor_thanks": {
        "en": "Thank you for your support!",
        "vi": "Cảm ơn bạn đã ủng hộ!",
    },
    "sponsor_qr_missing": {"en": "QR image not available", "vi": "Chưa có ảnh QR"},
    # Copyable payment details shown below each QR (replace with real info when QR images are set).
    "sponsor_vietqr_details": {
        "en": "(scan QR with your banking app)",
        "vi": "(quét mã QR bằng ứng dụng ngân hàng)",
    },
    "sponsor_momo_details": {
        "en": "(scan QR with the MoMo app)",
        "vi": "(quét mã QR bằng ứng dụng MoMo)",
    },
    # Accessibility names for QR images (announced by screen readers instead of silence).
    "a11y_vietqr_qr": {
        "en": "VietQR bank transfer QR code",
        "vi": "Mã QR chuyển khoản ngân hàng VietQR",
    },
    "a11y_momo_qr": {
        "en": "MoMo e-wallet QR code",
        "vi": "Mã QR ví điện tử MoMo",
    },
    # Accessibility names for dynamic status labels (screen reader announces the role).
    "a11y_token_status": {"en": "Login status", "vi": "Trạng thái đăng nhập"},
    "a11y_file_status": {"en": "Selected file", "vi": "File đã chọn"},
    # inline notice banner
    "tip_dismiss_banner": {"en": "Dismiss", "vi": "Đóng thông báo"},
    "a11y_error_banner": {"en": "Notification", "vi": "Thông báo"},
    # about dialog
    "about_title": {"en": "About HSSK Tools", "vi": "Về HSSK Tools"},
    "about_body": {
        "en": (
            "<b>HSSK Tools</b> v{version}<br><br>"
            "Bulk-pushes health-checkup data from Excel into "
            "<a href='https://hososuckhoe.com.vn'>hososuckhoe.com.vn</a>.<br><br>"
            "Bundle ID: <code>vn.hososuckhoe.hssktools</code>"
        ),
        "vi": (
            "<b>HSSK Tools</b> v{version}<br><br>"
            "Đẩy hàng loạt dữ liệu khám sức khoẻ từ Excel lên "
            "<a href='https://hososuckhoe.com.vn'>hososuckhoe.com.vn</a>.<br><br>"
            "Bundle ID: <code>vn.hososuckhoe.hssktools</code>"
        ),
    },
    # login messages
    "dlg_login_failed": {"en": "Login failed", "vi": "Đăng nhập thất bại"},
    # file dialogs
    "dlg_choose_excel_title": {"en": "Choose Excel file", "vi": "Chọn file Excel"},
    "dlg_save_template_title": {"en": "Save Excel template", "vi": "Lưu mẫu Excel"},
    "filter_excel_multi": {
        "en": "Excel files (*.xlsx *.xlsm)",
        "vi": "File Excel (*.xlsx *.xlsm)",
    },
    "filter_excel_xlsx": {"en": "Excel files (*.xlsx)", "vi": "File Excel (*.xlsx)"},
    # template
    "dlg_template_error": {"en": "Template error", "vi": "Lỗi tạo mẫu"},
    "dlg_template_created": {"en": "Template created", "vi": "Đã tạo mẫu"},
    "msg_saved_to": {
        "en": "Saved to:\n{path}",
        "vi": "Đã lưu vào:\n{path}",
    },
    # validation
    "dlg_validation": {"en": "Validation", "vi": "Kiểm tra"},
    "msg_validation_done": {
        "en": "Validation finished ({total} rows).",
        "vi": "Kiểm tra xong ({total} hàng).",
    },
    "msg_no_issues": {"en": "No issues found.", "vi": "Không có lỗi."},
    "val_status_invalid": {"en": "INVALID", "vi": "Không hợp lệ"},
    "val_status_warning": {"en": "WARNING", "vi": "Cảnh báo"},
    # run result statuses (results table)
    "status_CREATED": {"en": "Created", "vi": "Đã tạo"},
    "status_UPDATED": {"en": "Updated", "vi": "Đã cập nhật"},
    "status_DELETED": {"en": "Deleted", "vi": "Đã xoá"},
    "status_DRY_RUN_OK": {"en": "Dry-run OK", "vi": "Chạy thử OK"},
    "status_SKIPPED_ALREADY": {"en": "Skipped (already sent)", "vi": "Bỏ qua (đã gửi)"},
    "status_PENDING_VERIFY": {"en": "Needs verification", "vi": "Cần kiểm tra lại"},
    "status_INVALID": {"en": "Invalid", "vi": "Không hợp lệ"},
    "status_NO_PATIENT": {"en": "No patient found", "vi": "Không thấy bệnh nhân"},
    "status_MULTI_MATCH": {"en": "Multiple matches", "vi": "Trùng nhiều bệnh nhân"},
    "status_FAILED": {"en": "Failed", "vi": "Thất bại"},
    "status_AUTH_EXPIRED": {"en": "Token expired", "vi": "Token hết hạn"},
    "status_RATE_LIMITED": {"en": "Server busy", "vi": "Máy chủ bận"},
    # mode combo (run box)
    "lbl_mode": {"en": "Mode:", "vi": "Chế độ:"},
    "mode_create": {"en": "Create", "vi": "Tạo mới"},
    "mode_update": {"en": "Update", "vi": "Cập nhật"},
    "mode_delete": {"en": "Delete", "vi": "Xoá"},
    "btn_start_update_live": {"en": "⚠  UPDATE live records", "vi": "⚠  CẬP NHẬT DỮ LIỆU THẬT"},
    "btn_start_delete_live": {"en": "⚠  DELETE live records", "vi": "⚠  XOÁ HỒ SƠ THẬT"},
    "banner_production_update": {
        "en": "⚠️  PRODUCTION — this UPDATES LIVE medical records",
        "vi": "⚠️  PRODUCTION — đang CẬP NHẬT hồ sơ y tế THẬT",
    },
    "banner_production_delete": {
        "en": "⚠️  PRODUCTION — this DELETES LIVE medical records",
        "vi": "⚠️  PRODUCTION — đang XOÁ hồ sơ y tế THẬT",
    },
    # production confirm
    "dlg_confirm_push": {
        "en": "Confirm PRODUCTION push",
        "vi": "Xác nhận đẩy dữ liệu THẬT",
    },
    "msg_confirm_push": {
        "en": "This will create LIVE medical records on hososuckhoe.com.vn.\n\nProceed?",
        "vi": "Thao tác này sẽ tạo hồ sơ y tế THẬT trên hososuckhoe.com.vn.\n\nTiếp tục?",
    },
    "msg_confirm_push_update": {
        "en": "This will UPDATE LIVE medical records on hososuckhoe.com.vn.\n\nProceed?",
        "vi": "Thao tác này sẽ CẬP NHẬT hồ sơ y tế THẬT trên hososuckhoe.com.vn.\n\nTiếp tục?",
    },
    "msg_confirm_push_delete": {
        "en": ("This will PERMANENTLY DELETE medical records on hososuckhoe.com.vn.\n\nProceed?"),
        "vi": ("Thao tác này sẽ XOÁ VĨNH VIỄN hồ sơ y tế trên hososuckhoe.com.vn.\n\nTiếp tục?"),
    },
    "btn_confirm_push": {"en": "Confirm", "vi": "Xác nhận"},
    "dlg_update_needs_record_id": {
        "en": "Update mode — mapping error",
        "vi": "Chế độ cập nhật — lỗi mapping",
    },
    "msg_update_needs_record_id": {
        "en": (
            "Update mode needs the medicalRecordId column, which lives in mapping.update.yaml.\n\n"
            "That file is created automatically; if the column is missing, check that "
            "mapping.update.yaml still maps a column to target: medicalRecordId, required: true."
        ),
        "vi": (
            "Chế độ cập nhật cần cột medicalRecordId, nằm trong file mapping.update.yaml.\n\n"
            "File này được tạo tự động; nếu thiếu cột, hãy kiểm tra mapping.update.yaml vẫn "
            "ánh xạ một cột tới target: medicalRecordId, required: true."
        ),
    },
    "dlg_delete_needs_record_id": {
        "en": "Delete mode — mapping error",
        "vi": "Chế độ xoá — lỗi mapping",
    },
    "msg_delete_needs_record_id": {
        "en": (
            "Delete mode needs the medicalRecordId column, which lives in mapping.update.yaml.\n\n"
            "That file is created automatically; if the column is missing, check that "
            "mapping.update.yaml still maps a column to target: medicalRecordId, required: true."
        ),
        "vi": (
            "Chế độ xoá cần cột medicalRecordId, nằm trong file mapping.update.yaml.\n\n"
            "File này được tạo tự động; nếu thiếu cột, hãy kiểm tra mapping.update.yaml vẫn "
            "ánh xạ một cột tới target: medicalRecordId, required: true."
        ),
    },
    "dlg_mapping_error": {"en": "Mapping error", "vi": "Lỗi mapping"},
    "msg_bad_targets": {
        "en": "Mapping contains unknown API field target(s):\n{targets}",
        "vi": "Mapping chứa trường API không hợp lệ:\n{targets}",
    },
    # progress
    "prog_starting": {
        "en": "Starting… ({total} rows)",
        "vi": "Đang bắt đầu… ({total} hàng)",
    },
    "prog_all_done": {
        "en": "All {total} rows processed",
        "vi": "Đã xử lý {total} hàng",
    },
    "prog_row_of": {
        "en": "Row {done} of {total}   {eta}",
        "vi": "Hàng {done}/{total}   {eta}",
    },
    "prog_row_of_no_eta": {
        "en": "Row {done} of {total}",
        "vi": "Hàng {done}/{total}",
    },
    "eta_min_sec": {"en": "~{m}m {s}s left", "vi": "còn ~{m}m {s}s"},
    "eta_sec": {"en": "~{s}s left", "vi": "còn ~{s}s"},
    "msg_token_expired_abort": {
        "en": (
            "Your login token expired.\n\n"
            "Click 'Open website & log in', then press Start again — "
            "rows already sent will be skipped automatically."
        ),
        "vi": (
            "Token đăng nhập đã hết hạn.\n\n"
            "Nhấn 'Mở website && đăng nhập', sau đó nhấn Bắt đầu lại — "
            "các hàng đã gửi sẽ được tự động bỏ qua."
        ),
    },
    "lbl_aborted_token": {"en": "Aborted — token expired.", "vi": "Đã dừng — token hết hạn."},
    "msg_rate_limited_abort": {
        "en": (
            "The server is busy or temporarily unreachable.\n\n"
            "Wait a few minutes and press Start again — "
            "rows already sent will be skipped automatically."
        ),
        "vi": (
            "Máy chủ đang bận hoặc tạm thời không thể kết nối.\n\n"
            "Chờ vài phút và nhấn Bắt đầu lại — "
            "các hàng đã gửi sẽ được tự động bỏ qua."
        ),
    },
    "lbl_aborted_server": {"en": "Aborted — server error.", "vi": "Đã dừng — lỗi máy chủ."},
    "msg_run_cancelled": {"en": "Run cancelled.", "vi": "Đã hủy chạy."},
    "lbl_cancelled": {"en": "Cancelled.", "vi": "Đã hủy."},
    "msg_processed_of": {
        "en": "Processed {done} of {total} rows before stopping.",
        "vi": "Đã xử lý {done}/{total} hàng trước khi dừng.",
    },
    "msg_done": {
        "en": "Done — {done} rows processed.",
        "vi": "Hoàn thành — đã xử lý {done} hàng.",
    },
    "lbl_finished": {
        "en": "Finished ({done} rows).",
        "vi": "Hoàn thành ({done} hàng).",
    },
    "msg_skipped_rows": {
        "en": (
            "\n{skipped} already-sent row(s) were skipped — safe to re-run, "
            "previously sent rows are always skipped."
        ),
        "vi": (
            "\n{skipped} hàng đã gửi trước đó đã được bỏ qua — "
            "có thể chạy lại an toàn, các hàng đã gửi luôn được bỏ qua."
        ),
    },
    "msg_report_path": {"en": "\nReport: {path}", "vi": "\nBáo cáo: {path}"},
    "dlg_run_failed": {"en": "Run failed", "vi": "Chạy thất bại"},
    "lbl_error": {"en": "Error.", "vi": "Lỗi."},
    # disabled Start tooltips / nudges
    "tip_start_need_login": {
        "en": "Log in first to enable Start.",
        "vi": "Đăng nhập trước để bật nút Bắt đầu.",
    },
    "tip_start_need_file": {
        "en": "Choose an Excel file to enable Start.",
        "vi": "Chọn file Excel để bật nút Bắt đầu.",
    },
    "tip_start_need_both": {
        "en": "Log in and choose an Excel file to enable Start.",
        "vi": "Đăng nhập và chọn file Excel để bật nút Bắt đầu.",
    },
    "tip_start_busy": {
        "en": "An operation is already running.",
        "vi": "Đang có một thao tác chạy.",
    },
    "msg_not_validated_warn": {
        "en": "⚠ This file has not been validated yet.\n\n",
        "vi": "⚠ File này chưa được kiểm tra.\n\n",
    },
    "msg_validation_had_errors": {
        "en": "⚠ Validation found {n} invalid row(s) — those rows will fail.\n\n",
        "vi": "⚠ Kiểm tra phát hiện {n} hàng không hợp lệ — các hàng đó sẽ thất bại.\n\n",
    },
    "log_token_low": {
        "en": "⚠ Login token expires soon — re-login if your batch is large.",
        "vi": "⚠ Token đăng nhập sắp hết hạn — đăng nhập lại nếu lô dữ liệu lớn.",
    },
    "log_token_expired": {
        "en": "⛔ Login token expired — please log in again.",
        "vi": "⛔ Token đăng nhập đã hết hạn — vui lòng đăng nhập lại.",
    },
    # close while running
    "dlg_still_stopping": {
        "en": "Operation still stopping",
        "vi": "Đang dừng thao tác",
    },
    "msg_still_stopping": {
        "en": "An operation is still stopping — please wait a moment and try again.",
        "vi": "Một thao tác đang dừng — vui lòng chờ một lúc và thử lại.",
    },
    # preferences dialog
    "dlg_prefs_title": {"en": "Preferences", "vi": "Cài đặt"},
    "tab_general": {"en": "General", "vi": "Chung"},
    "tab_record_defaults": {"en": "Record defaults", "vi": "Cài đặt hồ sơ"},
    "grp_run_defaults": {
        "en": "Default run settings (loaded at startup)",
        "vi": "Cài đặt chạy mặc định (nạp khi khởi động)",
    },
    "grp_app_settings": {"en": "Application", "vi": "Ứng dụng"},
    "lbl_delay_rows": {"en": "Delay between rows:", "vi": "Độ trễ giữa các hàng:"},
    "lbl_row_limit": {"en": "Row limit:", "vi": "Giới hạn hàng:"},
    "spin_all_rows": {"en": "0 (all rows)", "vi": "0 (tất cả hàng)"},
    "chk_dryrun_default": {
        "en": "Dry-run by default (don't send)",
        "vi": "Chạy thử mặc định (không gửi)",
    },
    "lbl_language": {"en": "Language:", "vi": "Ngôn ngữ:"},
    "tip_language": {
        "en": "Changes the interface language immediately when you press Apply or OK.",
        "vi": "Đổi ngôn ngữ giao diện ngay khi bấm Áp dụng hoặc OK.",
    },
    "chk_check_updates": {
        "en": "Check for new versions at startup",
        "vi": "Kiểm tra phiên bản mới khi khởi động",
    },
    "tip_check_updates": {
        "en": (
            "Quietly asks GitHub for the latest release once per launch. "
            "Downloading and installing always needs your click to start."
        ),
        "vi": (
            "Âm thầm hỏi GitHub về bản phát hành mới nhất mỗi lần mở. "
            "Tải về và cài đặt luôn cần bạn bấm để bắt đầu."
        ),
    },
    "update_available": {
        "en": "A new version is available: {version}",
        "vi": "Đã có phiên bản mới: {version}",
    },
    "update_link": {"en": "Download", "vi": "Tải về"},
    "update_download_install": {"en": "Download && Install", "vi": "Tải về && Cài đặt"},
    "update_downloading": {
        "en": "Downloading update… {pct}%",
        "vi": "Đang tải bản cập nhật… {pct}%",
    },
    "update_downloaded": {
        "en": "Update downloaded and verified.",
        "vi": "Đã tải và xác minh xong bản cập nhật.",
    },
    "update_verify_failed": {
        "en": "The downloaded update failed verification — try again, or download manually.",
        "vi": "Bản cập nhật tải về không xác minh được — hãy thử lại hoặc tải thủ công.",
    },
    "update_download_failed": {
        "en": "Couldn't download the update — try again, or download manually.",
        "vi": "Không tải được bản cập nhật — hãy thử lại hoặc tải thủ công.",
    },
    "update_install_win_confirm_title": {
        "en": "Install update",
        "vi": "Cài đặt bản cập nhật",
    },
    "update_install_win_confirm": {
        "en": ("The installer will open and this app will close to finish updating.\n\nContinue?"),
        "vi": ("Trình cài đặt sẽ mở và ứng dụng này sẽ đóng để hoàn tất cập nhật.\n\nTiếp tục?"),
    },
    "update_install_mac_hint": {
        "en": "Drag HSSK Tools onto Applications to replace the old version, then reopen it.",
        "vi": "Kéo HSSK Tools vào thư mục Applications để thay bản cũ, rồi mở lại ứng dụng.",
    },
    "update_open_in_browser": {"en": "Open in browser", "vi": "Mở trong trình duyệt"},
    "note_record_defaults": {
        "en": (
            "These values are stamped on every uploaded record when the matching Excel "
            "column is blank or absent. Per-row Excel values always take precedence."
        ),
        "vi": (
            "Các giá trị này được gán vào mỗi hồ sơ tải lên khi cột Excel "
            "tương ứng bị trống hoặc thiếu. Giá trị từng hàng trong Excel luôn được ưu tiên."
        ),
    },
    "grp_record_defaults": {
        "en": "medicalRecordInfo defaults",
        "vi": "Giá trị mặc định của hồ sơ",
    },
    "msg_mapping_error_prefs": {
        "en": (
            "Cannot load the mapping file: {exc}\n\n"
            "Record defaults cannot be edited until the mapping file is valid. "
            "Fix it via 'Open mapping' in the main window, or delete the file so the app "
            "recreates it from the bundled example on the next start."
        ),
        "vi": (
            "Không thể tải file mapping: {exc}\n\n"
            "Chưa thể chỉnh sửa giá trị mặc định hồ sơ cho đến khi file mapping hợp lệ. "
            "Hãy sửa file bằng nút 'Mở file mapping' ở cửa sổ chính, hoặc xoá file đó để "
            "ứng dụng tạo lại từ file mẫu ở lần mở tiếp theo."
        ),
    },
    "tip_facility_locked": {
        "en": "Locked to the logged-in account — it cannot be edited here.",
        "vi": "Gắn theo tài khoản đang đăng nhập — không thể sửa tại đây.",
    },
    "btn_ok": {"en": "OK", "vi": "OK"},
    "btn_cancel": {"en": "Cancel", "vi": "Hủy"},
    "btn_apply": {"en": "Apply", "vi": "Áp dụng"},
    "btn_restore_run_defaults": {"en": "Reset run settings", "vi": "Khôi phục cài đặt chạy"},
    "btn_restore_record_defaults": {"en": "Reset record defaults", "vi": "Khôi phục cài đặt hồ sơ"},
    "tip_restore_run": {
        "en": (
            "Reset delay, row limit, dry-run and update check on this tab to factory values. "
            "Language is kept. Nothing is saved until you press Apply or OK."
        ),
        "vi": (
            "Đặt lại độ trễ, giới hạn hàng, chạy thử và kiểm tra cập nhật trong tab này về "
            "giá trị gốc. Ngôn ngữ được giữ nguyên. Chưa có gì được lưu cho đến khi bấm "
            "Áp dụng hoặc OK."
        ),
    },
    "tip_restore_record": {
        "en": (
            "Reload the values on this tab from the bundled example file. "
            "Nothing is saved until you press Apply or OK."
        ),
        "vi": (
            "Nạp lại các giá trị trong tab này từ file mẫu đi kèm. "
            "Chưa có gì được lưu cho đến khi bấm Áp dụng hoặc OK."
        ),
    },
    "msg_prefs_applied": {"en": "Settings saved.", "vi": "Đã lưu cài đặt."},
    "msg_prefs_save_failed": {
        "en": (
            "Could not save record defaults: {exc}\n"
            "Your edits are still here — fix the problem and press Apply again, "
            "or press Cancel to discard."
        ),
        "vi": (
            "Không thể lưu giá trị mặc định hồ sơ: {exc}\n"
            "Các thay đổi vẫn còn ở đây — hãy khắc phục rồi bấm Áp dụng lại, "
            "hoặc bấm Hủy để bỏ."
        ),
    },
    "dlg_discard_title": {"en": "Unsaved changes", "vi": "Thay đổi chưa lưu"},
    "msg_discard_changes": {
        "en": "You have unsaved changes in Settings.\nDiscard them?",
        "vi": "Bạn có thay đổi chưa lưu trong Cài đặt.\nBỏ các thay đổi này?",
    },
    "btn_discard": {"en": "Discard changes", "vi": "Bỏ thay đổi"},
    "btn_keep_editing": {"en": "Keep editing", "vi": "Tiếp tục chỉnh sửa"},
    # run-control tooltips
    "tip_mode": {
        "en": (
            "Create new records, Update existing ones, or Delete existing ones "
            "(Update/Delete need a medicalRecordId column)."
        ),
        "vi": (
            "Tạo hồ sơ mới, Cập nhật hoặc Xoá hồ sơ có sẵn (Cập nhật/Xoá cần cột medicalRecordId)."
        ),
    },
    "tip_delay": {
        "en": "Seconds to wait between rows. Increase this if the server rate-limits you.",
        "vi": "Số giây chờ giữa các dòng. Tăng lên nếu máy chủ giới hạn tốc độ.",
    },
    "tip_limit": {
        "en": "Process at most this many rows (0 = all rows). Handy for a quick test run.",
        "vi": "Chỉ xử lý tối đa số dòng này (0 = tất cả). Tiện cho lần chạy thử nhanh.",
    },
    "tip_dryrun": {
        "en": "When ticked, nothing is sent — payloads are built and written for inspection only.",
        "vi": "Khi bật, không gửi gì cả — chỉ tạo và ghi dữ liệu để kiểm tra.",
    },
    "tip_choose_excel": {
        "en": "Choose the Excel file to upload.",
        "vi": "Chọn file Excel cần tải lên.",
    },
    "tip_validate": {
        "en": "Check the file offline — nothing is sent.",
        "vi": "Kiểm tra file ngoại tuyến — không gửi gì cả.",
    },
    "tip_stop": {
        "en": "Stop after the row currently being processed.",
        "vi": "Dừng sau dòng đang xử lý.",
    },
    "tip_start_ready": {
        "en": "Start processing the selected file.",
        "vi": "Bắt đầu xử lý file đã chọn.",
    },
    # labeled result counters (progress row); short words — they sit next to the ETA
    "counter_ok": {"en": "ok", "vi": "thành công"},
    "counter_skipped": {"en": "skipped", "vi": "bỏ qua"},
    "counter_failed": {"en": "failed", "vi": "lỗi"},
    "counter_aborted": {"en": "aborted", "vi": "dừng"},
    "counter_valid": {"en": "valid", "vi": "hợp lệ"},
    "counter_warns": {"en": "warnings", "vi": "cảnh báo"},
    "counter_invalid": {"en": "invalid", "vi": "không hợp lệ"},
    # results filter / table tools
    "ph_filter": {"en": "Filter rows…", "vi": "Lọc dòng…"},
    "chk_problems_only": {"en": "Problems only", "vi": "Chỉ dòng có vấn đề"},
    "filter_all_statuses": {"en": "All statuses", "vi": "Tất cả trạng thái"},
    "tip_status_filter": {
        "en": "Show only rows with this status.",
        "vi": "Chỉ hiện các dòng có trạng thái này.",
    },
    "btn_clear_log": {"en": "Clear log", "vi": "Xoá nhật ký"},
    "empty_results": {
        "en": "Choose an Excel file and Validate, or Start a dry-run.",
        "vi": "Chọn file Excel rồi Kiểm tra, hoặc Chạy thử.",
    },
    "btn_export_csv": {"en": "Export CSV…", "vi": "Xuất CSV…"},
    "ctx_copy_cell": {"en": "Copy cell", "vi": "Sao chép ô"},
    "ctx_copy_row": {"en": "Copy row", "vi": "Sao chép dòng"},
    "ctx_copy_all": {"en": "Copy all visible", "vi": "Sao chép tất cả đang hiện"},
    "dlg_export_csv_title": {"en": "Export results to CSV", "vi": "Xuất kết quả ra CSV"},
    "filter_csv": {"en": "CSV files (*.csv)", "vi": "File CSV (*.csv)"},
    # legal dialog
    "legal_consent_title": {
        "en": "HSSK Tools — Terms & Conditions",
        "vi": "HSSK Tools — Điều khoản & Điều kiện",
    },
    "legal_info_title": {
        "en": "HSSK Tools — Legal & Security",
        "vi": "HSSK Tools — Pháp lý & Bảo mật",
    },
    "tab_terms": {"en": "Terms of Use", "vi": "Điều khoản sử dụng"},
    "tab_privacy": {"en": "Privacy Policy", "vi": "Chính sách bảo mật"},
    "tab_security": {"en": "Security", "vi": "Bảo mật"},
    "btn_accept": {"en": "Accept", "vi": "Chấp nhận"},
    "btn_decline": {"en": "Decline", "vi": "Từ chối"},
    # preferences — record default field labels
    "rec_normal_desc_value": {"en": "Normal description", "vi": "Mô tả bình thường"},
    "rec_doctorName": {"en": "Doctor (default)", "vi": "Bác sĩ (mặc định)"},
    "rec_healthfacilitiesId": {"en": "Health facility ID", "vi": "Mã cơ sở y tế"},
    "rec_typeOfExamination": {"en": "Examination type code", "vi": "Mã hình thức khám"},
    "rec_reasonCode": {"en": "Examinee category code", "vi": "Mã đối tượng khám"},
    "rec_reasonsMedicalexamination": {"en": "Reason for examination", "vi": "Lý do khám"},
    "rec_symptoms": {"en": "Default medical history", "vi": "Bệnh sử mặc định"},
    "rec_treatmentDayNumber": {"en": "Treatment days", "vi": "Số ngày điều trị"},
    "rec_diagnosesDischarge": {"en": "Default conclusion", "vi": "Kết luận mặc định"},
    "rec_diagnosesDischargeList": {
        "en": "Comorbidities list (comma-separated)",
        "vi": "Danh sách bệnh kèm (cách nhau bởi dấu phẩy)",
    },
    "rec_noteDisease": {"en": "Default monitored condition", "vi": "Bệnh theo dõi mặc định"},
    "rec_treatmentDirection": {"en": "Default treatment advice", "vi": "Tư vấn điều trị mặc định"},
    "rec_treatmentResultId": {"en": "Examination result code", "vi": "Mã kết quả khám"},
    "rec_dischargeStatusId": {"en": "Discharge status code", "vi": "Mã tình trạng ra viện"},
    "ph_not_logged_in": {"en": "(not logged in)", "vi": "(chưa đăng nhập)"},
    "ph_from_account": {"en": "(from account: {name})", "vi": "(từ tài khoản: {name})"},
}


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in ("en", "vi") else "vi"


def tr(key: str) -> str:
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(_lang) or entry.get("en") or key
