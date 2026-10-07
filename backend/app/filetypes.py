"""Upload type checks from the bytes themselves, never from the file name or the browser's claimed type.

`sniff` returns the type the content really is, or None. An upload is accepted only when that type is allowed for its
kind and agrees with the claimed type's family (image, audio, PDF). SVG is accepted only for the app's own sample
reports and only without scripts, event handlers or external references.
"""

import re

_SIGNATURES: list[tuple[bytes, int, str]] = [
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"GIF87a", 0, "image/gif"),
    (b"GIF89a", 0, "image/gif"),
    (b"%PDF-", 0, "application/pdf"),
    (b"\x1a\x45\xdf\xa3", 0, "audio/webm"),  # Matroska / WebM (browser recordings)
    (b"OggS", 0, "audio/ogg"),
    (b"fLaC", 0, "audio/flac"),
    (b"ID3", 0, "audio/mpeg"),
]
_FTYP_IMAGE = {b"heic", b"heix", b"heif", b"mif1", b"msf1", b"avif"}
_FTYP_AUDIO = {b"M4A ", b"mp42", b"isom", b"iso5", b"iso6", b"dash", b"3gp4", b"3gp5", b"mp41"}
_SVG_DANGER = re.compile(rb"<script|\bon[a-z]+\s*=|javascript:|<foreignObject|<iframe|<embed|<object|xlink:href\s*=\s*[\"'](?!#)|href\s*=\s*[\"']https?:", re.I)


def sniff(data: bytes) -> str | None:
    head = data[:64]
    for sig, off, mime in _SIGNATURES:
        if head[off:off + len(sig)] == sig:
            return mime
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in _FTYP_IMAGE:
            return "image/heic"
        if brand in _FTYP_AUDIO:
            return "audio/mp4"
    if len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0:
        return "audio/mpeg"  # MPEG audio frame
    text = data[:512].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if text.startswith((b"<svg", b"<?xml")) and b"<svg" in data[:4096].lower():
        return "image/svg+xml"
    return None


def family(mime: str) -> str:
    return "pdf" if mime == "application/pdf" else "audio" if mime.startswith(("audio/", "video/webm")) else mime.split("/")[0]


def safe_svg(data: bytes) -> bool:
    return not _SVG_DANGER.search(data)


def check(data: bytes, claimed: str, allowed: tuple[str, ...], sample: bool = False) -> str:
    """The real content type, or ValueError with a reason fit to show the user."""
    real = sniff(data)
    if real is None:
        raise ValueError("The file's contents are not a recognised image, PDF or recording")
    if not real.startswith(allowed):
        raise ValueError(f"The file's contents are {real}, which is not allowed here")
    if family(real) != family(claimed):
        raise ValueError(f"The file says it is {claimed} but its contents are {real}")
    if real == "image/svg+xml" and not (sample and safe_svg(data)):
        raise ValueError("SVG images are not accepted")
    return real
