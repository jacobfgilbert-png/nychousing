from pathlib import Path
from tempfile import TemporaryDirectory

from app.bulk_import import import_bulk_dir, import_bulk_file


def test_import_bulk_file_reads_csv():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "facebook_export.csv"
        path.write_text(
            "title,price,neighborhood,url,furnished,email\n"
            "Furnished Astoria room,$1800,Astoria,https://example.com/1,true,owner@example.com\n",
            encoding="utf-8",
        )

        listings = import_bulk_file(path)

    assert len(listings) == 1
    assert listings[0].source == "facebook"
    assert listings[0].price == 1800
    assert listings[0].neighborhood == "Astoria"
    assert listings[0].furnished is True
    assert listings[0].contact_method == "email"


def test_import_bulk_dir_reads_multiple_supported_files():
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "leasebreak.json").write_text(
            '[{"title": "Furnished Inwood studio", "rent": 2200, "link": "https://example.com/2", "location": "Inwood"}]',
            encoding="utf-8",
        )
        (tmp_path / "notes.txt").write_text(
            "Listing: Furnished room in Jackson Heights $1600 https://example.com/3",
            encoding="utf-8",
        )
        (tmp_path / "ignore.pdf").write_text("not read", encoding="utf-8")

        listings, stats = import_bulk_dir(tmp_path)

    assert stats.scanned_files == 2
    assert stats.imported_items == 2
    assert stats.failed_files == 0
    assert {listing.source for listing in listings} == {"leasebreak", "bulk_import"}
