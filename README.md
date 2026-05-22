# Activity Finder

[中文文档](README.zh.md)

Resolve Android app display names (labels) to their launch activities via `adb` and `aapt`.

## Installation

```bash
pip install activity-finder
```

Or install from source:

```bash
git clone https://github.com/jaxonister/activity_finder.git
cd activity_finder
pip install -e .
```

## Prerequisites

- Python >= 3.10
- [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools) (`adb` on PATH)
- Android SDK Build Tools (`aapt`). Set `AAPT_PATH` env var, or ensure it's discoverable via `ANDROID_HOME`.

## Usage

### CLI

```bash
# Search by label
activity-finder "Keep"

# With custom aapt path
activity-finder --aapt /path/to/aapt "WeChat"

# Disable cache
activity-finder --no-cache "Keep"

# Verbose output
activity-finder -v "Keep"
```

### Python API

```python
from activity_finder import AppInfoFinder, AppCache

cache = AppCache(db_path="apps.db")
finder = AppInfoFinder(cache=cache)

# Fuzzy match: "云盘" matches "中国移动云盘", "百度网盘", etc.
results = finder.resolve_label_to_package("云盘")
for r in results:
    print(f"{r['label']}  {r['package']}  {r['activity']}")

cache.close()
```

## How It Works

1. Lists all installed packages via `adb shell pm list packages`
2. Pulls each APK and reads labels via `aapt dump badging`
3. Matches labels against the keyword (substring/fuzzy match)
4. Returns all matching apps with label, package name, and launch activity
5. Caches results in SQLite to speed up subsequent searches

## License

MIT
