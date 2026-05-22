# tests/test_finder.py
import json
import subprocess
import time
from activity_finder.cache import AppCache


def test_cache_put_and_get(tmp_path):
    db = tmp_path / "test.db"
    cache = AppCache(db_path=str(db))
    cache.put("com.example.app", ["Example", "示例"], "com.example/.MainActivity")
    result = cache.get("com.example.app")
    assert result is not None
    assert result["package_name"] == "com.example.app"
    assert json.loads(result["labels"]) == ["Example", "示例"]
    assert result["launch_activity"] == "com.example/.MainActivity"
    cache.close()


def test_cache_get_miss(tmp_path):
    db = tmp_path / "test.db"
    cache = AppCache(db_path=str(db))
    result = cache.get("com.nonexistent.app")
    assert result is None
    cache.close()


def test_cache_is_stale_returns_true_when_expired(tmp_path):
    db = tmp_path / "test.db"
    cache = AppCache(db_path=str(db))
    cache.put("com.example.app", ["Example"], "com.example/.Main")
    conn = cache._conn
    conn.execute(
        "UPDATE app_cache SET updated_at = ? WHERE package_name = ?",
        (time.time() - 100000, "com.example.app"),
    )
    conn.commit()
    assert cache.is_stale("com.example.app", ttl_seconds=86400) is True
    cache.close()


def test_cache_is_stale_returns_false_when_fresh(tmp_path):
    db = tmp_path / "test.db"
    cache = AppCache(db_path=str(db))
    cache.put("com.example.app", ["Example"], "com.example/.Main")
    assert cache.is_stale("com.example.app", ttl_seconds=86400) is False
    cache.close()


def test_cache_put_overwrites_existing(tmp_path):
    db = tmp_path / "test.db"
    cache = AppCache(db_path=str(db))
    cache.put("com.example.app", ["Old"], "com.example/.Old")
    cache.put("com.example.app", ["New"], "com.example/.New")
    result = cache.get("com.example.app")
    assert json.loads(result["labels"]) == ["New"]
    assert result["launch_activity"] == "com.example/.New"
    cache.close()


# --- AppInfoFinder tests ---

import os
from unittest.mock import patch, MagicMock
from activity_finder.finder import AppInfoFinder


# --- aapt 路径自动检测测试 ---

def test_aapt_from_param():
    finder = AppInfoFinder(aapt="/custom/aapt")
    assert finder.aapt == "/custom/aapt"


def test_aapt_from_env(monkeypatch):
    monkeypatch.setenv("AAPT_PATH", "/env/aapt")
    finder = AppInfoFinder()
    assert finder.aapt == "/env/aapt"


def test_aapt_from_android_home(monkeypatch, tmp_path):
    monkeypatch.delenv("AAPT_PATH", raising=False)
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path))
    build_tools = tmp_path / "build-tools" / "34.0.0"
    build_tools.mkdir(parents=True)
    aapt_bin = build_tools / "aapt"
    aapt_bin.touch()
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    finder = AppInfoFinder()
    assert finder.aapt == str(aapt_bin)


def test_aapt_fallback_to_path(monkeypatch):
    monkeypatch.delenv("AAPT_PATH", raising=False)
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    finder = AppInfoFinder()
    assert finder.aapt == "aapt"


# --- 核心方法测试 ---

@patch("activity_finder.finder.subprocess.check_output")
def test_get_apk_path_success(mock_check_output):
    mock_check_output.return_value = b"package:/data/app/com.example/base.apk\n"
    finder = AppInfoFinder(aapt="/usr/bin/aapt")
    result = finder._get_apk_path("com.example")
    assert result == "/data/app/com.example/base.apk"


@patch("activity_finder.finder.subprocess.check_output")
def test_get_apk_path_not_found(mock_check_output):
    mock_check_output.return_value = b""
    finder = AppInfoFinder(aapt="/usr/bin/aapt")
    result = finder._get_apk_path("com.nonexistent")
    assert result is None


@patch("activity_finder.finder.subprocess.run")
def test_get_app_label(mock_run):
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0,
        stdout=(
            b"package: name='com.example'\n"
            b"application-label:'Example'\n"
            b"application-label-zh:'\xe7\xa4\xba\xe4\xbe\x8b'\n"
        ),
        stderr=b"",
    )
    finder = AppInfoFinder(aapt="/usr/bin/aapt")
    labels = finder._get_app_label("/tmp/test.apk")
    assert labels == ["Example", "示例"]


