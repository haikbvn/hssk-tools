"""Legal information dialog: Terms of Use, Privacy Policy, Security."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .i18n import _lang, tr

_TERMS_HTML = """
<h3>Terms of Use</h3>
<p>HSSK Tools is internal software for authorised clinic staff operating under a valid
account on the national health-record system (<b>hososuckhoe.com.vn</b>). By using this
application you agree to the following conditions.</p>

<h4>Authorised Use</h4>
<ul>
  <li>Use this tool only with credentials that belong to your facility and that you are
      lawfully authorised to operate.</li>
  <li>Do not process records belonging to facilities other than your own, or for any
      purpose outside routine health-checkup data entry.</li>
  <li>Each push creates permanent records in the national system. Verify your Excel data
      before switching off Dry-run mode.</li>
</ul>

<h4>Responsibilities</h4>
<ul>
  <li>You are responsible for the accuracy of the data you upload.</li>
  <li>Do not share login credentials or leave an active session unattended.</li>
  <li>Report unexpected behaviour or suspected misuse to your IT administrator immediately.</li>
</ul>

<h4>No Warranty</h4>
<p>This software is provided as-is for internal operational use. It is not a certified
medical device. The tool relies on the undocumented internal API of hososuckhoe.com.vn;
API changes by the national system operator may require updates to this application.</p>

<h4>Purchases &amp; Refunds</h4>
<p>HSSK Tools requires a purchased license key to run. Purchases are processed by
<a href="https://polar.sh">Polar</a>, acting as merchant of record; your payment details are
handled entirely by Polar and are never seen by this application beyond the license key it
issues.</p>
<ul>
  <li>Refunds are handled by Polar under its own terms — considered on a discretionary basis,
      typically within 60 days of purchase. See Polar's
      <a href="https://polar.sh/legal/checkout-buyer-terms">Checkout Buyer Terms</a> for the
      terms that govern your purchase.</li>
  <li>If a license is refunded, revoked, or expires, the application will stop working —
      including Dry-run and validation — until a valid license key is reinstalled.</li>
  <li>License keys are issued per buyer for use at your facility; do not share a purchased key
      outside your organisation.</li>
</ul>
"""

_TERMS_HTML_VI = """
<h3>Điều khoản sử dụng</h3>
<p>HSSK Tools là phần mềm nội bộ dành cho nhân viên phòng khám được uỷ quyền, sử dụng
tài khoản hợp lệ trên hệ thống hồ sơ sức khoẻ quốc gia (<b>hososuckhoe.com.vn</b>).
Khi sử dụng ứng dụng này, bạn đồng ý với các điều khoản sau.</p>

<h4>Sử dụng hợp lệ</h4>
<ul>
  <li>Chỉ sử dụng công cụ này với thông tin đăng nhập thuộc cơ sở của bạn và bạn
      được uỷ quyền hợp pháp để vận hành.</li>
  <li>Không xử lý hồ sơ thuộc cơ sở khác hoặc cho bất kỳ mục đích nào ngoài
      nhập liệu khám sức khoẻ thường quy.</li>
  <li>Mỗi lần đẩy dữ liệu sẽ tạo ra hồ sơ vĩnh viễn trong hệ thống quốc gia.
      Hãy kiểm tra dữ liệu Excel trước khi tắt chế độ Chạy thử.</li>
</ul>

<h4>Trách nhiệm</h4>
<ul>
  <li>Bạn chịu trách nhiệm về tính chính xác của dữ liệu mình tải lên.</li>
  <li>Không chia sẻ thông tin đăng nhập hoặc để phiên làm việc hoạt động mà không
      có người giám sát.</li>
  <li>Báo cáo ngay cho quản trị viên IT của bạn nếu phát hiện hành vi bất thường
      hoặc nghi ngờ lạm dụng.</li>
</ul>

<h4>Không bảo hành</h4>
<p>Phần mềm này được cung cấp nguyên trạng cho mục đích sử dụng nội bộ. Đây không
phải là thiết bị y tế được chứng nhận. Công cụ phụ thuộc vào API nội bộ chưa được
tài liệu hoá của hososuckhoe.com.vn; các thay đổi API từ phía vận hành hệ thống quốc
gia có thể yêu cầu cập nhật ứng dụng này.</p>

