import json

from scraper.model import MerchItem


def test_should_convert_merch_details_to_json() -> None:
    given_merch_item = MerchItem(
        artist="test_artist",
        currency="test_currency",
        edition_of=1,
        id=2,
        image_id=3,
        label="test_label",
        merch_type="test_merch_type",
        price=4.5,
        release_date="test_release_date",
        remaining=6,
        timestamp="test_timestamp",
        title="test_title",
        url="test_url",
    )
    expected_json = json.dumps({
        "artist": "test_artist",
        "currency": "test_currency",
        "editionOf": 1,
        "id": 2,
        "imageId": 3,
        "label": "test_label",
        "merchType": "test_merch_type",
        "price": 4.5,
        "releaseDate": "test_release_date",
        "remaining": 6,
        "timestamp": "test_timestamp",
        "title": "test_title",
        "url": "test_url",
    })

    actual_json = given_merch_item.to_json()  # type: ignore[attr-defined]

    assert actual_json == expected_json