@patch("activity_finder.finder.subprocess.check_output")
def test_get_launch_activity(mock_check_output):
    mock_check_output.return_value = b"com.example/.MainActivity\n"
    finder = AppInfoFinder(aapt="/usr/bin/aapt")
    activity = finder._get_launch_activity("com.example")
    assert activity == "com.example/.MainActivity"


@patch("activity_finder.finder.subprocess.check_output")
def test_resolve_label_to_package_with_cache_hit(mock_check_output, tmp_path):
    from activity_finder.cache import AppCache

    db = tmp_path / "test.db"
    cache = AppCache(db_path=str(db))
    cache.put("com.example", ["Example"], "com.example/.Main")

    finder = AppInfoFinder(aapt="/usr/bin/aapt", cache=cache)
    result = finder.resolve_label_to_package("Example")
    assert len(result) == 1
    assert result[0]["package"] == "com.example"
    assert result[0]["activity"] == "com.example/.Main"
    assert result[0]["label"] == "Example"
    mock_check_output.assert_not_called()
    cache.close()


@patch("activity_finder.finder.subprocess.check_output")
def test_resolve_label_fuzzy_match(mock_check_output, tmp_path):
    from activity_finder.cache import AppCache

    db = tmp_path / "test.db"
    cache = AppCache(db_path=str(db))
    cache.put("com.example.app", ["中国移动云盘", "ChinaMobile"], "com.example/.Main")
    cache.put("com.other.app", ["中国移动", "CM"], "com.other/.Main")

    finder = AppInfoFinder(aapt="/usr/bin/aapt", cache=cache)
    result = finder.resolve_label_to_package("中国移动")
    assert len(result) == 2
    labels = [r["label"] for r in result]
    assert "中国移动云盘" in labels
    assert "中国移动" in labels
    mock_check_output.assert_not_called()
    cache.close()


@patch("activity_finder.finder.subprocess.run")
@patch("activity_finder.finder.subprocess.check_call")
@patch("activity_finder.finder.subprocess.check_output")
def test_resolve_label_to_package_scans_apps(mock_check_output, mock_check_call, mock_run, tmp_path):
    def check_output_side_effect(cmd, **kwargs):
        if "list" in cmd and "packages" in cmd:
            return b"package:com.example\npackage:com.other\n"
        if "path" in cmd:
            if cmd[-1] == "com.example":
                return b"package:/data/app/com.example/base.apk\n"
            return b"package:/data/app/com.other/base.apk\n"
        if "resolve-activity" in cmd:
            return b"com.example/.MainActivity\n"
        return b""

    def run_side_effect(cmd, **kwargs):
        if "badging" in cmd:
            if "com.example" in cmd[-1]:
                return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"application-label:'Example'\n", stderr=b"")
            return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"application-label:'Other'\n", stderr=b"")
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    mock_check_output.side_effect = check_output_side_effect
    mock_check_call.return_value = 0
    mock_run.side_effect = run_side_effect

    finder = AppInfoFinder(aapt="/usr/bin/aapt")
    result = finder.resolve_label_to_package("Example")
    assert len(result) == 1
    assert result[0]["package"] == "com.example"
    assert result[0]["activity"] == "com.example/.MainActivity"
    assert result[0]["label"] == "Example"


# --- CLI tests ---

from activity_finder.cli import main
from unittest.mock import patch


def test_cli_prints_activity(capsys):
    with patch("activity_finder.cli.AppInfoFinder") as MockFinder:
        instance = MockFinder.return_value
        instance.resolve_label_to_package.return_value = [
            {"package": "com.example", "activity": "com.example/.Main", "label": "Example"},
        ]
        main(["Keep"])
        captured = capsys.readouterr()
        assert "com.example" in captured.out
        assert "com.example/.Main" in captured.out


def test_cli_prints_not_found(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        with patch("activity_finder.cli.AppInfoFinder") as MockFinder:
            instance = MockFinder.return_value
            instance.resolve_label_to_package.return_value = []
            main(["NonExistent"])
            assert "Not found" in caplog.text
