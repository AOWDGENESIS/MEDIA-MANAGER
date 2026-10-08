"""Dashboard-Ansicht (Originalauftrag §5)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.i18n import MEDIA_KIND_LABEL_KEYS, tr
from genesis_ui.widgets import set_plain_text


def _card(title: str, value: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    value_label = QLabel(value)
    value_label.setObjectName("CardValue")
    title_label = QLabel(title.upper())
    title_label.setObjectName("CardLabel")
    layout.addWidget(value_label)
    layout.addWidget(title_label)
    return frame


class DashboardView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        header = QLabel(tr("dashboard.title"))
        header.setObjectName("SectionTitle")
        root.addWidget(header)

        self.status_label = QLabel(tr("dashboard.loading"))
        root.addWidget(self.status_label)

        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        root.addLayout(self.grid)

        refresh_btn = QPushButton(tr("dashboard.refresh_button"))
        refresh_btn.setObjectName("Primary")
        refresh_btn.clicked.connect(self.refresh)
        root.addWidget(refresh_btn, alignment=Qt.AlignLeft)

        root.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        # Alte Karten entfernen
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            summary = self.api.dashboard_summary()
            health = self.api.health()
        except GenesisAPIError as exc:
            set_plain_text(self.status_label, tr("dashboard.error", error=exc))
            return

        mode = tr("app.state_on") if health["safe_test_mode"] else tr("app.state_off")
        ai_status = (
            tr("dashboard.ai_reachable") if health["ai_available"]
            else tr("dashboard.ai_unreachable")
        )
        # version/ai_provider stammen aus der Core-Konfiguration - Deep-
        # Review-Fund (Sitzung 11, Fortsetzung): konsistent per
        # set_plain_text() statt setText() behandeln.
        set_plain_text(
            self.status_label,
            tr(
                "dashboard.status", version=health["version"],
                ai_provider=health["ai_provider"], ai_status=ai_status, mode=mode,
            ),
        )

        row, col = 0, 0
        for kind, label_key in MEDIA_KIND_LABEL_KEYS.items():
            count = summary["counts_by_kind"].get(kind, 0)
            self.grid.addWidget(_card(tr(label_key), f"{count:,}".replace(",", ".")), row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1

        row += 1
        self.grid.addWidget(
            _card(tr("dashboard.card_total"), f"{summary['total']:,}".replace(",", ".")),
            row, 0,
        )
        self.grid.addWidget(
            _card(tr("dashboard.card_missing"), str(summary["missing_files"])), row, 1
        )
        self.grid.addWidget(
            _card(tr("dashboard.card_not_analyzed"), str(summary["not_yet_analyzed"])), row, 2
        )
        self.grid.addWidget(
            _card(tr("dashboard.card_running_jobs"), str(summary["running_jobs"])), row, 3
        )
