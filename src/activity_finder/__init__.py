"""activity_finder - Resolve Android app labels to launch activities."""

__version__ = "0.1.0"

from activity_finder.finder import AppInfoFinder
from activity_finder.cache import AppCache

__all__ = ["AppInfoFinder", "AppCache", "__version__"]
