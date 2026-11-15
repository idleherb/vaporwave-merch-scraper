from dataclasses import dataclass, field

from dataclasses_json import DataClassJsonMixin, LetterCase, config

Url = str


@dataclass(frozen=True)
class MerchItem(DataClassJsonMixin):
    dataclass_json_config = config(letter_case=LetterCase.CAMEL)["dataclasses_json"]

    artist: str
    currency: str
    edition_of: int | None
    id: int
    image_id: int
    label: str
    merch_type: str
    price: float
    release_date: str
    remaining: int | None
    timestamp: str = field(compare=False)
    title: str
    url: Url
