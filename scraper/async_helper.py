import asyncio
import http
import logging
import random
import weakref
from collections.abc import Coroutine, Generator, Iterable, Sequence
from typing import Any

from scraper.model import MerchItem, Url

MAX_REQUEST_RETRIES = 6
REQUEST_DELAY_MS = 2000  # 2 seconds
MAX_CONCURRENT_REQUESTS = 2
PAUSE_AFTER_REQUEST_S = 1.0
BOT_CHALLENGE_MARKER = "<title>Client Challenge</title>"
CURL_TIMEOUT_S = 60

_request_slots: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()


def _request_slot() -> asyncio.Semaphore:
    """Limit concurrent requests across all label scrapes of the running event loop."""
    loop = asyncio.get_running_loop()
    if loop not in _request_slots:
        _request_slots[loop] = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    return _request_slots[loop]


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


async def _fetch(url: str) -> tuple[int, str, Url]:
    """Fetch a page with curl; Bandcamp serves bot challenges to Python's HTTP clients on datacenter IPs."""
    process = await asyncio.create_subprocess_exec(
        "curl", "--silent", "--show-error", "--location", "--compressed",
        "--max-time", str(CURL_TIMEOUT_S),
        "--write-out", "%{stderr}\n%{http_code} %{url_effective}",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    *errors, status_line = stderr.decode("utf-8", errors="replace").rstrip("\n").split("\n")
    if process.returncode != 0:
        logging.error("curl failed for url %s: %s", url, " ".join(errors).strip())
        return 0, "", url
    status, response_url = status_line.split(" ", 1)
    return int(status), stdout.decode("utf-8", errors="replace"), response_url


async def request_with_retry(url: str) -> tuple[str, Url] | None:
    for num_try in range(MAX_REQUEST_RETRIES + 1):
        async with _request_slot():
            status, text, response_url = await _fetch(url)
            await asyncio.sleep(PAUSE_AFTER_REQUEST_S)

        if status == http.HTTPStatus.OK:
            if BOT_CHALLENGE_MARKER in text:
                logging.error("got bot challenge instead of content for url %s, skipping...", url)
                return None
            return text, response_url

        if status != http.HTTPStatus.TOO_MANY_REQUESTS:
            if status:  # curl errors are already logged
                logging.error("failed to reach url %s (%s), skipping...", url, status)
            return None

        if num_try < MAX_REQUEST_RETRIES:
            lower_delay = REQUEST_DELAY_MS * 0.5
            upper_delay = REQUEST_DELAY_MS * 1.5
            actual_delay = 2 ** (num_try + 1) * random.uniform(lower_delay, upper_delay) / 1000
            logging.warning(
                "failed to reach url %s (%s), pending retry %s with %.1fs delay...",
                url,
                status,
                num_try + 1,
                actual_delay,
            )
            await asyncio.sleep(actual_delay)

    logging.error("giving up on url %s after %s retries", url, MAX_REQUEST_RETRIES)
    return None
