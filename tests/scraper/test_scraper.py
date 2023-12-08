from functools import partial
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from pytest_unordered import unordered

from scraper.filesystem_helper import resources_dir
from scraper.model import MerchItem
from scraper.scraper import scrape_label_merch_url

tests_resources_dir = resources_dir / "tests"


@pytest.fixture()
def label_merch_3_unique_merch_paths_html() -> str:
    with (tests_resources_dir / "label_merch_3_unique_merch_paths.html").open() as f:
        return f.read()


@pytest.fixture()
def merch_item_25_available_cassette_and_vinyl_html() -> str:
    with (tests_resources_dir / "--25_merch_item_available_cassette_and_vinyl.html").open() as f:
        return f.read()


@pytest.fixture()
def merch_item_26_available_cassette_and_soldout_vinyl_html() -> str:
    with (tests_resources_dir / "--26_merch_item_available_cassette_and_soldout_vinyl.html").open() as f:
        return f.read()


@pytest.fixture()
def merch_item_blue_album_available_vinyl_and_soldout_cassette_html() -> str:
    with (tests_resources_dir / "blue-album_merch_item_available_vinyl_and_soldout_cassette.html").open() as f:
        return f.read()


@pytest.fixture()
def merch_item_pink_album_available_vinyl_and_soldout_cassette_html() -> str:
    with (tests_resources_dir / "pink-album_merch_item_available_vinyl_and_soldout_cassette.html").open() as f:
        return f.read()


@pytest.fixture()
async def mock_server(  # noqa: PLR0913
        aiohttp_server: Any,  # noqa: ANN401
        label_merch_3_unique_merch_paths_html: str,
        merch_item_25_available_cassette_and_vinyl_html: str,
        merch_item_26_available_cassette_and_soldout_vinyl_html: str,
        merch_item_blue_album_available_vinyl_and_soldout_cassette_html: str,
        merch_item_pink_album_available_vinyl_and_soldout_cassette_html: str,
) -> TestServer:
    async def handler(_: web.Request, html: str) -> web.Response:
        return web.Response(text=html)

    app = web.Application()
    app.add_routes([web.get(
        "/test_label_merch_url",
        partial(handler, html=label_merch_3_unique_merch_paths_html)),
    ])
    app.add_routes([web.get(
        "/album/--25",
        partial(handler, html=merch_item_25_available_cassette_and_vinyl_html)),
    ])
    app.add_routes([web.get(
        "/album/--26",
        partial(handler, html=merch_item_26_available_cassette_and_soldout_vinyl_html)),
    ])
    app.add_routes([web.get(
        "/album/blue-album",
        partial(handler, html=merch_item_blue_album_available_vinyl_and_soldout_cassette_html)),
    ])
    app.add_routes([web.get(
        "/album/pink-album",
        partial(handler, html=merch_item_pink_album_available_vinyl_and_soldout_cassette_html)),
    ])

    return await aiohttp_server(app)


async def test_scrape_label_merch_url(mock_server: TestServer) -> None:
    url = str(mock_server.make_url("/test_label_merch_url"))
    actual_merch_items = list(await scrape_label_merch_url(url))
    expected_merch_items = \
        [
            MerchItem(
                artist="t e l e p a t h テレパシー能力者",
                currency="USD",
                edition_of=None,
                id=2281430982,
                image_id=29606615,
                label="Geometric Lullaby",
                merch_type="Cassette",
                price=15.0,
                release_date="23 Aug 2022 02:32:07 GMT",
                remaining=None,
                timestamp="2022-09-07T11:12:09.227903",
                title="現実を超えて",
                url="https://geometriclullaby.bandcamp.com/album/--26",
            ),
            MerchItem(
                artist="鬱",
                currency="USD",
                edition_of=333,
                id=965252114,
                image_id=29195359,
                label="Geometric Lullaby",
                merch_type="Vinyl",
                price=35.0,
                release_date="25 Jan 2022 19:45:57 GMT",
                remaining=88,
                timestamp="2022-09-07T11:12:09.266830",
                title="・過世的購物中心蕭條導瀉檔案完畢世界・  (Blue Album)",
                url="https://geometriclullaby.bandcamp.com/album/blue-album",
            ),
            MerchItem(
                artist="t e l e p a t h テレパシー能力者",
                currency="USD",
                edition_of=None,
                id=2963618744,
                image_id=29606590,
                label="Geometric Lullaby",
                merch_type="Cassette",
                price=15.0,
                release_date="23 Aug 2022 02:28:52 GMT",
                remaining=None,
                timestamp="2022-09-07T11:12:09.293530",
                title="アンタラ通信",
                url="https://geometriclullaby.bandcamp.com/album/--25",
            ),
            MerchItem(
                artist="t e l e p a t h テレパシー能力者",
                currency="USD",
                edition_of=None,
                id=524554060,
                image_id=26919027,
                label="Geometric Lullaby",
                merch_type="Vinyl",
                price=44.44,
                release_date="23 Nov 2021 08:52:26 GMT",
                remaining=78,
                timestamp="2022-09-07T11:12:09.293530",
                title="アンタラ通信",
                url="https://geometriclullaby.bandcamp.com/album/--25",
            ),
            MerchItem(
                artist="鬱",
                currency="USD",
                edition_of=333,
                id=401367820,
                image_id=29195372,
                label="Geometric Lullaby",
                merch_type="Vinyl",
                price=30.0,
                release_date="25 Jan 2022 19:48:11 GMT",
                remaining=71,
                timestamp="2022-09-07T11:12:09.319782",
                title="・薔薇綺麗躊躇網羅就職痙攣蝋燭鷹麟爨齉馕龘爨齉龘・  (Pink Album)",
                url="https://geometriclullaby.bandcamp.com/album/pink-album",
            ),
        ]

    assert actual_merch_items == unordered(expected_merch_items)
