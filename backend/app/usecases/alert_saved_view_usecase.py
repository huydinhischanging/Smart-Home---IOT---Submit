from app.extensions.database import db


class AlertSavedViewUseCase:
    VALID_FILTERS = {"all", "unread", "critical", "warning", "info"}
    VALID_TIME_RANGES = {"all", "24h", "7d", "30d"}
    VALID_SORTS = {"newest", "oldest"}

    def __init__(self, alert_saved_view_repo):
        self.alert_saved_view_repo = alert_saved_view_repo

    def get_views(self, user_id):
        return self._normalize_views(self.alert_saved_view_repo.get_views(user_id))

    def replace_views(self, user_id, views):
        normalized = self._normalize_views(views)
        self.alert_saved_view_repo.replace_views(user_id, normalized)
        db.session.commit()
        return normalized

    def get_stats(self, limit=10):
        try:
            parsed_limit = int(limit)
        except (TypeError, ValueError):
            parsed_limit = 10
        parsed_limit = min(max(parsed_limit, 1), 50)
        return self.alert_saved_view_repo.get_stats(limit=parsed_limit)

    def _normalize_views(self, views):
        if not isinstance(views, list):
            raise ValueError("views must be a list")

        normalized = []
        seen_names = set()
        for raw_view in views:
            if not isinstance(raw_view, dict):
                continue
            name = str(raw_view.get("name", "")).strip()[:24]
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            normalized.append({
                "name": name,
                "kind": "saved",
                "pinned": bool(raw_view.get("pinned", False)),
                "filter": self._normalize_filter(raw_view.get("filter")),
                "query": str(raw_view.get("query", ""))[:120],
                "deviceCode": str(raw_view.get("deviceCode", ""))[:64],
                "timeRange": self._normalize_time_range(raw_view.get("timeRange")),
                "sort": self._normalize_sort(raw_view.get("sort")),
            })

        pinned = [view for view in normalized if view["pinned"]]
        unpinned = [view for view in normalized if not view["pinned"]]
        return (pinned + unpinned)[:8]

    def _normalize_filter(self, value):
        candidate = str(value or "all").strip().lower()
        return candidate if candidate in self.VALID_FILTERS else "all"

    def _normalize_time_range(self, value):
        candidate = str(value or "all").strip().lower()
        return candidate if candidate in self.VALID_TIME_RANGES else "all"

    def _normalize_sort(self, value):
        candidate = str(value or "newest").strip().lower()
        return candidate if candidate in self.VALID_SORTS else "newest"