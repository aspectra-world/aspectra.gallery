# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright © 2026 lucya.systems — https://lucya.systems
"""The rest of Aperture as pages Lucent draws (console/lucent_pages.py):
every page answers, and the writes go through the console's own steps."""

import base64
import json

import pytest

from aperture.console import lucent, security
from aperture.runtime import settings

from test_lucent import PASSWORD, bearer, paired  # noqa: F401  (the fixture)

BY = {"sub": "1", "email": "lucya@example.org", "name": "Lucya"}


@pytest.fixture
def keep_tech():
    """Put tech/.album back the way it was: these tests write to it."""
    meta = settings.photos_dir / "tech" / ".album"
    before = {p.name: p.read_bytes() for p in meta.iterdir() if p.is_file()} if meta.is_dir() else {}
    gallery = settings.photos_dir / ".gallery" / "gallery.cfg"
    gallery_before = gallery.read_bytes() if gallery.is_file() else None
    yield
    if meta.is_dir():
        for p in meta.iterdir():
            if p.is_file() and p.name not in before:
                p.unlink()
    for name, data in before.items():
        (meta / name).write_bytes(data)
    if gallery_before is None:
        gallery.unlink(missing_ok=True)
    else:
        gallery.write_bytes(gallery_before)


def do(client, fake, page, action, values=None, files=None):
    return client.post(f"/lucent/v1/pages/{page}/do/{action}", headers=bearer(fake),
                       json={"values": values or {}, "files": files or [], "by": BY})


def test_manifest_names_the_pages_and_the_photo_actions(paired):
    fake, client = paired
    m = client.get("/lucent/v1/manifest", headers=bearer(fake)).json()
    assert [p["id"] for p in m["pages"]] == ["uebersicht", "alben", "website", "system"]
    assert m["media"]["actions"] is True and m["media"]["album_page"] == "alben"
    assert {b["id"] for b in m["media"]["bulk"]} == {"feature", "unfeature"}


@pytest.mark.parametrize("path", [
    "uebersicht", "alben", "alben?v_filter=probleme", "alben?v_album=berlin",
    "alben?v_album=berlin&v_tab=fotos", "alben?v_album=berlin&v_tab=aussehen", "alben?v_album=berlin&v_tab=text",
    "alben?v_album=berlin&v_tab=dateien", "alben?v_album=berlin&v_tab=roh", "alben?v_album=berlin&v_tab=verlauf",
    "website", "website?v_tab=aussehen", "website?v_tab=startseite", "website?v_tab=footer",
    "website?v_tab=dateien", "website?v_tab=roh", "website?v_tab=verlauf",
    "system", "system?v_tab=speicher", "system?v_tab=pruefung", "system?v_tab=pruefung&v_run=1",
    "system?v_tab=datenschutz&v_run=1", "system?v_tab=sicherung", "system?v_tab=aktivitaet",
    "system?v_tab=tags", "system?v_tab=passwort", "system?v_tab=ueber"])
def test_every_page_answers(paired, path):
    fake, client = paired
    r = client.get(f"/lucent/v1/pages/{path}", headers=bearer(fake))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] and isinstance(body["sections"], list)
    json.dumps(body)


def test_pages_need_the_connector_secret(paired):
    _, client = paired
    assert client.get("/lucent/v1/pages/alben").status_code == 401
    assert client.post("/lucent/v1/pages/alben/do/cfg", json={}).status_code == 401


def test_a_tab_saves_its_keys_through_the_console_and_audits_the_person(paired, keep_tech):
    fake, client = paired
    r = do(client, fake, "alben", "cfg", {"album": "tech", "_keys": "name,showcase,tags,stat",
                                            "name": "Tech, Desk", "showcase": "true", "tags": "a, b",
                                            "stat": "Kamera: Fuji\nOrt: Wien"})
    assert r.status_code == 200, r.text
    text = (settings.photos_dir / "tech" / ".album" / "album.cfg").read_text()
    assert "name = Tech, Desk" in text and "showcase = true" in text and "stat = Kamera: Fuji" in text
    assert security.recent(1)[0]["by"] == "lucent:lucya@example.org"
    # an emptied field drops its line
    do(client, fake, "alben", "cfg", {"album": "tech", "_keys": "showcase", "showcase": ""})
    assert "showcase" not in (settings.photos_dir / "tech" / ".album" / "album.cfg").read_text()


def test_featured_list_add_move_remove_and_cover(paired, keep_tech):
    fake, client = paired
    for name in ("desk.jpg", "rack.jpg"):
        do(client, fake, "alben", "featured_add", {"album": "tech", "entry": name})
    do(client, fake, "alben", "featured_move", {"album": "tech", "entry": "rack.jpg", "dir": "up"})
    text = (settings.photos_dir / "tech" / ".album" / "album.cfg").read_text()
    assert text.index("rack.jpg") < text.index("desk.jpg")
    do(client, fake, "alben", "cover_set", {"album": "tech", "entry": "rack.jpg"})
    do(client, fake, "alben", "featured_remove", {"album": "tech", "entry": "desk.jpg"})
    text = (settings.photos_dir / "tech" / ".album" / "album.cfg").read_text()
    assert "cover = rack.jpg" in text and "desk.jpg" not in text


def test_raw_history_and_restore(paired, keep_tech):
    fake, client = paired
    do(client, fake, "alben", "raw", {"album": "tech", "raw": "name = Eins\n"})
    do(client, fake, "alben", "raw", {"album": "tech", "raw": "name = Zwei\n"})
    page = client.get("/lucent/v1/pages/alben?v_album=tech&v_tab=verlauf", headers=bearer(fake)).json()
    versions = next(s for s in page["sections"] if s["id"] == "versions")["items"]
    restore = versions[0]["actions"][0]
    assert do(client, fake, "alben", "restore", restore["values"]).status_code == 200
    assert (settings.photos_dir / "tech" / ".album" / "album.cfg").read_text() == "name = Eins\n"


