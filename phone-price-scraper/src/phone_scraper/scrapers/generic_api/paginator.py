from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

LINK_NEXT_RE = re.compile(r'<([^>]+)>\s*;\s*rel=["\']?next["\']?', re.IGNORECASE)


def get_by_dotted_path(payload: Any, dotted_path: str | None) -> Any:
    """Resolve a dotted path like 'data.pagination.next_cursor' from nested dicts."""
    if not dotted_path:
        return payload
    current = payload
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if 0 <= idx < len(current) else None
        else:
            return None
    return current


@dataclass
class PageRequestSpec:
    url: str
    params: dict[str, Any]
    page_index: int


class ApiPaginator:
    """
    Config-driven paginator supporting:
    none, page_number, offset_limit, cursor, and link_header.
    """

    def __init__(self, config: dict[str, Any] | None, base_url: str, base_params: dict[str, Any]) -> None:
        self.config = config or {"type": "none"}
        self.ptype = str(self.config.get("type", "none")).lower()
        self.base_url = base_url
        self.base_params = dict(base_params)
        self.max_pages = int(self.config.get("max_pages", 50))

    def initial_request(self) -> PageRequestSpec:
        params = dict(self.base_params)
        if self.ptype == "page_number":
            param_name = str(self.config.get("page_param", "page"))
            start_page = int(self.config.get("start_page", 1))
            params[param_name] = start_page
        elif self.ptype == "offset_limit":
            offset_param = str(self.config.get("offset_param", "offset"))
            limit_param = str(self.config.get("limit_param", "limit"))
            limit_val = int(self.config.get("limit", 100))
            params[offset_param] = int(self.config.get("start_offset", 0))
            params[limit_param] = limit_val
        return PageRequestSpec(url=self.base_url, params=params, page_index=0)

    def next_request(
        self,
        prev: PageRequestSpec,
        response: httpx.Response,
        payload: Any,
        items_count: int,
    ) -> PageRequestSpec | None:
        if prev.page_index + 1 >= self.max_pages:
            return None

        if self.ptype == "none":
            return None

        if self.ptype == "page_number":
            if items_count == 0:
                return None
            total_pages_path = self.config.get("total_pages_path")
            param_name = str(self.config.get("page_param", "page"))
            next_page = int(prev.params.get(param_name, 1)) + 1
            if total_pages_path:
                total_pages = get_by_dotted_path(payload, str(total_pages_path))
                if total_pages is not None and next_page > int(total_pages):
                    return None
            params = dict(prev.params)
            params[param_name] = next_page
            return PageRequestSpec(url=self.base_url, params=params, page_index=prev.page_index + 1)

        if self.ptype == "offset_limit":
            limit_param = str(self.config.get("limit_param", "limit"))
            offset_param = str(self.config.get("offset_param", "offset"))
            limit_val = int(prev.params.get(limit_param, self.config.get("limit", 100)))
            if items_count < limit_val:
                return None
            params = dict(prev.params)
            params[offset_param] = int(prev.params.get(offset_param, 0)) + limit_val
            return PageRequestSpec(url=self.base_url, params=params, page_index=prev.page_index + 1)

        if self.ptype == "cursor":
            cursor_path = str(self.config.get("cursor_path", "next_cursor"))
            cursor_param = str(self.config.get("cursor_param", "cursor"))
            next_cursor = get_by_dotted_path(payload, cursor_path)
            if not next_cursor:
                return None
            params = dict(prev.params)
            params[cursor_param] = str(next_cursor)
            return PageRequestSpec(url=self.base_url, params=params, page_index=prev.page_index + 1)

        if self.ptype == "link_header":
            link_hdr = response.headers.get("Link") or response.headers.get("link") or ""
            match = LINK_NEXT_RE.search(link_hdr)
            if not match:
                return None
            return PageRequestSpec(url=match.group(1), params={}, page_index=prev.page_index + 1)

        raise ValueError(f"Unsupported pagination type: {self.ptype}")
