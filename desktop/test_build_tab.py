# -*- coding: utf-8 -*-
"""BuildTab.has_unsaved_changes() across its real lifecycle.

That logic lives entirely in the widget (basket + exported signature) and had
no coverage before this file. Runs headless via the offscreen Qt platform, so
it works in CI and on machines without a display.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

import pytest

pytest.importorskip("PySide6")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PySide6.QtWidgets import QApplication  # noqa: E402

from settings import Settings  # noqa: E402
from size_import import basket as basket_module  # noqa: E402
from tabs.build_tab import BuildTab  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def tab(qapp):
    return BuildTab(Settings())


def _record_export(tab):
    """Do what export() does to the exported signature, without a file dialog."""
    tab._exported_signature = tab._signature()


def test_fresh_tab_is_not_unsaved(tab):
    assert tab.has_unsaved_changes() is False


def test_adding_a_product_makes_it_unsaved(tab):
    tab.basket = basket_module.add(tab.basket, 1, "Frame One", {"bridge": 18})
    assert tab.has_unsaved_changes() is True


def test_recording_an_export_clears_unsaved(tab):
    tab.basket = basket_module.add(tab.basket, 1, "Frame One", {"bridge": 18})
    _record_export(tab)
    assert tab.has_unsaved_changes() is False


def test_adding_another_product_makes_it_unsaved_again(tab):
    tab.basket = basket_module.add(tab.basket, 1, "Frame One", {"bridge": 18})
    _record_export(tab)

    tab.basket = basket_module.add(tab.basket, 2, "Frame Two", {"bridge": 20})
    assert tab.has_unsaved_changes() is True


def test_removing_back_to_exported_state_clears_unsaved(tab):
    tab.basket = basket_module.add(tab.basket, 1, "Frame One", {"bridge": 18})
    _record_export(tab)

    tab.basket = basket_module.add(tab.basket, 2, "Frame Two", {"bridge": 20})
    assert tab.has_unsaved_changes() is True

    tab.basket = basket_module.remove(tab.basket, 2)
    assert tab.has_unsaved_changes() is False


def test_clearing_the_basket_entirely_clears_unsaved(tab):
    tab.basket = basket_module.add(tab.basket, 1, "Frame One", {"bridge": 18})
    _record_export(tab)

    tab.basket = basket_module.add(tab.basket, 2, "Frame Two", {"bridge": 20})
    assert tab.has_unsaved_changes() is True

    tab.basket = {}
    assert tab.has_unsaved_changes() is False
