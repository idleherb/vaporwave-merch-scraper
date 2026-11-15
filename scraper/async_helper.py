import asyncio
import http
import logging
import weakref
from collections.abc import Coroutine, Generator, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from scraper.model import MerchItem, Url

MAX_REQUEST_RETRIES = 8
INITIAL_PAUSE_AFTER_REQUEST_S = 1.0
MAX_PAUSE_AFTER_REQUEST_S = 10.0
PAUSE_GROWTH_ON_RATE_LIMIT = 1.5
INITIAL_COOLDOWN_S = 30.0
MAX_COOLDOWN_S = 15 * 60.0
BOT_CHALLENGE_MARKER = "<title>Client Challenge</title>"
CURL_TIMEOUT_S = 60


@dataclass
class _Throttle:
    """Pace all requests of one event loop and back off together when Bandcamp rate limits us."""

    slot: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(1))
    pause_s: float = INITIAL_PAUSE_AFTER_REQUEST_S
    cooldown_until: float = 0.0
    consecutive_rate_limits: int = 0

    def on_success(self) -> None:
        self.consecutive_rate_limits = 0

    def on_rate_limit(self, retry_after_s: float | None) -> float:
        cooldown_s = min(INITIAL_COOLDOWN_S * 2.0 ** self.consecutive_rate_limits, MAX_COOLDOWN_S)
        if retry_after_s is not None:
            cooldown_s = max(cooldown_s, retry_after_s)
        self.consecutive_rate_limits += 1
        self.pause_s = min(self.pause_s * PAUSE_GROWTH_ON_RATE_LIMIT, MAX_PAUSE_AFTER_REQUEST_S)
        self.cooldown_until = asyncio.get_running_loop().time() + cooldown_s
        return cooldown_s

    async def wait_for_cooldown(self) -> None:
        remaining_s = self.cooldown_until - asyncio.get_running_loop().time()
        if remaining_s > 0:
            await asyncio.sleep(remaining_s)


_throttles: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, _Throttle]" = weakref.WeakKeyDictionary()


def _throttle() -> _Throttle:
    loop = asyncio.get_running_loop()
    if loop not in _throttles:
        _throttles[loop] = _Throttle()
    return _throttles[loop]


async def gather_scraping_results(
        future_results: Generator[Coroutine[Any, Any, Iterable[MerchItem]], Any, None],
        urls: Iterable[str],
) -> Sequence[MerchItem]:
    nested_results = await asyncio.gather(*future_results, return_exceptions=True)
    results: list[MerchItem] = []
    for result_or_exception, url in zip(nested_results, urls, strict=True):
        if isinstance(result_or_exception, BaseException):
            logging.error("failed to scrape %s", url, exc_info=result_or_exception)
        else:
            results += result_or_exception

    return results


async def _fetch(url: str) -> tuple[int, float | None, str, Url]:
    """Fetch a page with curl; Bandcamp serves bot challenges to Python's HTTP clients on datacenter IPs."""
    process = await asyncio.create_subprocess_exec(
        "curl", "--silent", "--show-error", "--location", "--compressed",
        "--max-time", str(CURL_TIMEOUT_S),
        "--write-out", "%{stderr}\n%{http_code} %header{retry-after} %{url_effective}",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    *errors, status_line = stderr.decode("utf-8", errors="replace").rstrip("\n").split("\n")
    if process.returncode != 0:
        logging.error("curl failed for url %s: %s", url, " ".join(errors).strip())
        return 0, None, "", url
    status, retry_after, response_url = status_line.split(" ", 2)
    retry_after_s = float(retry_after) if retry_after.isdigit() else None
    return int(status), retry_after_s, stdout.decode("utf-8", errors="replace"), response_url


async def request_with_retry(url: str) -> tuple[str, Url] | None:
    throttle = _throttle()
    for num_try in range(MAX_REQUEST_RETRIES + 1):
        async with throttle.slot:
            await throttle.wait_for_cooldown()
            status, retry_after_s, text, response_url = await _fetch(url)
            if status == http.HTTPStatus.TOO_MANY_REQUESTS:
                cooldown_s = throttle.on_rate_limit(retry_after_s)
                logging.warning(
                    "rate limited on url %s (try %s), pausing all requests for %.0fs, "
                    "then %.1fs between requests...",
                    url,
                    num_try + 1,
                    cooldown_s,
                    throttle.pause_s,
                )
                continue
            throttle.on_success()
            await asyncio.sleep(throttle.pause_s)

        if status == http.HTTPStatus.OK:
            if BOT_CHALLENGE_MARKER in text:
                logging.error("got bot challenge instead of content for url %s, skipping...", url)
                return None
            return text, response_url

        if status:  # curl errors are already logged
            logging.error("failed to reach url %s (%s), skipping...", url, status)
        return None

    logging.error("giving up on url %s after %s retries", url, MAX_REQUEST_RETRIES)
    return None
