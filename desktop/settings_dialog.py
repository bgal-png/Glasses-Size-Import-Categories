# -*- coding: utf-8 -*-
"""⚙️ Settings — the optional update token.

No token is ever baked into a build: a token-carrying .exe must not be attached
to a Release, and private distribution would break self-update.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.resize(520, 200)

        layout = QVBoxLayout(self)
        explanation = QLabel(
            "This repo is private, so checking for updates needs a GitHub "
            "fine-grained token with read access to its Contents and Releases. "
            "It is stored per user and never included in a build."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        form = QFormLayout()
        self.token = QLineEdit(settings.update_token)
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText("github_pat_… (optional)")
        form.addRow("Update token", self.token)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        self.settings.update_token = self.token.text()
        super().accept()
