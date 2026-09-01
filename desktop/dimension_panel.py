# -*- coding: utf-8 -*-
"""The six millimetre fields, shown in the right-hand 'Control panel' dock.

Each field resolves live to its global category ID, or says plainly that no
category exists for that value — the same feedback the web version gives, in
the house colours.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

import theme
from size_import.categories import DIMENSIONS, resolve

MAX_MM = 300


class DimensionPanel(QWidget):
    """Emits `add_requested` when the user commits the entered values."""

    add_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lookup = {}
        self._spins = {}
        self._notes = {}
        self._product_selected = False

        layout = QVBoxLayout(self)
        box = QGroupBox("Dimensions (mm)")
        box_layout = QVBoxLayout(box)

        for dimension in DIMENSIONS:
            spin = QSpinBox()
            spin.setRange(0, MAX_MM)
            spin.setSpecialValueText(" ")   # 0 reads as empty, never as a value
            spin.valueChanged.connect(self._refresh_notes)
            note = QLabel("")
            note.setWordWrap(True)

            box_layout.addWidget(QLabel(dimension.label))
            box_layout.addWidget(spin)
            box_layout.addWidget(note)

            self._spins[dimension.key] = spin
            self._notes[dimension.key] = note

        layout.addWidget(box)

        self.add_button = QPushButton("Add to basket")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self.add_requested)
        layout.addWidget(self.add_button)

        self.hint = QLabel("Pick a product first.")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        layout.addStretch(1)

    # --- state in ---
    def set_lookup(self, lookup: dict) -> None:
        self._lookup = lookup or {}
        self._refresh_notes()

    def set_product_selected(self, selected: bool) -> None:
        self._product_selected = bool(selected)
        self._refresh_notes()

    # --- state out ---
    def values(self) -> dict:
        """{dimension key: mm} for every field the user actually filled.

        0 means "not entered": no dimension has a category for 0 (the minimums
        are bridge 1, temple 1, lens height 4, to-bend 10, lens width 14,
        glasses width 45), so treating it as blank is safe.
        """
        return {key: spin.value() for key, spin in self._spins.items() if spin.value()}

    def clear(self) -> None:
        for spin in self._spins.values():
            spin.blockSignals(True)
            spin.setValue(0)
            spin.blockSignals(False)
        self._refresh_notes()

    # --- live feedback ---
    def _refresh_notes(self) -> None:
        for dimension in DIMENSIONS:
            spin = self._spins[dimension.key]
            note = self._notes[dimension.key]
            value = spin.value()
            if not value:
                note.setText("")
                note.setStyleSheet("")
                continue
            category_id = resolve(self._lookup, dimension.key, value)
            if category_id is None:
                note.setText(f"No category for {dimension.label} {value} — will be skipped")
                note.setStyleSheet(
                    f"background-color: {theme.COLOR_ERROR};"
                    f"color: {theme.COLOR_FORCED_TEXT}; padding: 2px 4px; border-radius: 3px;"
                )
            else:
                note.setText(f"category {category_id}")
                note.setStyleSheet(f"color: {theme.STATUS_READY};")

        has_values = bool(self.values())
        self.add_button.setEnabled(self._product_selected and has_values)
        if not self._product_selected:
            self.hint.setText("Pick a product first.")
        elif not has_values:
            self.hint.setText("Enter at least one dimension.")
        else:
            self.hint.setText("")
