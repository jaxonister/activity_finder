# Activity Finder

[English](README.md)

通过 `adb` 和 `aapt` 将 Android 应用显示名称（标签）解析为启动 Activity。

## 安装

```bash
pip install activity-finder
```

从源码安装：

```bash
git clone https://github.com/jaxonister/activity_finder.git
cd activity_finder
pip install -e .
```

## 前置条件

- Python >= 3.10
- [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools)（`adb` 需在 PATH 中）
- Android SDK Build Tools（`aapt`）。设置 `AAPT_PATH` 环境变量，或确保可通过 `ANDROID_HOME` 自动检测到。

## 使用

### 命令行

```bash
# 按标签搜索
activity-finder "Keep"

# 自定义 aapt 路径
activity-finder --aapt /path/to/aapt "WeChat"

# 禁用缓存
activity-finder --no-cache "Keep"

# 详细输出
activity-finder -v "Keep"
```

### Python API

```python
from activity_finder import AppInfoFinder, AppCache

cache = AppCache(db_path="apps.db")
finder = AppInfoFinder(cache=cache)

# 模糊匹配："云盘" 可匹配 "中国移动云盘"、"百度网盘" 等
results = finder.resolve_label_to_package("云盘")
for r in results:
    print(f"{r['label']}  {r['package']}  {r['activity']}")

cache.close()
```

## 工作原理

1. 通过 `adb shell pm list packages` 列出所有已安装应用
2. 逐个拉取 APK 并通过 `aapt dump badging` 读取标签
3. 将标签与搜索关键词进行子串模糊匹配
4. 返回所有匹配的应用名称、包名和启动 Activity
5. 将结果缓存到 SQLite，加速后续搜索

## 许可证

MIT