def test_upload_an_icon_and_a_text_then_delete(paired, keep_tech):
    fake, client = paired
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'
    files = [{"name": "icon.svg", "type": "image/svg+xml", "data_b64": base64.b64encode(svg).decode()},
             {"name": "album_de.md", "type": "text/markdown", "data_b64": base64.b64encode("Hallo".encode()).decode()}]
    r = do(client, fake, "alben", "upload", {"album": "tech"}, files)
    assert r.status_code == 200, r.text
    meta = settings.photos_dir / "tech" / ".album"
    assert (meta / "icon.svg").is_file() and (meta / "album_de.md").read_text().strip() == "Hallo"
    assert client.get("/lucent/v1/pages/alben/file/a/tech/icon.svg", headers=bearer(fake)).status_code == 200
    do(client, fake, "alben", "asset_delete", {"album": "tech", "name": "icon.svg"})
    assert not (meta / "icon.svg").exists()


def test_a_bad_upload_is_the_tools_sentence(paired, keep_tech):
    fake, client = paired
    files = [{"name": "evil.exe", "type": "application/octet-stream", "data_b64": base64.b64encode(b"MZ").decode()}]
    r = do(client, fake, "alben", "upload", {"album": "tech"}, files)
    assert r.status_code == 422


def test_bulk_key_on_many_albums_is_all_or_nothing(paired, keep_tech):
    fake, client = paired
    r = do(client, fake, "alben", "bulk", {"key": "unlisted", "value": "true", "albums": "tech\nno_such_album"})
    assert r.status_code == 422
    assert "unlisted" not in ((settings.photos_dir / "tech" / ".album" / "album.cfg").read_text()
                              if (settings.photos_dir / "tech" / ".album" / "album.cfg").exists() else "")
    r = do(client, fake, "alben", "bulk", {"key": "unlisted", "value": "true", "albums": "tech"})
    assert r.status_code == 200
    assert "unlisted = true" in (settings.photos_dir / "tech" / ".album" / "album.cfg").read_text()


def test_site_tab_writes_gallery_cfg(paired, keep_tech):
    fake, client = paired
    r = do(client, fake, "website", "cfg", {"_keys": "site_name,album_order",
                                             "site_name": "Archiv", "album_order": "#Reisen\nberlin\ntech"})
    assert r.status_code == 200, r.text
    text = (settings.photos_dir / ".gallery" / "gallery.cfg").read_text()
    assert "site_name = Archiv" in text and "#Reisen" in text


def test_indexer_actions_go_through_the_control_channel(paired):
    fake, client = paired
    assert do(client, fake, "system", "scan", {"album": "tech"}).status_code == 200
    assert do(client, fake, "system", "pause", {"reason": "Umzug"}).json()["notice"] == "Indexer pausiert."
    assert "Indexer" in do(client, fake, "system", "resume", {}).json()["notice"]
    assert do(client, fake, "system", "job_rebuild", {"album": "", "all": "1"}).status_code == 200
    assert do(client, fake, "system", "job_nope", {}).status_code == 422


def test_backup_downloads_as_an_archive(paired):
    fake, client = paired
    r = client.get("/lucent/v1/pages/system/download/config.tar.gz", headers=bearer(fake))
    assert r.status_code == 200 and r.headers["content-type"] == "application/gzip"
    assert r.content[:2] == b"\x1f\x8b"


def test_password_change_needs_the_current_one(paired):
    fake, client = paired

    bad = do(client, fake, "system", "password", {"current": "wrong", "password": "x" * 16, "again": "x" * 16})
    assert bad.status_code == 422
    ok = do(client, fake, "system", "password", {"current": PASSWORD, "password": "y" * 16, "again": "y" * 16})
    assert ok.status_code == 200, ok.text
    assert security.verify_password("y" * 16)


def test_photo_page_extras_and_actions(paired, keep_tech):
    fake, client = paired
    from aperture import db
    pid = db.conn().execute("SELECT id FROM images WHERE rel_path = 'tech/rack.jpg'").fetchone()[0]
    d = client.get(f"/lucent/v1/media/{pid}", headers=bearer(fake)).json()
    assert {a["id"] for a in d["actions"]} >= {"feature", "cover", "link"}
    assert any(s["id"] == "diag" for s in d["sections"])
    r = client.post(f"/lucent/v1/media/{pid}/do/feature", headers=bearer(fake), json={"values": {}, "by": BY})
    assert r.status_code == 200, r.text
    assert "rack.jpg" in (settings.photos_dir / "tech" / ".album" / "album.cfg").read_text()
    r = client.post("/lucent/v1/media/bulk/do/unfeature", headers=bearer(fake), json={"ids": [pid], "by": BY})
    assert r.status_code == 200
    assert "rack.jpg" not in (settings.photos_dir / "tech" / ".album" / "album.cfg").read_text()


def test_search_speaks_the_librarys_grammar(paired):
    fake, client = paired
    r = client.get("/lucent/v1/media?q=tag:workspace", headers=bearer(fake)).json()
    assert [i["title"] for i in r["items"]] == ["desk.jpg"]
    r = client.get("/lucent/v1/media?q=album:berlin%20is:featured", headers=bearer(fake)).json()
    assert r["total"] >= 1 and all(i["album"].startswith("berlin") for i in r["items"])
