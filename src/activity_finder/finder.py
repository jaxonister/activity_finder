"""Core logic for finding Android app info via adb and aapt."""

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile

from tqdm import tqdm

from activity_finder.cache import AppCache

logger = logging.getLogger(__name__)


class AppInfoFinder:
    def __init__(self, aapt: str | None = None, cache: AppCache | None = None):
        self.aapt = aapt or os.getenv("AAPT_PATH") or self._detect_aapt()
        if not self.aapt:
            raise ValueError(
                "aapt not found. Set AAPT_PATH env var, pass aapt param, "
                "or ensure Android SDK build-tools are installed."
            )
        logger.info("aapt path: %s", self.aapt)
        self.cache = cache

    def _detect_aapt(self) -> str | None:
        sdk_root = os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT")
        if sdk_root:
            build_tools_dir = os.path.join(sdk_root, "build-tools")
            if os.path.isdir(build_tools_dir):
                versions = sorted(os.listdir(build_tools_dir), reverse=True)
                for ver in versions:
                    candidate = os.path.join(build_tools_dir, ver, "aapt")
                    if os.path.isfile(candidate):
                        return candidate
        return "aapt"

    def _get_apk_path(self, package_name: str) -> str | None:
        try:
            output = subprocess.check_output(
                ["adb", "shell", "pm", "path", package_name], timeout=60
            ).decode()
            match = re.search(r"package:(.+)", output)
            return match.group(1).strip() if match else None
        except Exception as e:
            logger.warning("Failed to get APK path for %s: %s", package_name, e)
            return None

    def _pull_apk(self, remote_path: str, local_path: str) -> None:
        subprocess.check_call(
            ["adb", "pull", remote_path, local_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _get_app_label(self, apk_path: str) -> list[str] | None:
        try:
            result = subprocess.run(
                [self.aapt, "dump", "badging", apk_path],
                timeout=60,
                capture_output=True,
            )
            output = result.stdout.decode(errors="ignore")
            return re.findall(r"application-label(?:-[\w\-]+)?:'([^']+)'", output)
        except Exception as e:
            logger.warning("Failed to get app label for %s: %s", apk_path, e)
            return None

    def _get_launch_activity(self, package_name: str) -> str | None:
        try:
            output = subprocess.check_output(
                ["adb", "shell", "cmd", "package", "resolve-activity", "--brief", package_name],
                timeout=60,
            ).decode().strip()
            lines = output.splitlines()
            return lines[-1].strip() if lines else None
        except Exception as e:
            logger.warning("Failed to get launch activity for %s: %s", package_name, e)
            return None

    def _match_label(self, keyword: str, labels: list[str]) -> str | None:
        """Substring match: return the first label containing keyword, or None."""
        for label in labels:
            if keyword in label:
                return label
        return None

    def resolve_label_to_package(self, label_keyword: str) -> list[dict]:
        """Search apps by label keyword (substring match).

        Returns a list of dicts, each with keys: package, activity, label.
        """
        results: list[dict] = []

        if self.cache:
            cached = self.cache.find_by_label(label_keyword)
            for entry in cached:
                if not self.cache.is_stale(entry["package_name"]):
                    results.append({
                        "package": entry["package_name"],
                        "activity": entry["launch_activity"],
                        "label": entry["label"],
                    })
            if results:
                logger.info("Cache hit: %d match(es) for '%s'", len(results), label_keyword)
                return results

        try:
            packages = subprocess.check_output(
                ["adb", "shell", "pm", "list", "packages"], timeout=60
            ).decode().splitlines()
            packages = [line.split(":")[1] for line in packages if ":" in line]
        except Exception as e:
            logger.error("Failed to get package list: %s", e)
            return results

        logger.info("Found %d packages to scan", len(packages))
        temp_dir = tempfile.mkdtemp()
        scanned = 0
        errors = 0
        try:
            for package in tqdm(packages, desc="Scanning apps", unit="app"):
                try:
                    if self.cache and not self.cache.is_stale(package):
                        entry = self.cache.get(package)
                        if entry:
                            labels = entry["labels"]
                            if isinstance(labels, str):
                                labels = json.loads(labels)
                            matched = self._match_label(label_keyword, labels)
                            if matched:
                                results.append({
                                    "package": package,
                                    "activity": entry["launch_activity"],
                                    "label": matched,
                                })
                            continue

                    apk_path = self._get_apk_path(package)
                    if not apk_path:
                        continue

                    local_apk = os.path.join(temp_dir, f"{package}.apk")
                    self._pull_apk(apk_path, local_apk)
                    labels = self._get_app_label(local_apk)
                    if not labels:
                        continue

                    activity = self._get_launch_activity(package)

                    if self.cache:
                        self.cache.put(package, labels, activity or "")

                    matched = self._match_label(label_keyword, labels)
                    if matched:
                        results.append({
                            "package": package,
                            "activity": activity or "",
                            "label": matched,
                        })
                except Exception as e:
                    errors += 1
                    logger.warning("Error scanning %s: %s", package, e)
                    continue
                finally:
                    scanned += 1
        finally:
            logger.info("Scan complete: %d/%d scanned, %d errors, %d match(es)",
                        scanned, len(packages), errors, len(results))
            shutil.rmtree(temp_dir)

        return results

    def _list_packages(self) -> list[str] | None:
        try:
            output = subprocess.check_output(
                ["adb", "shell", "pm", "list", "packages"], timeout=60
            ).decode().splitlines()
            return [line.split(":")[1] for line in output if ":" in line]
        except Exception as e:
            logger.error("Failed to get package list: %s", e)
            return None
