"""Lightweight persistence of UI preferences via QSettings."""

from __future__ import annotations

import json

from PySide6.QtCore import QByteArray, QSettings

_ORG = "hssk-tools"
_APP = "hssk-gui"

_RECENT_FILES_LIMIT = 5


def add_recent(paths: list[str], path: str, limit: int = _RECENT_FILES_LIMIT) -> list[str]:
    """Move-to-front dedupe for the recent-files list (pure, so it unit-tests headless)."""
    out = [path] + [p for p in paths if p != path]
    return out[:limit]


class UiSettings:
    # Factory defaults, shared with the preferences dialog so its "Reset" action and the
    # getters below can't drift apart.
    DELAY_DEFAULT = 1.0
    LIMIT_DEFAULT = 0
    DRY_RUN_DEFAULT = True
    CHECK_UPDATES_DEFAULT = True
    LANGUAGE_DEFAULT = "vi"

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
        return float(self._s.value("delay", self.DELAY_DEFAULT, type=float))  # type: ignore[arg-type]

    @delay.setter
    def delay(self, value: float) -> None:
        self._s.setValue("delay", value)

    @property
    def dry_run(self) -> bool:
        return bool(self._s.value("dry_run", self.DRY_RUN_DEFAULT, type=bool))

    @dry_run.setter
    def dry_run(self, value: bool) -> None:
        self._s.setValue("dry_run", value)

    @property
    def limit(self) -> int:
        return int(self._s.value("limit", self.LIMIT_DEFAULT, type=int))  # type: ignore[call-overload]

    @limit.setter
    def limit(self, value: int) -> None:
        self._s.setValue("limit", value)

    @property
    def terms_accepted(self) -> bool:
        return bool(self._s.value("terms_accepted", False, type=bool))

    @terms_accepted.setter
    def terms_accepted(self, value: bool) -> None:
        self._s.setValue("terms_accepted", value)

    @property
    def language(self) -> str:
        return str(self._s.value("language", self.LANGUAGE_DEFAULT, type=str))

    @language.setter
    def language(self, value: str) -> None:
        self._s.setValue("language", value)

    @property
    def update_mode(self) -> bool:
        return bool(self._s.value("update_mode", False, type=bool))

    @update_mode.setter
    def update_mode(self, value: bool) -> None:
        self._s.setValue("update_mode", value)

    @property
    def check_updates(self) -> bool:
        return bool(self._s.value("check_updates", self.CHECK_UPDATES_DEFAULT, type=bool))

    @check_updates.setter
    def check_updates(self, value: bool) -> None:
        self._s.setValue("check_updates", value)

    @property
    def geometry(self) -> QByteArray:
        value = self._s.value("geometry", QByteArray(), type=QByteArray)
        return value if isinstance(value, QByteArray) else QByteArray()

    @geometry.setter
    def geometry(self, value: QByteArray) -> None:
        self._s.setValue("geometry", value)

    # Stored as one JSON-encoded string: QSettings round-trips a 1-element list as a plain
    # str on some backends, so a native list type is a trap.
    @property
    def recent_files(self) -> list[str]:
        raw = str(self._s.value("recent_files", "[]", type=str))
        try:
            value = json.loads(raw)
        except ValueError:
            return []
        return [p for p in value if isinstance(p, str)] if isinstance(value, list) else []

    @recent_files.setter
    def recent_files(self, value: list[str]) -> None:
        self._s.setValue("recent_files", json.dumps(value, ensure_ascii=False))

    def add_recent_file(self, path: str) -> None:
        self.recent_files = add_recent(self.recent_files, path)

    @property
    def results_splitter(self) -> QByteArray:
        value = self._s.value("results_splitter", QByteArray(), type=QByteArray)
        return value if isinstance(value, QByteArray) else QByteArray()

    @results_splitter.setter
    def results_splitter(self, value: QByteArray) -> None:
        self._s.setValue("results_splitter", value)