<h4>Mua hàng &amp; Hoàn tiền</h4>
<p>HSSK Tools yêu cầu mã giấy phép đã mua để có thể chạy. Giao dịch mua được xử lý bởi
<a href="https://polar.sh">Polar</a> với vai trò đơn vị bán hàng chính thức (merchant of
record); thông tin thanh toán của bạn do Polar xử lý hoàn toàn và ứng dụng này không bao giờ
nhìn thấy, ngoài mã giấy phép mà Polar cấp.</p>
<ul>
  <li>Việc hoàn tiền do Polar xử lý theo điều khoản riêng của họ — được xem xét theo từng
      trường hợp, thường trong vòng 60 ngày kể từ khi mua. Xem
      <a href="https://polar.sh/legal/checkout-buyer-terms">Điều khoản mua hàng của Polar</a>
      (Checkout Buyer Terms) để biết điều khoản đầy đủ áp dụng cho giao dịch mua của bạn.</li>
  <li>Nếu giấy phép bị hoàn tiền, thu hồi hoặc hết hạn, ứng dụng sẽ ngừng hoạt động — kể cả
      chế độ Chạy thử và xác thực dữ liệu — cho đến khi cài đặt lại mã giấy phép hợp lệ.</li>
  <li>Mã giấy phép được cấp cho từng người mua để sử dụng tại cơ sở của bạn; không chia sẻ
      mã đã mua ra ngoài tổ chức của bạn.</li>
</ul>
"""

_PRIVACY_HTML = """
<h3>Privacy Policy</h3>
<p>HSSK Tools processes patient personally identifiable information (PII) solely to
upload health-checkup records to the national system.</p>

<h4>Data Processed</h4>
<ul>
  <li><b>Patient PII</b> — full names, national ID / CCCD numbers, health insurance
      numbers, phone numbers, and examination results read from the Excel file.</li>
  <li><b>Authentication credentials</b> — a bearer JWT token obtained after login through
      the embedded browser; stored locally in a restricted-permission file.</li>
  <li><b>Operator profile</b> — display name and facility ID fetched once at login and
      cached locally.</li>
</ul>

<h4>How Data Is Used</h4>
<ul>
  <li>Patient data is read from your Excel file, validated, and transmitted directly to
      <b>hososuckhoe.com.vn</b> via HTTPS. No data is sent to any other server.</li>
  <li>A local ledger records which (identifier, exam-date) pairs have been pushed,
      enabling safe re-runs. It contains identifiers but not full patient records.</li>
  <li>Run reports saved to the local user-data directory contain PII and should be
      managed per your clinic's data-retention policy.</li>
</ul>

<h4>Data Storage</h4>
<ul>
  <li>All data remains on the local workstation and on hososuckhoe.com.vn. No cloud
      storage, analytics, or telemetry is performed.</li>
  <li>The token file is stored with owner-only permissions (Unix: 600; Windows: user ACL).</li>
</ul>

<h4>Your Obligations</h4>
<p>As operator, you are responsible for handling patient data in accordance with
Vietnamese law on health information and personal data protection
(Nghị định 13/2023/NĐ-CP and relevant Ministry of Health regulations).</p>
"""

_PRIVACY_HTML_VI = """
<h3>Chính sách bảo mật</h3>
<p>HSSK Tools xử lý thông tin cá nhân (PII) của bệnh nhân chỉ nhằm mục đích tải
hồ sơ khám sức khoẻ lên hệ thống quốc gia.</p>

<h4>Dữ liệu được xử lý</h4>
<ul>
  <li><b>PII của bệnh nhân</b> — họ tên đầy đủ, số CCCD/CMND, số bảo hiểm y tế,
      số điện thoại và kết quả khám đọc từ file Excel.</li>
  <li><b>Thông tin xác thực</b> — token JWT thu được sau khi đăng nhập qua trình
      duyệt nhúng; được lưu trữ cục bộ trong file có quyền hạn chế.</li>
  <li><b>Hồ sơ người vận hành</b> — tên hiển thị và mã cơ sở y tế lấy một lần
      khi đăng nhập và lưu cache cục bộ.</li>
