# -*- coding: utf-8 -*-
"""Build import — search a product, collect a basket, export the import file."""
from __future__ import annotations

import datetime
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from dimension_panel import DimensionPanel
from size_import import basket as basket_module
from size_import.catalogue import search
from size_import.categories import DIMENSIONS
from size_import.export import export_filename, to_bytes
from tabs.base import BaseTab

SEARCH_LIMIT = 50
COLUMNS = ["Product", "Global ID", "Sizes", "Category IDs"]


class BuildTab(BaseTab):
    TITLE = "🧱 Build import"

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.basket = {}
        self._selected_id = None
        self._selected_name = None

        self.panel = DimensionPanel()
        self.panel.add_requested.connect(self.add_to_basket)

        layout = QVBoxLayout(self)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by name, e.g. crulle g5063")
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        self.results = QListWidget()
        self.results.setMaximumHeight(180)
        self.results.currentItemChanged.connect(self._on_pick)
        layout.addWidget(self.results)

        self.selected_label = QLabel("No product selected.")
        self.selected_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.selected_label)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        # Qt table headers are not selectable text, so offer copying explicitly.
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        layout.addWidget(self.table, 1)

    # --- snapshot ---
    def on_snapshot(self, snapshot) -> None:
        self.panel.set_lookup(snapshot.lookup if snapshot else {})
        self._on_search(self.search_box.text())
        self._render_basket()

    def control_panel(self):
        return self.panel

    # --- search ---
    def _on_search(self, text: str) -> None:
        self.results.clear()
        if not self.snapshot or not text.strip():
            return
        matches = search(self.snapshot.catalogue, text, limit=SEARCH_LIMIT)
        for row in matches.itertuples(index=False):
            # row.name / row.globalId rely on the column names written by
            # refresh_data.py and read by size_import/catalogue.py.
            item = QListWidgetItem(f"{row.name}  —  {row.globalId}")
            item.setData(Qt.UserRole, (int(row.globalId), str(row.name)))
            self.results.addItem(item)
        if self.results.count() == SEARCH_LIMIT:
            self.status_message.emit(
                f"Showing the first {SEARCH_LIMIT} matches — refine the search if needed."
            )

    def _on_pick(self, current, _previous) -> None:
        if current is None:
            self._selected_id = None
            self._selected_name = None
            self.selected_label.setText("No product selected.")
            self.panel.set_product_selected(False)
            return
        self._selected_id, self._selected_name = current.data(Qt.UserRole)
        self.selected_label.setText(
            f"Selected: {self._selected_name}   ·   Global ID {self._selected_id}"
        )
        self.panel.set_product_selected(True)

    # --- basket ---
    def add_to_basket(self) -> None:
        values = self.panel.values()
        if self._selected_id is None or not values:
            return
        self.basket = basket_module.add(
            self.basket, self._selected_id, self._selected_name, values
        )
        self.panel.clear()
        self._render_basket()
        self.status_message.emit(f"Added {self._selected_name}.")

    def _render_basket(self) -> None:
        lookup = self.snapshot.lookup if self.snapshot else {}
        self.table.setRowCount(0)
        for global_id, entry in self.basket.items():
            ids = basket_module.category_ids(entry, lookup)
            sizes = " | ".join(
                ", ".join(
                    f"{dimension.label} {value_set[dimension.key]}"
                    for dimension in DIMENSIONS
                    if dimension.key in value_set
                )
                for value_set in entry["value_sets"]
            )
            row = self.table.rowCount()
            self.table.insertRow(row)
            for column, text in enumerate(
                [entry["name"], str(global_id), sizes, ";".join(str(i) for i in ids)]
            ):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, global_id)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def selected_global_ids(self) -> list:
        rows = {index.row() for index in self.table.selectedIndexes()}
        return [int(self.table.item(row, 1).text()) for row in sorted(rows)]

    def remove_selected(self) -> None:
        ids = self.selected_global_ids()
        if not ids:
            self.status_message.emit("Select a basket row first.")
            return
        answer = QMessageBox.question(
            self, "Remove", f"Remove {len(ids)} product(s) from the basket?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        for global_id in ids:
            self.basket = basket_module.remove(self.basket, global_id)
        self._render_basket()

    def clear_basket(self) -> None:
        if not self.basket:
            return
        answer = QMessageBox.question(
            self, "Clear basket", f"Clear all {len(self.basket)} product(s)?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.basket = {}
        self._render_basket()

    # --- copying ---
    def _table_menu(self, point) -> None:
        menu = QMenu(self)
        menu.addAction("Copy selected rows", self._copy_selected)
        menu.addAction("Copy whole table (TSV)", self._copy_all)
        menu.exec(self.table.viewport().mapToGlobal(point))

    def _copy_selected(self) -> None:
        self._copy_rows(sorted({index.row() for index in self.table.selectedIndexes()}))

    def _copy_all(self) -> None:
        self._copy_rows(range(self.table.rowCount()))

    def _copy_rows(self, rows) -> None:
        lines = ["\t".join(COLUMNS)]
        for row in rows:
            lines.append(
                "\t".join(
                    self.table.item(row, column).text() for column in range(len(COLUMNS))
                )
            )
        QApplication.clipboard().setText("\n".join(lines))
        self.status_message.emit("Copied — paste straight into Excel.")

    # --- export ---
    def export(self) -> None:
        lookup = self.snapshot.lookup if self.snapshot else {}
        rows = basket_module.export_rows(self.basket, lookup)
        if not rows:
            QMessageBox.information(
                self, "Nothing to export",
                "The basket has no product with a resolvable category yet.",
            )
            return

        suggested = os.path.join(
            self.settings.last_dir("export") or os.path.expanduser("~"),
            export_filename(datetime.date.today()),
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save import file", suggested, "Excel files (*.xlsx)"
        )
        if not path:
            return
        with open(path, "wb") as handle:
            handle.write(to_bytes(rows))
        self.settings.set_last_dir("export", os.path.dirname(path))
        self.status_message.emit(f"Exported {len(rows)} product(s) to {path}")
        QMessageBox.information(
            self, "Exported", f"{len(rows)} product(s) written to:\n{path}"
        )

    def has_unsaved_changes(self) -> bool:
        return bool(self.basket)
