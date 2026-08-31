# -*- coding: utf-8 -*-
"""Glasses Size Import — desktop entry point.

Run from source:   "C:\\gv\\Scripts\\python.exe" desktop\\main.py
Selftest:          "C:\\gv\\Scripts\\python.exe" desktop\\main.py --selftest
Build:             "C:\\gv\\Scripts\\pyinstaller.exe" desktop\\GlassesSizeImport.spec
"""
from __future__ import annotations

import os
import sys

# --- import bootstrap ------------------------------------------------------
# size_import/ and refresh_data.py live in the repo root; the desktop modules
# import each other flat. Make both work from source and from a bundle.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
# ---------------------------------------------------------------------------

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QAction, QIcon  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QDockWidget, QFileDialog, QLabel, QMainWindow, QMessageBox,
    QProgressBar, QTabWidget, QVBoxLayout, QWidget,
)

import data_store  # noqa: E402
import theme  # noqa: E402
import updater  # noqa: E402
from app_paths import resource_path  # noqa: E402
from settings import Settings  # noqa: E402
from settings_dialog import SettingsDialog  # noqa: E402
from tabs import ALL_TABS  # noqa: E402
from version import APP_NAME, ORG_NAME, __version__  # noqa: E402
from workers import Worker  # noqa: E402


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.snapshot = None
        self._worker = None
        self._update_worker = None

        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1200, 780)

        self.tabs = QTabWidget()
        self.tab_widgets = []
        for cls in ALL_TABS:
            tab = cls(self.settings, self)
            tab.status_message.connect(self.show_status)
            tab.busy.connect(self.set_busy)
            self.tabs.addTab(tab, cls.TITLE)
            self.tab_widgets.append(tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)
        self.build_tab, self.data_tab = self.tab_widgets

        self.dock = QDockWidget("Control panel", self)
        self.dock.setObjectName("control_panel")
        self.dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.dock.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )
        self._empty_dock = QWidget()
        QVBoxLayout(self._empty_dock)
        self.dock.setWidget(self._empty_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.resizeDocks([self.dock], [320], Qt.Horizontal)

        self._build_toolbar()

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setMaximumWidth(180)
        self.statusBar().addPermanentWidget(self.progress)
        self.data_status = QLabel("")
        self.statusBar().addPermanentWidget(self.data_status)

        self._on_tab_changed(self.tabs.currentIndex())
        # The basket only changes through actions that emit a status message,
        # so that is enough to keep the unsaved-marker in the title honest.
        self.build_tab.status_message.connect(lambda _message: self._update_title())
        self.load_snapshot()

    # ------------------------------------------------------------- toolbar
    def _build_toolbar(self) -> None:
        bar = self.addToolBar("Main")
        bar.setObjectName("main_toolbar")

        self.act_refresh = QAction("🔁 Refresh from Excel", self)
        self.act_refresh.triggered.connect(self.refresh_from_excel)
        bar.addAction(self.act_refresh)

        self.act_remove = QAction("🗑 Remove selected", self)
        self.act_remove.triggered.connect(lambda: self.build_tab.remove_selected())
        bar.addAction(self.act_remove)

        self.act_clear = QAction("🧹 Clear basket", self)
        self.act_clear.triggered.connect(lambda: self.build_tab.clear_basket())
        bar.addAction(self.act_clear)

        self.act_export = QAction("💾 Export import file", self)
        self.act_export.triggered.connect(lambda: self.build_tab.export())
        bar.addAction(self.act_export)

        bar.addSeparator()

        self.act_settings = QAction("⚙️ Settings", self)
        self.act_settings.triggered.connect(self.open_settings)
        bar.addAction(self.act_settings)

        self.act_update = QAction("⬆️ Check updates", self)
        self.act_update.triggered.connect(self.check_updates)
        bar.addAction(self.act_update)

        self.act_dark = QAction("🌙 Dark mode", self)
        self.act_dark.setCheckable(True)
        self.act_dark.setChecked(self.settings.dark_mode)
        self.act_dark.toggled.connect(self.toggle_dark)
        bar.addAction(self.act_dark)

    def _on_tab_changed(self, index: int) -> None:
        tab = self.tabs.widget(index)
        panel = tab.control_panel() if tab else None
        if panel is None:
            self.dock.setWidget(self._empty_dock)
            self.dock.hide()
        else:
            self.dock.setWidget(panel)
            self.dock.show()
        on_build = tab is self.build_tab
        for action in (self.act_remove, self.act_clear, self.act_export):
            action.setEnabled(on_build)

    # -------------------------------------------------------------- status
    def show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)

    def set_busy(self, busy: bool) -> None:
        self.progress.setVisible(bool(busy))
        for action in (self.act_refresh, self.act_export, self.act_update):
            action.setEnabled(not busy)

    def _update_title(self) -> None:
        mark = " •" if self.build_tab.has_unsaved_changes() else ""
        self.setWindowTitle(f"{APP_NAME} {__version__}{mark}")

    # ------------------------------------------------------------ snapshot
    def load_snapshot(self) -> None:
        try:
            self.snapshot = data_store.load_snapshot()
        except (FileNotFoundError, RuntimeError) as error:
            self.snapshot = None
            self.data_status.setText("No data")
            self.data_status.setStyleSheet(theme.status_style("error"))
            QMessageBox.warning(self, "No product data", str(error))
            for tab in self.tab_widgets:
                tab.set_snapshot(None)
            return

        for tab in self.tab_widgets:
            tab.set_snapshot(self.snapshot)
        self.data_status.setText(
            f"{len(self.snapshot.catalogue):,} products ({self.snapshot.source}, "
            f"{self.snapshot.updated_at:%Y-%m-%d})"
        )
        self.data_status.setStyleSheet(theme.status_style("ready"))

    def refresh_from_excel(self) -> None:
        catalogue_xlsx, _ = QFileDialog.getOpenFileName(
            self, "Select Main catalogue.xlsx",
            self.settings.last_dir("source") or os.path.expanduser("~"),
            "Excel files (*.xlsx *.xlsm)",
        )
        if not catalogue_xlsx:
            return
        self.settings.set_last_dir("source", os.path.dirname(catalogue_xlsx))

        categories_xlsx, _ = QFileDialog.getOpenFileName(
            self, "Select Glasses size category ids.xlsx (Cancel to keep the current one)",
            os.path.dirname(catalogue_xlsx), "Excel files (*.xlsx *.xlsm)",
        )

        self.set_busy(True)
        self.show_status("Refreshing from Excel — this takes about 15 seconds…")
        worker = Worker(
            data_store.refresh_from_excel, catalogue_xlsx, categories_xlsx or None
        )

        def done(report):
            self.set_busy(False)
            self.data_tab.show_report(report)
            self.load_snapshot()
            catalogue = report.get("catalogue") or {}
            QMessageBox.information(
                self, "Refreshed",
                f"{catalogue.get('products', 0)} products loaded.\n"
                "See the Data tab for the full report.",
            )

        worker.done.connect(done)
        worker.failed.connect(
            lambda message: (self.set_busy(False),
                             QMessageBox.warning(self, "Refresh failed", message))
        )
        worker.start()
        self._worker = worker

    # ------------------------------------------------------------ settings
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        dialog.exec()

    def toggle_dark(self, enabled: bool) -> None:
        self.settings.dark_mode = bool(enabled)
        theme.apply_theme(QApplication.instance(), bool(enabled))

    # ------------------------------------------------------------- updates
    def check_updates(self) -> None:
        if not self.settings.update_token:
            QMessageBox.information(
                self, "Updates not configured",
                "This repo is private, so the update check needs a GitHub token "
                "with read access to its Releases.\nAdd one in ⚙️ Settings.",
            )
            return
        self.set_busy(True)
        worker = Worker(updater.update_available, self.settings.update_token)

        def done(release):
            self.set_busy(False)
            if not release:
                QMessageBox.information(
                    self, "Up to date", f"You are on the latest version ({__version__})."
                )
                return
            answer = QMessageBox.question(
                self, "Update available",
                f"Version {release['version']} is available (you have {__version__}).\n"
                "Download and install it now?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                self._download_update(release)

        worker.done.connect(done)
        worker.failed.connect(
            lambda message: (self.set_busy(False),
                             QMessageBox.warning(self, "Update check failed", message))
        )
        worker.start()
        self._update_worker = worker

    def _download_update(self, release: dict) -> None:
        self.set_busy(True)
        worker = Worker(
            updater.download_and_swap, release, self.settings.update_token
        )

        def done(_path):
            self.set_busy(False)
            QMessageBox.information(
                self, "Restarting",
                "The update was downloaded. The app will now close and reopen.",
            )
            QApplication.instance().quit()

        worker.done.connect(done)
        worker.failed.connect(
            lambda message: (self.set_busy(False),
                             QMessageBox.warning(self, "Update failed", message))
        )
        worker.start()
        self._update_worker = worker

    # --------------------------------------------------------------- close
    def closeEvent(self, event) -> None:
        if self.build_tab.has_unsaved_changes():
            answer = QMessageBox.question(
                self, "Basket not exported",
                f"{len(self.build_tab.basket)} product(s) are still in the basket "
                "and will be lost. Close anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()


def _selftest(win) -> int:
    """--selftest: build the whole UI headlessly, print a report, exit."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    problems = []
    print(f"{APP_NAME} {__version__}")
    print(f"tabs: {win.tabs.count()}")
    for index in range(win.tabs.count()):
        tab = win.tabs.widget(index)
        win.tabs.setCurrentIndex(index)
        QApplication.processEvents()
        panel = tab.control_panel()
        print(
            f"  [{index}] {win.tabs.tabText(index)!r:20} "
            f"dock={'yes' if panel is not None else 'no'}"
        )
        for name in ("set_snapshot", "control_panel", "has_unsaved_changes"):
            if not callable(getattr(tab, name, None)):
                problems.append(f"{tab.__class__.__name__} missing {name}")

    snapshot = win.snapshot
    print(f"snapshot: {'none' if snapshot is None else snapshot.source}")
    if snapshot is not None:
        print(f"products: {len(snapshot.catalogue)}")
        print(f"categories: {sum(len(v) for v in snapshot.lookup.values())}")
    else:
        problems.append("no snapshot loaded — is data/ bundled or refreshed?")
    print(f"data status: {win.data_status.text()!r}")
    print(f"dock shown on current tab: {not win.dock.isHidden()}")
    print(f"update token configured: {bool(win.settings.update_token)}")

    if problems:
        print("PROBLEMS:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("SELFTEST OK — UI built, snapshot loaded.")
    return 0


def main() -> int:
    selftest = "--selftest" in sys.argv
    if selftest:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)

    icon_path = resource_path("app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    settings = Settings()
    theme.apply_theme(app, settings.dark_mode)

    win = MainWindow()
    if selftest:
        QApplication.processEvents()
        code = _selftest(win)
        # Never leave a QThread alive at interpreter exit — Qt hangs on it.
        for attr in ("_worker", "_update_worker"):
            worker = getattr(win, attr, None)
            if worker is not None and worker.isRunning():
                worker.wait(5000)
        return code

    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