</ul>

<h4>Cách dữ liệu được sử dụng</h4>
<ul>
  <li>Dữ liệu bệnh nhân được đọc từ file Excel của bạn, xác thực và truyền trực
      tiếp đến <b>hososuckhoe.com.vn</b> qua HTTPS. Không có dữ liệu nào được gửi
      đến máy chủ khác.</li>
  <li>Một sổ cái cục bộ ghi lại các cặp (mã định danh, ngày khám) đã được đẩy,
      cho phép chạy lại an toàn. Nó chứa mã định danh nhưng không chứa toàn bộ
      hồ sơ bệnh nhân.</li>
  <li>Báo cáo chạy được lưu vào thư mục dữ liệu người dùng cục bộ có chứa PII
      và cần được quản lý theo chính sách lưu giữ dữ liệu của phòng khám.</li>
</ul>

<h4>Lưu trữ dữ liệu</h4>
<ul>
  <li>Tất cả dữ liệu đều ở trên máy trạm cục bộ và trên hososuckhoe.com.vn.
      Không thực hiện lưu trữ đám mây, phân tích hay telemetry.</li>
  <li>File token được lưu với quyền chỉ dành cho chủ sở hữu (Unix: 600;
      Windows: user ACL).</li>
</ul>

<h4>Trách nhiệm của bạn</h4>
<p>Là người vận hành, bạn chịu trách nhiệm xử lý dữ liệu bệnh nhân theo quy định
pháp luật Việt Nam về thông tin y tế và bảo vệ dữ liệu cá nhân
(Nghị định 13/2023/NĐ-CP và các quy định liên quan của Bộ Y tế).</p>
"""

_SECURITY_HTML = """
<h3>Security</h3>
<p>This page summarises the security measures built into HSSK Tools and the
responsibilities that remain with you as the operator.</p>

<h4>Authentication Token Handling</h4>
<ul>
  <li>Your login token (JWT) is captured from the embedded Chromium browser and saved
      locally with restrictive permissions (Unix: 600; Windows: user-only ACL).
      It is never transmitted to any server other than hososuckhoe.com.vn.</li>
  <li>Token expiry is decoded locally and shown in the status bar. The application
      will not attempt a push with a token it knows to be expired.</li>
  <li>If the server returns 401 Unauthorized during a run, the batch is aborted
      cleanly — no partial or corrupted records are created.</li>
</ul>

<h4>Data in Transit</h4>
<ul>
  <li>All communication with hososuckhoe.com.vn uses HTTPS (TLS).</li>
  <li>No patient data leaves the machine except as part of the authorised push to
      hososuckhoe.com.vn.</li>
</ul>

<h4>Rate Limiting and Server Safety</h4>
<ul>
  <li>Requests are sent sequentially with a configurable delay (default 1 s) plus
      random jitter to avoid overloading the national server.</li>
  <li>Exponential backoff is applied on 429 and 5xx errors. A circuit breaker aborts
      the batch after repeated failures.</li>
</ul>

<h4>Local File Security</h4>
<ul>
  <li>Excel input files, result spreadsheets, run logs, and the token file all contain
      sensitive data. Store them on encrypted volumes with appropriate access controls.</li>
  <li>Do not copy these files to shared drives, email, or cloud storage unless your
      clinic's security policy explicitly permits it.</li>
</ul>

<h4>Responsible Use</h4>
<ul>
  <li>Lock or log out of your workstation when stepping away during an active session.</li>
  <li>If you suspect compromised credentials, log out of hososuckhoe.com.vn immediately
      and notify your IT administrator.</li>
  <li>Keep the application updated — security-relevant changes are noted in the CHANGELOG.</li>
