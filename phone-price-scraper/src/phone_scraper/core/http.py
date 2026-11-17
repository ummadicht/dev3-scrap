from __future__ import annotations

import hashlib
import logging
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from phone_scraper.core.rate_limit import DomainRateLimiter
from phone_scraper.core.retry import with_retry

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
    ),
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

CAPTCHA_MARKERS = (
    "type the characters you see in this image",
    "api-services-support@amazon.com",
    "g-recaptcha",
    "cf-challenge-running",
    "verify you are human",
    "captcha-delivery",
    "bot detection",
)

LOGIN_WALL_MARKERS = (
    "sign in to continue",
    "please log in to view",
    "/ap/signin",
)


class BlockedByAntiBotError(RuntimeError):
    """Raised when a target responds with a CAPTCHA or login wall."""


class RobotsDisallowedError(RuntimeError):
    """Raised when robots.txt forbids fetching the target URL."""


def detect_block(status_code: int, body: str) -> str | None:
    """Detect CAPTCHA or login wall without attempting to bypass it."""
    lower = body.lower()
    for marker in CAPTCHA_MARKERS:
        if marker in lower:
            return f"CAPTCHA detected ({marker})"
    for marker in LOGIN_WALL_MARKERS:
        if marker in lower and status_code in (200, 401, 403):
            return f"Login wall detected ({marker})"
    if status_code in (403, 503) and ("captcha" in lower or "robot" in lower):
        return f"Anti-bot HTTP {status_code} block detected"
    return None


