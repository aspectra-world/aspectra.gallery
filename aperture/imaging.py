# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright © 2026 lucya.systems — https://lucya.systems
"""The one way a file in the photo tree is opened for decoding.

`Image.open` picks a decoder by what the bytes look like, not by the
extension: a `photo.jpg` that is really a FlashPix, PSD, EPS or TGA file goes
straight into that format's decoder. Pillow carries some forty of them, and
most of its memory-safety advisories live in the ones no camera writes. So
the decoders a photograph -- or a mark, a thumbnail, a backdrop -- may reach
are listed here, and nothing else is ever tried.
"""

from __future__ import annotations

from PIL import Image

# What a camera, a phone or an export writes. MPO is how many cameras (and
# iPhones) store a JPEG; HEIF/AVIF arrive through pillow-heif or Pillow's own
# AVIF plugin when either is installed.
PHOTO_FORMATS = ("JPEG", "MPO", "PNG", "WEBP", "GIF", "TIFF", "BMP", "HEIF", "AVIF")


def _registered() -> list[str]:
    # Image.open raises KeyError for a name nobody registered, and HEIF is
    # registered at runtime (pillow_heif.register_heif_opener), so the list is
    # filtered per call rather than once at import.
    Image.init()
    return [f for f in PHOTO_FORMATS if f in Image.OPEN]


def open_image(path, *, formats=None):
    """`Image.open` restricted to PHOTO_FORMATS (or the narrower `formats`).
    A file in any other format raises PIL.UnidentifiedImageError, which every
    caller already treats as "cannot decode"."""
    allowed = _registered() if formats is None else [f for f in _registered() if f in formats]
    return Image.open(path, formats=allowed)
