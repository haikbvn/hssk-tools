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

from . import theme
from .i18n import tr

_QR_WIDTH = 220


def _qr_widget(image_name: str, caption_key: str, a11y_key: str, details_key: str) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.setSpacing(6)

    px = QPixmap(str(sponsor_asset(image_name)))
    img_label = QLabel()
    img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    img_label.setAccessibleName(tr(a11y_key))
    img_label.setAccessibleDescription(tr(caption_key))
    if px.isNull():
        img_label.setText(tr("sponsor_qr_missing"))
        img_label.setFrameShape(QFrame.Shape.Box)
        img_label.setFixedSize(_QR_WIDTH, _QR_WIDTH)
        muted = theme.color("muted")
        img_label.setStyleSheet(f"color: {muted}; border: 1px solid {muted};")
    else:
        img_label.setPixmap(px.scaledToWidth(_QR_WIDTH, Qt.TransformationMode.SmoothTransformation))

    caption = QLabel(tr(caption_key))
    caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

    details = QLabel(tr(details_key))
    details.setAlignment(Qt.AlignmentFlag.AlignCenter)
    details.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    details.setWordWrap(True)

    layout.addWidget(img_label)
    layout.addWidget(caption)
    layout.addWidget(details)
    return container


class SponsorDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("sponsor_title"))
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(tr("sponsor_intro"))
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(intro)

        qr_row = QHBoxLayout()
        qr_row.setSpacing(24)
        qr_row.addStretch()
        # qr_row.addWidget(
        #     _qr_widget(
        #         "vietqr.png", "sponsor_vietqr_caption", "a11y_vietqr_qr", "sponsor_vietqr_details"
        #     )
        # )
        qr_row.addWidget(
            _qr_widget("momo.png", "sponsor_momo_caption", "a11y_momo_qr", "sponsor_momo_details")
        )
        qr_row.addStretch()
        layout.addLayout(qr_row)

        thanks = QLabel(tr("sponsor_thanks"))
        thanks.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(thanks)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
