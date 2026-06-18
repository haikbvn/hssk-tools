"""Lightweight persistence of UI preferences via QSettings."""

from __future__ import annotations

from PySide6.QtCore import QSettings

_ORG = "hssk-tools"
_APP = "hssk-gui"


class UiSettings:
    def __init__(self) -> None:
        self._s = QSettings(_ORG, _APP)

    @property
    def last_file(self) -> str:
        return str(self._s.value("last_file", "", type=str))

    @last_file.setter
    def last_file(self, value: str) -> None:
        self._s.setValue("last_file", value)

    @property
    def delay(self) -> float:
        return float(self._s.value("delay", 1.0, type=float))  # type: ignore[arg-type]

    @delay.setter
    def delay(self, value: float) -> None:
        self._s.setValue("delay", value)

    @property
    def dry_run(self) -> bool:
        return bool(self._s.value("dry_run", True, type=bool))

    @dry_run.setter
    def dry_run(self, value: bool) -> None:
        self._s.setValue("dry_run", value)

    @property
    def limit(self) -> int:
        return int(self._s.value("limit", 0, type=int))  # type: ignore[call-overload]

    @limit.setter
    def limit(self, value: int) -> None:
        self._s.setValue("limit", value)
