import asyncio
import http
import logging
import random
from collections.abc import Coroutine, Generator, Iterable, Sequence
from typing import Any

from aiohttp import ClientSession

from scraper.model import MerchItem, Url

MAX_REQUEST_RETRIES = 12
REQUEST_DELAY_MS = 2000  # 2 seconds


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


async def request_with_retry(session: ClientSession, url: str, num_try: int = 0) -> tuple[str, Url] | None:
    async with session.get(url) as res:
        if res.status == http.HTTPStatus.OK:
            return await res.text(encoding="utf-8"), str(res.url)

        if res.status == http.HTTPStatus.NOT_FOUND:
            logging.error("failed to reach url %s (%s)", url, res.status)
            return None

        if res.status == http.HTTPStatus.TOO_MANY_REQUESTS:
            if num_try < MAX_REQUEST_RETRIES:
                num_try += 1
                lower_delay = REQUEST_DELAY_MS * 0.5
                upper_delay = REQUEST_DELAY_MS * 1.5
                actual_delay = 2 ** num_try * random.uniform(lower_delay, upper_delay)
                logging.warning(
                    "failed to reach url %s(%s), "
                    "pending retry %s with %s delay...",
                    url,
                    res.status,
                    num_try,
                    actual_delay,
                )
                await asyncio.sleep(actual_delay)
                return await request_with_retry(session=session, url=url, num_try=num_try)
        else:
            logging.error("failed to reach url %s (%s), skipping...", url, res.status)
            return None

    return None
