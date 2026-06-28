"""Minimal two-language (Vietnamese / English) translation support."""

from __future__ import annotations

_lang = "vi"

_STRINGS: dict[str, dict[str, str]] = {
    # window / groups
    "window_title": {
        "en": "HSSK Tools v{version} — Health checkup uploader",
        "vi": "HSSK Tools v{version} — Tải lên dữ liệu khám sức khoẻ",
    },
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
    "menu_settings": {"en": "Settings", "vi": "Cài đặt"},
    "menu_settings_action": {"en": "Settings…", "vi": "Cài đặt…"},
    "menu_help": {"en": "Help", "vi": "Trợ giúp"},
    "menu_user_guide": {"en": "User Guide", "vi": "Hướng dẫn sử dụng"},
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
    "msg_validation_summary": {
        "en": "{valid} valid, {invalid} invalid, {warns} warnings ({total} rows).",
        "vi": "{valid} hợp lệ, {invalid} không hợp lệ, {warns} cảnh báo ({total} hàng).",
    },
    "msg_no_issues": {"en": "No issues found.", "vi": "Không có lỗi."},
    "val_status_invalid": {"en": "INVALID", "vi": "Không hợp lệ"},
    "val_status_warning": {"en": "WARNING", "vi": "Cảnh báo"},
    # run result statuses (results table)
    "status_CREATED": {"en": "Created", "vi": "Đã tạo"},
    "status_UPDATED": {"en": "Updated", "vi": "Đã cập nhật"},
    "status_DRY_RUN_OK": {"en": "Dry-run OK", "vi": "Chạy thử OK"},
    "status_SKIPPED_ALREADY": {"en": "Skipped (already sent)", "vi": "Bỏ qua (đã gửi)"},
    "status_INVALID": {"en": "Invalid", "vi": "Không hợp lệ"},
    "status_NO_PATIENT": {"en": "No patient found", "vi": "Không thấy bệnh nhân"},
    "status_MULTI_MATCH": {"en": "Multiple matches", "vi": "Trùng nhiều bệnh nhân"},
    "status_FAILED": {"en": "Failed", "vi": "Thất bại"},
    "status_AUTH_EXPIRED": {"en": "Token expired", "vi": "Token hết hạn"},
    "status_RATE_LIMITED": {"en": "Server busy", "vi": "Máy chủ bận"},
    # engine-authored row messages (results table Message column). Raw API/exception and
    # per-cell coercion detail is passed through untranslated.
    "msg_row_created": {"en": "Created", "vi": "Đã tạo"},
    "msg_row_updated": {"en": "Updated", "vi": "Đã cập nhật"},
    "msg_row_dryrun": {"en": "Payload built (not sent)", "vi": "Đã dựng dữ liệu (chưa gửi)"},
    "msg_row_already": {"en": "Already processed", "vi": "Đã xử lý trước đó"},
    "msg_row_id_blank": {"en": "Identifier is blank", "vi": "Mã định danh trống"},
    "msg_row_recordid_blank": {"en": "medicalRecordId is blank", "vi": "medicalRecordId trống"},
    "msg_row_coercion": {"en": "Coercion error: ", "vi": "Lỗi chuyển đổi: "},
    "msg_row_fetch": {"en": "Fetch detail: ", "vi": "Lỗi lấy chi tiết: "},
    # individual coerce error/warning fragments (variable tails are field names / raw values)
    "msg_coerce_missing_col": {
        "en": "missing required column ",
        "vi": "thiếu cột bắt buộc ",
    },
    "msg_coerce_cannot_parse": {
        "en": ": cannot parse ",
        "vi": ": không thể đọc ",
    },
    "msg_coerce_as_type": {"en": " as ", "vi": " thành "},
    "msg_coerce_range": {
        "en": " outside expected range ",
        "vi": " nằm ngoài phạm vi ",
    },
    "msg_coerce_date_before": {"en": " is before ", "vi": " trước "},
    # mode combo (run box)
    "lbl_mode": {"en": "Mode:", "vi": "Chế độ:"},
    "mode_create": {"en": "Create", "vi": "Tạo mới"},
    "mode_update": {"en": "Update", "vi": "Cập nhật"},
    "btn_start_update_live": {"en": "⚠  UPDATE live records", "vi": "⚠  CẬP NHẬT DỮ LIỆU THẬT"},
    "banner_production_update": {
        "en": "⚠️  PRODUCTION — this UPDATES LIVE medical records",
        "vi": "⚠️  PRODUCTION — đang CẬP NHẬT hồ sơ y tế THẬT",
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
    # run complete
    "dlg_run_complete": {"en": "Run complete", "vi": "Hoàn thành"},
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
    "tab_run_defaults": {"en": "Run defaults", "vi": "Cài đặt chạy"},
    "tab_record_defaults": {"en": "Record defaults", "vi": "Cài đặt hồ sơ"},
    "grp_run_defaults": {
        "en": "Saved run defaults (applied on each launch)",
        "vi": "Cài đặt chạy mặc định (áp dụng mỗi lần khởi động)",
    },
    "lbl_delay_rows": {"en": "Delay between rows:", "vi": "Độ trễ giữa các hàng:"},
    "lbl_row_limit": {"en": "Row limit:", "vi": "Giới hạn hàng:"},
    "spin_all_rows": {"en": "0 (all rows)", "vi": "0 (tất cả hàng)"},
    "chk_dryrun_default": {
        "en": "Dry-run by default (don't send)",
        "vi": "Chạy thử mặc định (không gửi)",
    },
    "lbl_language": {"en": "Language:", "vi": "Ngôn ngữ:"},
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
            "Cannot load mapping file: {exc}\n\n"
            "Record defaults cannot be edited until the mapping is valid.\n"
            "Click 'Restore defaults' to recover from the bundled example."
        ),
        "vi": (
            "Không thể tải file mapping: {exc}\n\n"
            "Không thể chỉnh sửa giá trị mặc định hồ sơ cho đến khi mapping hợp lệ.\n"
            "Nhấn 'Khôi phục mặc định' để khôi phục từ file mẫu đi kèm."
        ),
    },
    "btn_restore_defaults": {"en": "Restore defaults", "vi": "Khôi phục mặc định"},
    "dlg_run_defaults_saved": {"en": "Run defaults saved", "vi": "Đã lưu cài đặt chạy"},
    "msg_run_defaults_saved": {
        "en": (
            "Run defaults were saved.\n\n"
            "Record defaults could not be saved because the mapping file is unreadable. "
            "Click 'Restore defaults' to recover from the bundled example."
        ),
        "vi": (
            "Đã lưu cài đặt chạy.\n\n"
            "Không thể lưu giá trị mặc định hồ sơ vì file mapping không đọc được. "
            "Nhấn 'Khôi phục mặc định' để khôi phục từ file mẫu đi kèm."
        ),
    },
    "dlg_save_error": {"en": "Save error", "vi": "Lỗi lưu"},
    # run-control tooltips
    "tip_mode": {
        "en": "Create new records, or Update existing ones (needs a medicalRecordId column).",
        "vi": "Tạo hồ sơ mới, hoặc Cập nhật hồ sơ có sẵn (cần cột medicalRecordId).",
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
    # results filter / table tools
    "ph_filter": {"en": "Filter rows…", "vi": "Lọc dòng…"},
    "chk_problems_only": {"en": "Problems only", "vi": "Chỉ dòng có vấn đề"},
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
