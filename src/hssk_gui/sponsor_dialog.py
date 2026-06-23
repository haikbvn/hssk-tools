"""Support / donate dialog: shows VietQR and MoMo QR codes side by side."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from hssk.config import sponsor_asset

from .i18n import tr

_QR_WIDTH = 220


def _qr_widget(image_name: str, caption_key: str) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.setSpacing(6)

    px = QPixmap(str(sponsor_asset(image_name)))
    img_label = QLabel()
    img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if px.isNull():
        img_label.setText(tr("sponsor_qr_missing"))
        img_label.setFrameShape(QFrame.Shape.Box)
        img_label.setFixedSize(_QR_WIDTH, _QR_WIDTH)
        img_label.setStyleSheet("color: grey; border: 1px solid #aaa;")
    else:
        img_label.setPixmap(px.scaledToWidth(_QR_WIDTH, Qt.TransformationMode.SmoothTransformation))

    caption = QLabel(tr(caption_key))
    caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

    layout.addWidget(img_label)
    layout.addWidget(caption)
    return container


class SponsorDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("sponsor_title"))
        self.setMinimumWidth(540)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(tr("sponsor_intro"))
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(intro)

        qr_row = QHBoxLayout()
        qr_row.setSpacing(24)
        qr_row.addStretch()
        qr_row.addWidget(_qr_widget("vietqr.png", "sponsor_vietqr_caption"))
        qr_row.addWidget(_qr_widget("momo.png", "sponsor_momo_caption"))
        qr_row.addStretch()
        layout.addLayout(qr_row)

        thanks = QLabel(tr("sponsor_thanks"))
        thanks.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(thanks)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
