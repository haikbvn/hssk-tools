"""In-app User Guide dialog (Help → User Guide), bilingual like the legal dialog.

The long-form guide body lives here as module constants (one per language) rather than in
``i18n.py``, which holds only short UI strings — mirroring how the legal text is stored in
``legal_dialog.py``. The active language is read the same way the legal dialog reads it.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .i18n import _lang, tr

_GUIDE_HTML = """
<h2>HSSK Tools — User Guide</h2>
<p>This guide walks you through pushing health-checkup data from an Excel file to
<b>hososuckhoe.com.vn</b>, step by step. The main window has three numbered sections —
<b>1 · Login</b>, <b>2 · Data</b>, <b>3 · Run</b> — and a Results area; this guide follows the
same order.</p>

<p><b>Contents</b></p>
<ol>
  <li><a href="#overview">Overview &amp; authorised use</a></li>
  <li><a href="#template">Get a blank Excel template</a></li>
  <li><a href="#fill">Fill in the Excel file</a></li>
  <li><a href="#login">Log in</a></li>
  <li><a href="#validate">Validate (offline check)</a></li>
  <li><a href="#dryrun">Dry-run first</a></li>
  <li><a href="#push">Push live records</a></li>
  <li><a href="#results">Read the results</a></li>
  <li><a href="#rerun">Re-running safely</a></li>
  <li><a href="#modes">Create vs Update mode</a></li>
  <li><a href="#prefs">Preferences</a></li>
  <li><a href="#mapping">Column mapping</a></li>
  <li><a href="#trouble">Troubleshooting</a></li>
  <li><a href="#files">Where your files live &amp; privacy</a></li>
</ol>

<a name="overview"></a><h3>1 · Overview &amp; authorised use</h3>
<p>HSSK Tools reads patient rows from an Excel file and, for each row, creates a health-examination
record on <a href="https://hososuckhoe.com.vn">hososuckhoe.com.vn</a> using
<b>your own authorised account</b>. Every live push creates a <b>permanent</b> record in the
national system, so the tool defaults to a safe <b>Dry-run</b> mode and is deliberately
throttled.</p>
<ul>
  <li>Use the tool only with credentials for your own facility, for routine health-checkup
      entry.</li>
  <li>You are responsible for the accuracy of the data you upload.</li>
  <li>For the full legal text, see <b>Help → Terms of Use / Privacy Policy / Security</b>.</li>
</ul>

<a name="template"></a><h3>2 · Get a blank Excel template</h3>
<p>In section <b>2 · Data</b>, click <b>Template…</b> to save a blank <code>.xlsx</code> whose
columns exactly match the active mapping. It opens automatically and includes a couple of example
rows (delete them) and per-column hints — <b>hover a column header</b> to read its hint.</p>
<p>The <b>Mã định danh</b> column is the patient <b>search key</b>. It is normally a
<b>CCCD (citizen ID) or health-insurance number</b> — exactly what you would type into the
website's search box — <i>not</i> the patient's internal medical code. The tool searches the site
with this value and fills the matched patient's real code into the record automatically.</p>

<a name="fill"></a><h3>3 · Fill in the Excel file</h3>
<ul>
  <li><b>Required columns</b> must have a value in every row (e.g. Mã định danh, Ngày khám,
      diagnosis, doctor). Optional columns may be left blank.</li>
  <li><b>Dates</b> use day-first format (<code>dd/MM/yyyy</code>); a time of day is optional.</li>
  <li><b>Decimal numbers</b> may use a comma (Vietnamese locale), e.g. <code>36,8</code>.</li>
  <li><b>BMI</b> is calculated automatically from weight and height when the BMI cell is left
      blank.</li>
  <li>You can also <b>drag &amp; drop</b> an Excel file onto the window instead of using
      <b>Choose Excel…</b>.</li>
</ul>

<a name="login"></a><h3>4 · Log in</h3>
<p>In section <b>1 · Login</b>, click <b>Open website &amp; log in</b>. A browser window opens —
log in to hososuckhoe.com.vn as normal. The tool captures your session and remembers it for next
time, so you usually only log in once.</p>
<ul>
  <li>The status line shows your logged-in identity and how long the session is valid for.</li>
  <li>It warns when under ~5 minutes remain, and turns red when the session expires — just click
      <b>Open website &amp; log in</b> again.</li>
</ul>

