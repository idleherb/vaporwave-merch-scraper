import asyncio
import logging
from typing import Any, Coroutine, Generator, Iterable, Sequence

from scraper.model import MerchDetails


async def gather_scraping_results(
        future_results: Generator[Coroutine[Any, Any, Iterable[MerchDetails]], Any, None],
        urls: Iterable[str],
) -> Sequence[MerchDetails]:
    nested_results = await asyncio.gather(*future_results, return_exceptions=True)
    results: list[MerchDetails] = []
    for result_or_exception, url in zip(nested_results, urls):
        if isinstance(result_or_exception, Exception):
            logging.error(f"failed to scrape {url}", exc_info=result_or_exception)
        else:
            results += result_or_exception

    return results
