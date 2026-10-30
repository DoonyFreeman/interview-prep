"""Download links must have real PDF assets, not the SPA fallback page."""
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from app import main


def test_every_cheatsheet_has_a_real_pdf():
    frontend = Path(__file__).resolve().parents[2] / "frontend"
    markdown = frontend / "src" / "content" / "cheatsheets"
    downloads = frontend / "public" / "cheatsheets"
    sheets = {path.stem for path in markdown.glob("*.md")}
    pdfs = {path.stem for path in downloads.glob("*.pdf")}
    assert len(sheets) == 6
    assert pdfs == sheets
    for slug in sheets:
        with (downloads / f"{slug}.pdf").open("rb") as stream:
            assert stream.read(5) == b"%PDF-", slug


async def test_pdf_downloads_and_reader_routes_share_the_production_origin(tmp_path, monkeypatch):
    frontend = Path(__file__).resolve().parents[2] / "frontend"
    static = tmp_path / "static"
    downloads = static / "cheatsheets"
    downloads.mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    for source in (frontend / "public" / "cheatsheets").glob("*.pdf"):
        (downloads / source.name).write_bytes(source.read_bytes())
    monkeypatch.setattr(main, "STATIC_DIR", static)

    async with AsyncClient(transport=ASGITransport(app=main.create_app()), base_url="http://test") as client:
        for path in ("/cheatsheets", "/cheatsheets/ml-metrics", "/progress"):
            response = await client.get(path)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/html")
        for pdf in downloads.glob("*.pdf"):
            response = await client.get(f"/cheatsheets/{pdf.name}")
            assert response.status_code == 200, pdf.name
            assert response.headers["content-type"] == "application/pdf"
            assert response.content == pdf.read_bytes()
