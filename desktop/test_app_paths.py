# desktop/test_app_paths.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app_paths  # noqa: E402


def test_cache_dir_lives_under_localappdata(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    path = app_paths.cache_dir()

    assert path == os.path.join(str(tmp_path), "GlassesSizeImport")
    assert os.path.isdir(path)


def test_cache_dir_accepts_subfolders(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    path = app_paths.cache_dir("data")

    assert path.endswith(os.path.join("GlassesSizeImport", "data"))
    assert os.path.isdir(path)


def test_resource_path_points_next_to_the_source_when_not_frozen():
    here = os.path.dirname(os.path.abspath(app_paths.__file__))

    assert app_paths.resource_path("app_icon.ico") == os.path.join(here, "app_icon.ico")


def test_repo_root_is_the_parent_of_the_desktop_folder():
    here = os.path.dirname(os.path.abspath(app_paths.__file__))

    assert app_paths.repo_root() == os.path.dirname(here)