class RobotsChecker:
    """Caches and evaluates robots.txt rules per origin."""

    def __init__(self, timeout_sec: float = 10.0) -> None:
        self._cache: dict[str, RobotFileParser | None] = {}
        self._timeout_sec = timeout_sec

    def is_allowed(self, url: str, user_agent: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._cache:
            robots_url = f"{origin}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                resp = httpx.get(robots_url, timeout=self._timeout_sec, follow_redirects=True)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                    self._cache[origin] = rp
                else:
                    self._cache[origin] = None
            except httpx.HTTPError:
                self._cache[origin] = None
        cached = self._cache[origin]
        if cached is None:
            return True
        return cached.can_fetch(user_agent, url)


class RawCache:
    """Stores raw HTML/JSON responses under raw/{source}/{date}/."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def cache_path(
        self,
        source: str,
        key: str,
        ext: str,
        day: datetime | None = None,
    ) -> Path:
        dt = day or datetime.now(UTC)
        date_str = dt.strftime("%Y-%m-%d")
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return self.base_dir / source / date_str / f"{digest}.{ext.lstrip('.')}"

    def read(self, source: str, key: str, ext: str, day: datetime | None = None) -> str | None:
        path = self.cache_path(source, key, ext, day)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def write(
        self,
        source: str,
        key: str,
        content: str,
        ext: str,
        day: datetime | None = None,
    ) -> Path:
        path = self.cache_path(source, key, ext, day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


class HttpFetcher:
    """Configurable HTTP client with robots.txt, rate limit, retry, UA/proxy rotation, and cache."""

    def __init__(
        self,
        respect_robots_txt: bool = True,
        rate_limiter: DomainRateLimiter | None = None,
        timeout_sec: float = 20.0,
        max_retries: int = 3,
        user_agents: list[str] | None = None,
        proxies: list[str] | None = None,
        raw_cache_dir: Path = Path("raw"),
        use_raw_cache: bool = False,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.respect_robots_txt = respect_robots_txt
        self.rate_limiter = rate_limiter or DomainRateLimiter()
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.user_agents = user_agents or DEFAULT_USER_AGENTS
        self.proxies = proxies or []
        self.raw_cache = RawCache(raw_cache_dir)
        self.use_raw_cache = use_raw_cache
        self.robots = RobotsChecker(timeout_sec=min(10.0, timeout_sec))
        self.transport = transport

    def pick_user_agent(self) -> str:
        return random.choice(self.user_agents)

    def pick_proxy(self) -> str | None:
        return random.choice(self.proxies) if self.proxies else None

    def request(
        self,
        method: str,
        url: str,
        *,
        source: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        cache_ext: str = "html",
        check_robots: bool | None = None,
    ) -> httpx.Response:
        ua = self.pick_user_agent()
        should_check_robots = self.respect_robots_txt if check_robots is None else check_robots
        if should_check_robots and not self.robots.is_allowed(url, ua):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")

        cache_key = f"{method.upper()}:{url}:{params or ''}"
        if self.use_raw_cache:
            cached = self.raw_cache.read(source, cache_key, cache_ext)
            if cached is not None:
                logger.info("Using cached raw payload for %s (%s)", source, url)
                return httpx.Response(
                    status_code=200,
                    text=cached,
                    request=httpx.Request(method, url),
                )

        req_headers = {"User-Agent": ua, **(headers or {})}
        proxy = self.pick_proxy()

        def _do_call() -> httpx.Response:
            client_kwargs: dict[str, Any] = {
                "timeout": self.timeout_sec,
                "follow_redirects": True,
            }
            if self.transport is not None:
                client_kwargs["transport"] = self.transport
            elif proxy:
                client_kwargs["proxy"] = proxy

            with httpx.Client(**client_kwargs) as client:
                return client.request(
                    method=method.upper(),
                    url=url,
                    headers=req_headers,
                    params=params,
                    json=json_body,
                )

        with self.rate_limiter.acquire(url):
            response = with_retry(_do_call, max_attempts=self.max_retries)

        block_reason = detect_block(response.status_code, response.text)
        if block_reason:
            raise BlockedByAntiBotError(f"{source}: {block_reason} at {url}")

        if response.is_success:
            self.raw_cache.write(source, cache_key, response.text, cache_ext)
        return response


class PlaywrightFetcher:
    """Headless Playwright fetcher blocking heavy media and waiting on explicit selectors."""

    BLOCKED_RESOURCE_TYPES = {"image", "font", "media"}

    def __init__(
        self,
        respect_robots_txt: bool = True,
        rate_limiter: DomainRateLimiter | None = None,
        timeout_ms: int = 25000,
        user_agents: list[str] | None = None,
        proxies: list[str] | None = None,
        raw_cache_dir: Path = Path("raw"),
        use_raw_cache: bool = False,
    ) -> None:
        self.respect_robots_txt = respect_robots_txt
        self.rate_limiter = rate_limiter or DomainRateLimiter()
        self.timeout_ms = timeout_ms
        self.user_agents = user_agents or DEFAULT_USER_AGENTS
        self.proxies = proxies or []
        self.raw_cache = RawCache(raw_cache_dir)
        self.use_raw_cache = use_raw_cache
        self.robots = RobotsChecker()

    def fetch_html(
        self,
        url: str,
        *,
        source: str,
        wait_selector: str,
    ) -> str:
        ua = random.choice(self.user_agents)
        if self.respect_robots_txt and not self.robots.is_allowed(url, ua):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")

        if self.use_raw_cache:
            cached = self.raw_cache.read(source, url, "html")
            if cached is not None:
                logger.info("Loaded cached Playwright HTML for %s (%s)", source, url)
                return cached

        from playwright.sync_api import sync_playwright

        with self.rate_limiter.acquire(url), sync_playwright() as p:
            launch_kwargs: dict[str, Any] = {"headless": True}
            if self.proxies:
                launch_kwargs["proxy"] = {"server": random.choice(self.proxies)}
            browser = p.chromium.launch(**launch_kwargs)
            try:
                context = browser.new_context(user_agent=ua)
                page = context.new_page()
                page.route(
                    "**/*",
                    lambda route: (
                        route.abort()
                        if route.request.resource_type in self.BLOCKED_RESOURCE_TYPES
                        else route.continue_()
                    ),
                )
                response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                status_code = response.status if response else 200
                page.wait_for_selector(wait_selector, timeout=self.timeout_ms)
                html = page.content()
                block_reason = detect_block(status_code, html)
                if block_reason:
                    raise BlockedByAntiBotError(f"{source}: {block_reason} at {url}")
                self.raw_cache.write(source, url, html, "html")
                return html
            finally:
                browser.close()
