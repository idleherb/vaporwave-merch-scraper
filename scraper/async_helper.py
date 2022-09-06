import asyncio
import http
import logging
import random
from typing import Any, Coroutine, Generator, Iterable, Optional, Sequence

from aiohttp import ClientSession

from scraper.model import MerchItem, Url

MAX_REQUEST_RETRIES = 12
REQUEST_DELAY_MS = 0.5  # 500ms


async def gather_scraping_results(
        future_results: Generator[Coroutine[Any, Any, Iterable[MerchItem]], Any, None],
        urls: Iterable[str],
) -> Sequence[MerchItem]:
    nested_results = await asyncio.gather(*future_results, return_exceptions=True)
    results: list[MerchItem] = []
    for result_or_exception, url in zip(nested_results, urls):
        if isinstance(result_or_exception, Exception):
            logging.error(f"failed to scrape {url}", exc_info=result_or_exception)
        else:
            results += result_or_exception

    return results


async def request_with_retry(session: ClientSession, url: str, num_try: int = 0) -> Optional[tuple[str, Url]]:
    async with session.get(url) as res:
        if res.status == http.HTTPStatus.OK:
            return await res.text(encoding="utf-8"), str(res.url)
        elif res.status == http.HTTPStatus.NOT_FOUND:
            logging.error(f"failed to reach url {url} ({res.status})")
            return None
        elif res.status == http.HTTPStatus.TOO_MANY_REQUESTS:
            if num_try < MAX_REQUEST_RETRIES:
                num_try += 1
                lower_delay = REQUEST_DELAY_MS * 0.5
                upper_delay = REQUEST_DELAY_MS * 1.5
                actual_delay = 2 ** num_try * random.uniform(lower_delay, upper_delay)
                logging.warning(
                    f"failed to reach url {url}({res.status}), "
                    f"pending retry {num_try} with {actual_delay:.2f}s delay..."
                )
                await asyncio.sleep(actual_delay)
                return await request_with_retry(session=session, url=url, num_try=num_try)
        else:
            logging.error(f"failed to reach url {url} ({res.status}), skipping...")
            return None

    return None
