from dataclasses import dataclass, field
from typing import Optional

from dataclasses_json import LetterCase, dataclass_json

Url = str


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(frozen=True)
class MerchItem:
    artist: str
    currency: str
    edition_of: Optional[int]
    id: int
    image_id: int
    label: str
    merch_type: str
    price: float
    release_date: str
    remaining: Optional[int]
    timestamp: str = field(compare=False)
    title: str
    url: Url
