from datetime import date

from app.yerr_client import parse_yerr_response


def test_parse_yerr_response_maps_listing_fields():
    data = {
        "listings": [
            {
                "id": "abc",
                "sourcePlatform": "reddit",
                "sourceUrl": "https://www.reddit.com/r/NYCapartments/comments/abc/demo/",
                "sourceId": "abc",
                "price": "2250.00",
                "borough": "queens",
                "neighborhood": "jackson_heights",
                "listingType": "sublet",
                "isRoomOnly": True,
                "availableAt": "2026-10-01T00:00:00.000Z",
                "isFurnished": True,
                "amenities": ["laundry", "near train"],
                "title": "Furnished Jackson Heights room",
            }
        ],
        "meta": {"total": 180, "has_more": False},
    }

    listings, total, has_more = parse_yerr_response(data)

    assert total == 180
    assert has_more is False
    assert len(listings) == 1
    assert listings[0].source == "yerr:reddit"
    assert listings[0].price == 2250
    assert listings[0].available_from == date(2026, 10, 1)
    assert listings[0].neighborhood == "Jackson Heights"
    assert listings[0].listing_type == "private_room"
    assert listings[0].furnished is True