<a name="validate"></a><h3>5 · Validate (offline check)</h3>
<p>Click <b>Validate</b> to check your file with <b>no network calls</b>. Only rows with a problem
appear in the Results table: <b>INVALID</b> rows (red) will fail if pushed, and <b>WARNING</b> rows
(amber) push but with a noted issue. A broken column mapping is reported up front, before any row is
processed. Fix the file and validate again until there are no errors.</p>

<a name="dryrun"></a><h3>6 · Dry-run first</h3>
<p><b>Dry-run is on by default.</b> With <b>Dry-run (don't send)</b> ticked, clicking
<b>Start dry-run</b> builds every record <i>without sending anything</i>, so you can inspect the
result. Use the <b>Limit</b> box (e.g. <code>1</code>) to process just a few rows as a test, and
<b>Open report folder</b> to inspect the built payloads.</p>

<a name="push"></a><h3>7 · Push live records</h3>
<p>When you are confident, <b>untick Dry-run</b>. A red <b>PRODUCTION</b> banner appears and the
Start button turns red (<b>PUSH live records</b>). Click it, then <b>confirm the prompt</b>.</p>
<ul>
  <li>Start with a small <b>Limit</b> (e.g. <code>1</code>) and <b>verify the record on the
      website</b> before pushing the whole batch.</li>
  <li>The tool sends requests one at a time with a short delay to avoid overloading the server;
      this is intentional and should not be bypassed.</li>
  <li><b>Stop</b> cancels mid-run; rows already sent are kept.</li>
</ul>

<a name="results"></a><h3>8 · Read the results</h3>
<p>Each processed row appears in the Results table with a <b>Status</b>. The counter shows
<b>✓</b> succeeded, <b>↷</b> skipped, <b>✗</b> failed, and <b>⛔</b> aborted.</p>
<ul>
  <li><b>Created / Updated</b> — the record was written.</li>
  <li><b>Dry-run OK</b> — the record was built but not sent.</li>
  <li><b>Skipped (already sent)</b> — sent on a previous run (see Re-running safely).</li>
  <li><b>Invalid</b> — a cell could not be read; fix the Excel and re-run.</li>
  <li><b>No patient found</b> — no patient matched the Mã định danh; check the value.</li>
  <li><b>Multiple matches</b> — more than one patient matched; the tool will not guess.</li>
  <li><b>Failed</b> — the server rejected the record; the Message column has the detail.</li>
  <li><b>Token expired / Server busy</b> — the batch was aborted; see Troubleshooting.</li>
</ul>
<p>Use <b>Open results spreadsheet</b> for a full report and <b>Open report folder</b> for the
run's files.</p>

<a name="rerun"></a><h3>9 · Re-running safely</h3>
<p>The tool keeps a local <b>ledger</b> of every <code>(identifier, examination-date)</code> pair it
has successfully sent. If a run is interrupted (cancelled, expired session, server error) you can
simply <b>fix the issue and Start again</b> — already-sent rows are skipped automatically, so no
record is created twice.</p>

<a name="modes"></a><h3>10 · Create, Update and Delete mode</h3>
<p>The <b>Mode</b> selector chooses <b>Create</b> (new records, the usual case), <b>Update</b>
(modify existing records) or <b>Delete</b> (remove existing records). Update mode reads
<code>medicalRecordId</code> (the <b>Mã hồ sơ</b> column) from a small extra mapping file,
<code>mapping.update.yaml</code>, that the tool creates and merges automatically — so update
templates already include the column. You still fill in each record's id in Excel; if your header
differs from <b>Mã hồ sơ</b>, edit <code>mapping.update.yaml</code>.</p>
<p><b>Delete</b> mode reuses that same <b>Mã hồ sơ</b> column and needs only two columns —
<b>Mã định danh</b> and <b>Mã hồ sơ</b> (extra columns in a full template are ignored). It fetches
each record first (to confirm it exists and show the patient) and then removes it. Deletion is
<b>permanent</b>, so it is dry-run by default like the other modes — untick Dry-run and confirm the
production prompt to actually delete.</p>

<a name="prefs"></a><h3>11 · Preferences</h3>
<p>Open <b>Settings → Settings…</b>. On the <b>General</b> tab you can set the delay between rows,
a default row limit, whether Dry-run starts ticked, update checking, and the <b>Language</b>
(Vietnamese / English — the change applies immediately when you press Apply or OK). On the
<b>Record defaults</b> tab you can set values that are stamped onto a record only when the matching
Excel cell is blank — per-row Excel values always win. <b>Apply</b> saves without closing; each tab
has its own <b>Reset</b> button to restore that tab's factory values.</p>

<a name="mapping"></a><h3>12 · Column mapping</h3>
<p>The mapping links your Excel column names to the API fields. Click <b>Open mapping</b> to edit
it. Change the column names on the left to match your spreadsheet's header row; leave the API
<code>target</code> on the right unchanged. The identifier column must map to
<code>medicalIdentifierCode</code>. It lives in your user-config folder
(<code>~/Library/Application Support/hssk-tools/mapping.yaml</code> on macOS,
<code>%APPDATA%\\hssk-tools\\mapping.yaml</code> on Windows) and is created from a bundled example
on first run.</p>

<a name="trouble"></a><h3>13 · Troubleshooting</h3>
<ul>
  <li><b>Token expired</b> — click <b>Open website &amp; log in</b>, then Start again; sent rows are
      skipped.</li>
  <li><b>Server busy</b> — wait a few minutes and Start again; sent rows are skipped.</li>
  <li><b>No patient found / Multiple matches</b> — check the Mã định danh value against the
      website's search box; the tool never guesses between patients.</li>
  <li><b>Validation errors</b> — fix the flagged cells in the Excel file and click Validate
      again.</li>
  <li><b>App won't open (unsigned build)</b> — on macOS, right-click the app → Open, then Open; on
      Windows, when SmartScreen appears click "More info" → "Run anyway".</li>
</ul>

<a name="files"></a><h3>14 · Where your files live &amp; privacy</h3>
<p>Run reports, the ledger, and your login token are stored in the app's user-data folder and
<b>contain patient PII or secrets</b>. Handle them according to your clinic's data-retention and
security policy, and do not copy them to shared drives, email, or cloud storage unless your policy
permits it. For details, see <b>Help → Privacy Policy</b> and <b>Help → Security</b>.</p>
"""

_GUIDE_HTML_VI = """
<h2>HSSK Tools — Hướng dẫn sử dụng</h2>
<p>Hướng dẫn này chỉ bạn từng bước cách đẩy dữ liệu khám sức khoẻ từ file Excel lên
<b>hososuckhoe.com.vn</b>. Cửa sổ chính có ba phần đánh số — <b>1 · Đăng nhập</b>,
<b>2 · Dữ liệu</b>, <b>3 · Chạy</b> — và khu vực Kết quả; hướng dẫn này đi theo đúng thứ tự đó.</p>

<p><b>Mục lục</b></p>
<ol>
  <li><a href="#overview">Tổng quan &amp; sử dụng hợp lệ</a></li>
  <li><a href="#template">Lấy mẫu Excel trống</a></li>
  <li><a href="#fill">Điền vào file Excel</a></li>
  <li><a href="#login">Đăng nhập</a></li>
  <li><a href="#validate">Kiểm tra (ngoại tuyến)</a></li>
  <li><a href="#dryrun">Chạy thử trước</a></li>
  <li><a href="#push">Đẩy dữ liệu thật</a></li>
  <li><a href="#results">Đọc kết quả</a></li>
  <li><a href="#rerun">Chạy lại an toàn</a></li>
  <li><a href="#modes">Chế độ Tạo mới, Cập nhật và Xoá</a></li>
  <li><a href="#prefs">Cài đặt</a></li>
  <li><a href="#mapping">File mapping cột</a></li>
  <li><a href="#trouble">Xử lý sự cố</a></li>
  <li><a href="#files">Vị trí lưu file &amp; bảo mật</a></li>
</ol>

<a name="overview"></a><h3>1 · Tổng quan &amp; sử dụng hợp lệ</h3>
<p>HSSK Tools đọc từng hàng bệnh nhân từ file Excel và, với mỗi hàng, tạo một hồ sơ khám sức khoẻ
trên <a href="https://hososuckhoe.com.vn">hososuckhoe.com.vn</a> bằng
<b>tài khoản được uỷ quyền của chính bạn</b>. Mỗi lần đẩy dữ liệu thật sẽ tạo ra một hồ sơ
<b>vĩnh viễn</b> trong hệ thống quốc gia, vì vậy công cụ mặc định chạy ở chế độ <b>Chạy thử</b> an
toàn và được giới hạn tốc độ có chủ đích.</p>
<ul>
  <li>Chỉ dùng công cụ với thông tin đăng nhập của cơ sở bạn, cho việc nhập liệu khám sức khoẻ
      thường quy.</li>
  <li>Bạn chịu trách nhiệm về tính chính xác của dữ liệu mình tải lên.</li>
  <li>Xem nội dung pháp lý đầy đủ tại <b>Trợ giúp → Điều khoản sử dụng / Chính sách bảo mật /
      Bảo mật</b>.</li>
</ul>

<a name="template"></a><h3>2 · Lấy mẫu Excel trống</h3>
<p>Trong phần <b>2 · Dữ liệu</b>, nhấn <b>Mẫu Excel…</b> để lưu một file <code>.xlsx</code> trống có
các cột khớp chính xác với file mapping đang dùng. File sẽ tự mở, gồm vài hàng ví dụ (hãy xoá đi) và
gợi ý cho từng cột — <b>di chuột lên tiêu đề cột</b> để đọc gợi ý.</p>
<p>Cột <b>Mã định danh</b> là <b>khoá tìm kiếm</b> bệnh nhân. Thông thường đây là
<b>số CCCD hoặc số bảo hiểm y tế</b> — đúng thứ bạn gõ vào ô tìm kiếm của website —
<i>không phải</i> mã hồ sơ y tế nội bộ của bệnh nhân. Công cụ tìm trên hệ thống bằng giá trị này
rồi tự điền mã thật của bệnh nhân khớp được vào hồ sơ.</p>

<a name="fill"></a><h3>3 · Điền vào file Excel</h3>
<ul>
  <li><b>Cột bắt buộc</b> phải có giá trị ở mọi hàng (ví dụ Mã định danh, Ngày khám, chẩn đoán,
      bác sĩ). Cột tuỳ chọn có thể để trống.</li>
  <li><b>Ngày</b> dùng định dạng ngày trước (<code>dd/MM/yyyy</code>); giờ là tuỳ chọn.</li>
  <li><b>Số thập phân</b> có thể dùng dấu phẩy (theo tiếng Việt), ví dụ <code>36,8</code>.</li>
  <li><b>BMI</b> được tự động tính từ cân nặng và chiều cao khi ô BMI để trống.</li>
  <li>Bạn cũng có thể <b>kéo &amp; thả</b> file Excel vào cửa sổ thay vì dùng
      <b>Chọn file Excel…</b>.</li>
</ul>

<a name="login"></a><h3>4 · Đăng nhập</h3>
<p>Trong phần <b>1 · Đăng nhập</b>, nhấn <b>Mở website &amp; đăng nhập</b>. Một cửa sổ trình duyệt
sẽ mở — đăng nhập vào hososuckhoe.com.vn như bình thường. Công cụ thu lại phiên làm việc và ghi nhớ
cho lần sau, nên thường bạn chỉ cần đăng nhập một lần.</p>
<ul>
  <li>Dòng trạng thái hiển thị danh tính đã đăng nhập và thời gian còn hiệu lực của phiên.</li>
  <li>Nó cảnh báo khi còn dưới ~5 phút và chuyển đỏ khi phiên hết hạn — chỉ cần nhấn
      <b>Mở website &amp; đăng nhập</b> lại.</li>
</ul>

<a name="validate"></a><h3>5 · Kiểm tra (ngoại tuyến)</h3>
<p>Nhấn <b>Kiểm tra</b> để kiểm tra file mà <b>không gọi mạng</b>. Chỉ những hàng có vấn đề mới hiện
trong bảng Kết quả: hàng <b>Không hợp lệ</b> (đỏ) sẽ thất bại nếu đẩy, còn hàng <b>Cảnh báo</b>
(vàng) vẫn đẩy được nhưng có điểm cần lưu ý. File mapping bị lỗi sẽ được báo ngay từ đầu, trước khi
xử lý bất kỳ hàng nào. Hãy sửa file và kiểm tra lại cho đến khi không còn lỗi.</p>

<a name="dryrun"></a><h3>6 · Chạy thử trước</h3>
<p><b>Chạy thử được bật mặc định.</b> Khi ô <b>Chạy thử (không gửi)</b> được tích, nhấn
<b>Bắt đầu chạy thử</b> sẽ dựng từng hồ sơ <i>mà không gửi gì cả</i>, để bạn kiểm tra kết quả. Dùng
ô <b>Giới hạn</b> (ví dụ <code>1</code>) để xử lý thử vài hàng, và <b>Mở thư mục báo cáo</b> để xem
các hồ sơ đã dựng.</p>

<a name="push"></a><h3>7 · Đẩy dữ liệu thật</h3>
<p>Khi đã chắc chắn, hãy <b>bỏ tích Chạy thử</b>. Một dải băng đỏ <b>PRODUCTION</b> hiện ra và nút
Bắt đầu chuyển đỏ (<b>ĐẨY DỮ LIỆU THẬT</b>). Nhấn nút đó rồi <b>xác nhận ở hộp thoại</b>.</p>
<ul>
  <li>Bắt đầu với <b>Giới hạn</b> nhỏ (ví dụ <code>1</code>) và <b>kiểm tra hồ sơ trên website</b>
      trước khi đẩy cả lô.</li>
  <li>Công cụ gửi từng yêu cầu một, có độ trễ ngắn để tránh quá tải máy chủ; đây là chủ đích và
      không nên bỏ qua.</li>
  <li><b>Dừng</b> huỷ giữa chừng; các hàng đã gửi vẫn được giữ.</li>
</ul>

<a name="results"></a><h3>8 · Đọc kết quả</h3>
<p>Mỗi hàng đã xử lý hiện trong bảng Kết quả kèm <b>Trạng thái</b>. Bộ đếm hiển thị <b>✓</b> thành
công, <b>↷</b> bỏ qua, <b>✗</b> thất bại, và <b>⛔</b> bị dừng.</p>
<ul>
  <li><b>Đã tạo / Đã cập nhật</b> — hồ sơ đã được ghi.</li>
  <li><b>Chạy thử OK</b> — hồ sơ đã dựng nhưng chưa gửi.</li>
  <li><b>Bỏ qua (đã gửi)</b> — đã gửi ở lần chạy trước (xem Chạy lại an toàn).</li>
  <li><b>Không hợp lệ</b> — một ô không đọc được; sửa Excel rồi chạy lại.</li>
  <li><b>Không thấy bệnh nhân</b> — không có bệnh nhân nào khớp Mã định danh; kiểm tra lại giá
      trị.</li>
  <li><b>Trùng nhiều bệnh nhân</b> — có nhiều hơn một bệnh nhân khớp; công cụ sẽ không tự đoán.</li>
  <li><b>Thất bại</b> — máy chủ từ chối hồ sơ; xem chi tiết ở cột Ghi chú.</li>
  <li><b>Token hết hạn / Máy chủ bận</b> — lô bị dừng; xem Xử lý sự cố.</li>
</ul>
<p>Dùng <b>Mở bảng kết quả</b> để xem báo cáo đầy đủ và <b>Mở thư mục báo cáo</b> để xem các file
của lần chạy.</p>

<a name="rerun"></a><h3>9 · Chạy lại an toàn</h3>
<p>Công cụ lưu một <b>sổ cái</b> cục bộ cho mọi cặp <code>(mã định danh, ngày khám)</code> đã gửi
thành công. Nếu một lần chạy bị gián đoạn (huỷ, hết phiên, lỗi máy chủ) bạn chỉ cần <b>sửa vấn đề
và nhấn Bắt đầu lại</b> — các hàng đã gửi sẽ tự động được bỏ qua, nên không hồ sơ nào bị tạo hai
lần.</p>

<a name="modes"></a><h3>10 · Chế độ Tạo mới, Cập nhật và Xoá</h3>
<p>Ô <b>Chế độ</b> chọn <b>Tạo mới</b> (hồ sơ mới, trường hợp thường gặp), <b>Cập nhật</b> (sửa
hồ sơ đã có) hoặc <b>Xoá</b> (xoá hồ sơ đã có). Chế độ Cập nhật đọc <code>medicalRecordId</code>
(cột <b>Mã hồ sơ</b>) từ một file mapping phụ nhỏ, <code>mapping.update.yaml</code>, được công cụ
tạo và gộp tự động — nên mẫu Excel cho cập nhật đã có sẵn cột này. Bạn vẫn cần điền mã hồ sơ của
từng bản ghi vào Excel; nếu tiêu đề cột của bạn khác <b>Mã hồ sơ</b>, hãy sửa
<code>mapping.update.yaml</code>.</p>
<p>Chế độ <b>Xoá</b> dùng lại chính cột <b>Mã hồ sơ</b> đó và chỉ cần hai cột —
<b>Mã định danh</b> và <b>Mã hồ sơ</b> (các cột thừa trong mẫu đầy đủ sẽ bị bỏ qua). Công cụ lấy
chi tiết từng hồ sơ trước (để xác nhận hồ sơ tồn tại và hiển thị bệnh nhân) rồi mới xoá. Việc xoá là
<b>vĩnh viễn</b>, nên mặc định vẫn là chạy thử như các chế độ khác — bỏ chọn Chạy thử và xác nhận
để xoá thật.</p>

<a name="prefs"></a><h3>11 · Cài đặt</h3>
<p>Mở <b>Cài đặt → Cài đặt…</b>. Trong tab <b>Chung</b> bạn có thể đặt độ trễ giữa các hàng,
giới hạn hàng mặc định, có bật Chạy thử sẵn hay không, kiểm tra cập nhật, và <b>Ngôn ngữ</b>
(Tiếng Việt / English — thay đổi áp dụng ngay khi bấm Áp dụng hoặc OK). Trong tab <b>Cài đặt hồ
sơ</b> bạn có thể đặt các giá trị chỉ được gán vào hồ sơ khi ô Excel tương ứng để trống — giá trị
từng hàng trong Excel luôn được ưu tiên. <b>Áp dụng</b> lưu mà không đóng; mỗi tab có nút <b>Khôi
phục</b> riêng để đặt lại giá trị gốc của tab đó.</p>

<a name="mapping"></a><h3>12 · File mapping cột</h3>
<p>File mapping liên kết tên cột Excel của bạn với các trường API. Nhấn <b>Mở file mapping</b> để
chỉnh. Đổi tên cột ở bên trái cho khớp hàng tiêu đề của bảng tính; giữ nguyên <code>target</code>
API ở bên phải. Cột mã định danh phải trỏ tới <code>medicalIdentifierCode</code>. File nằm trong
thư mục cấu hình người dùng (<code>~/Library/Application Support/hssk-tools/mapping.yaml</code> trên
macOS, <code>%APPDATA%\\hssk-tools\\mapping.yaml</code> trên Windows) và được tạo từ file mẫu đi kèm
ở lần chạy đầu tiên.</p>

<a name="trouble"></a><h3>13 · Xử lý sự cố</h3>
<ul>
  <li><b>Token hết hạn</b> — nhấn <b>Mở website &amp; đăng nhập</b>, rồi Bắt đầu lại; các hàng đã
      gửi được bỏ qua.</li>
  <li><b>Máy chủ bận</b> — chờ vài phút rồi Bắt đầu lại; các hàng đã gửi được bỏ qua.</li>
  <li><b>Không thấy bệnh nhân / Trùng nhiều bệnh nhân</b> — kiểm tra giá trị Mã định danh so với ô
      tìm kiếm của website; công cụ không bao giờ tự đoán giữa các bệnh nhân.</li>
  <li><b>Lỗi kiểm tra</b> — sửa các ô bị đánh dấu trong file Excel rồi nhấn Kiểm tra lại.</li>
  <li><b>Ứng dụng không mở (bản chưa ký)</b> — trên macOS, chuột phải vào ứng dụng → Open, rồi Open;
      trên Windows, khi SmartScreen hiện ra nhấn "More info" → "Run anyway".</li>
</ul>

<a name="files"></a><h3>14 · Vị trí lưu file &amp; bảo mật</h3>
<p>Báo cáo chạy, sổ cái và token đăng nhập được lưu trong thư mục dữ liệu người dùng của ứng dụng
và <b>chứa PII bệnh nhân hoặc thông tin bí mật</b>. Hãy xử lý theo chính sách lưu giữ dữ liệu và
bảo mật của phòng khám, và không sao chép chúng lên ổ đĩa dùng chung, email hay lưu trữ đám mây
trừ khi chính sách cho phép. Chi tiết xem <b>Trợ giúp → Chính sách bảo mật</b> và
<b>Trợ giúp → Bảo mật</b>.</p>
"""


def guide_html(lang: str) -> str:
    """Return the User Guide body for ``lang`` (Vietnamese for ``"vi"``, else English)."""
    return _GUIDE_HTML_VI if lang == "vi" else _GUIDE_HTML


class GuideDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("guide_title"))
        self.setMinimumSize(720, 560)

        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)  # http(s) links open in the system browser
        browser.setHtml(guide_html(_lang))  # internal #anchor links scroll within the document
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