</ul>
"""

_SECURITY_HTML_VI = """
<h3>Bảo mật</h3>
<p>Trang này tóm tắt các biện pháp bảo mật được tích hợp trong HSSK Tools và
các trách nhiệm còn lại của bạn với tư cách là người vận hành.</p>

<h4>Xử lý token xác thực</h4>
<ul>
  <li>Token đăng nhập (JWT) của bạn được thu từ trình duyệt Chromium nhúng và lưu
      cục bộ với quyền hạn chế (Unix: 600; Windows: user-only ACL). Token không
      bao giờ được truyền đến máy chủ nào khác ngoài hososuckhoe.com.vn.</li>
  <li>Thời hạn token được giải mã cục bộ và hiển thị trên thanh trạng thái. Ứng
      dụng sẽ không thử đẩy dữ liệu với token đã biết là hết hạn.</li>
  <li>Nếu máy chủ trả về 401 Unauthorized trong khi chạy, batch sẽ bị dừng
      một cách sạch sẽ — không có hồ sơ nào bị tạo một phần hoặc bị hỏng.</li>
</ul>

<h4>Dữ liệu trong quá trình truyền</h4>
<ul>
  <li>Tất cả giao tiếp với hososuckhoe.com.vn sử dụng HTTPS (TLS).</li>
  <li>Không có dữ liệu bệnh nhân nào rời khỏi máy tính ngoại trừ phần đẩy được
      uỷ quyền lên hososuckhoe.com.vn.</li>
</ul>

<h4>Giới hạn tốc độ và an toàn máy chủ</h4>
<ul>
  <li>Các yêu cầu được gửi tuần tự với độ trễ có thể cấu hình (mặc định 1 giây)
      cộng với jitter ngẫu nhiên để tránh quá tải máy chủ quốc gia.</li>
  <li>Exponential backoff được áp dụng với lỗi 429 và 5xx. Circuit breaker dừng
      batch sau nhiều lần lỗi liên tiếp.</li>
</ul>

<h4>Bảo mật file cục bộ</h4>
<ul>
  <li>File Excel đầu vào, bảng kết quả, nhật ký chạy và file token đều chứa dữ
      liệu nhạy cảm. Lưu trữ chúng trên ổ đĩa mã hoá với kiểm soát truy cập phù hợp.</li>
  <li>Không sao chép các file này lên ổ đĩa dùng chung, email hay lưu trữ đám mây
      trừ khi chính sách bảo mật của phòng khám cho phép rõ ràng.</li>
</ul>

<h4>Sử dụng có trách nhiệm</h4>
<ul>
  <li>Khoá hoặc đăng xuất khỏi máy trạm khi rời đi trong phiên làm việc đang hoạt động.</li>
  <li>Nếu nghi ngờ thông tin đăng nhập bị xâm phạm, hãy đăng xuất khỏi
      hososuckhoe.com.vn ngay lập tức và thông báo cho quản trị viên IT.</li>
  <li>Giữ ứng dụng được cập nhật — các thay đổi liên quan đến bảo mật được ghi chú
      trong CHANGELOG.</li>
</ul>
"""


class LegalDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        tab: int = 0,
        consent: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("legal_consent_title") if consent else tr("legal_info_title"))
        self.setMinimumSize(680, 480)

        vi = _lang == "vi"
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(_make_browser(_TERMS_HTML_VI if vi else _TERMS_HTML), tr("tab_terms"))
        tabs.addTab(_make_browser(_PRIVACY_HTML_VI if vi else _PRIVACY_HTML), tr("tab_privacy"))
        tabs.addTab(_make_browser(_SECURITY_HTML_VI if vi else _SECURITY_HTML), tr("tab_security"))
        tabs.setCurrentIndex(tab)
        layout.addWidget(tabs)

        if consent:
            buttons = QDialogButtonBox()
            buttons.addButton(tr("btn_accept"), QDialogButtonBox.ButtonRole.AcceptRole)
            buttons.addButton(tr("btn_decline"), QDialogButtonBox.ButtonRole.RejectRole)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
        else:
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def _make_browser(html: str) -> QTextBrowser:
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setHtml(html)
    return browser
