#!/usr/bin/env python3
"""Check image alt text in local HTML files, fail CI on a missing alt.

Run: python3 src/image_alt_checker.py docs/
     python3 src/image_alt_checker.py page.html

The tool reads local HTML files and checks one rule: every <img>
must have an alt attribute, and the alt text must not be empty.
Every problem names the file and the exact line it is on. The tool
exits 1 when any file fails, so it can fail a CI run.

It is report-only: it never rewrites a file, and it runs fully
offline. It sends nothing anywhere and needs no API key.

Images are found with the standard-library ``html.parser``, so an
<img> inside a comment, a <script> block, or a <style> block is
not counted.

Exit codes: 0 when every file passes, 1 when any file fails,
2 for a usage or input problem (missing file, bad flag, no files).
"""

import argparse
import contextlib
import sys
from html.parser import HTMLParser
from pathlib import Path

VERSION = "1.0.0"

HTML_EXTS = {".html", ".htm"}


class Image:
    """One <img> tag: its line, its src, and its alt (or None)."""

    def __init__(self, line, src, alt):
        self.line = line
        self.src = src
        self.alt = alt

    def __repr__(self):
        return "Image(line %d, src=%r, alt=%r)" % (
            self.line,
            self.src,
            self.alt,
        )


class _HtmlImageParser(HTMLParser):
    """Collect <img> tags with their line numbers and attributes.

    Tags inside comments, <script> and <style> blocks are not
    reported: HTMLParser treats those as data, not tags.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        line, _ = self.getpos()
        values = dict(attrs)
        self.images.append(
            Image(line, values.get("src", ""), values.get("alt"))
        )


def extract_images(text):
    """Return the list of <img> tags in one HTML document."""
    parser = _HtmlImageParser()
    parser.feed(text)
    parser.close()
    return parser.images


def _describe(image):
    """Short label for one image, used in problem messages."""
    if image.src:
        return '<img src="%s">' % image.src
    return "<img>"


def check_images(images, allow_empty_alt=False):
    """Check one list of images. Returns a list of problem strings."""
    problems = []
    for image in images:
        if image.alt is None:
            problems.append(
                "line %d: %s has no alt attribute"
                % (image.line, _describe(image))
            )
        elif image.alt.strip() == "" and not allow_empty_alt:
            problems.append(
                "line %d: %s has an empty alt attribute"
                % (image.line, _describe(image))
            )
    return problems


def check_file(path, allow_empty_alt=False):
    """Check one file. Returns a list of problem strings (empty = pass)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return ["cannot read file: %s" % exc]
    except UnicodeDecodeError:
        return ["file is not valid UTF-8 text"]
    suffix = path.suffix.lower()
    if suffix not in HTML_EXTS:
        return ["unknown file type (use .html or .htm)"]
    return check_images(extract_images(text), allow_empty_alt)


def collect_files(paths, recursive=True):
    """Expand paths into a sorted list of HTML files.

    A path may be a file or a directory. Directories are scanned for
    ``.html`` and ``.htm`` files, recursively when ``recursive`` is
    true. Returns (files, problems) where problems are usage errors.
    """
    files = []
    problems = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            problems.append("no such file or directory: %s" % raw)
            continue
        if path.is_file():
            files.append(path)
            continue
        if recursive:
            found = []
            for ext in (".html", ".htm"):
                found.extend(path.rglob("*" + ext))
        else:
            found = []
            for ext in (".html", ".htm"):
                found.extend(path.glob("*" + ext))
        files.extend(sorted(set(found)))
    return files, problems


def build_parser():
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="image_alt_checker",
        description=(
            "Check image alt text in local HTML files: every <img> "
            "must have an alt attribute, and the alt text must not "
            "be empty. Prints PASS or FAIL per file and exits 1 when "
            "any file fails, so it can fail a CI run."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="PATH",
        help="HTML file or directory to check. Directories are "
        "scanned for .html and .htm files.",
    )
    parser.add_argument(
        "--allow-empty-alt",
        action="store_true",
        help="Allow an empty alt attribute (alt=\"\"). For images "
        "that are decorative on purpose. A missing alt attribute "
        "still fails.",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not look inside subdirectories of a named directory.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="image_alt_checker " + VERSION,
    )
    return parser


def run(argv=None, stdout=None, stderr=None):
    """Run the checker. Returns the exit code (0, 1, or 2)."""
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    try:
        # argparse writes --version output and usage errors to the real
        # sys.stdout/sys.stderr, so point those at the caller's streams.
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    files, problems = collect_files(args.paths, recursive=not args.no_recursive)
    if problems:
        for problem in problems:
            print("error: %s" % problem, file=err)
        return 2
    if not files:
        print("error: no HTML files found", file=err)
        return 2
    passed = 0
    failed = 0
    for path in files:
        found = check_file(path, args.allow_empty_alt)
        if found:
            failed += 1
            print("FAIL %s: %s" % (path, "; ".join(found)), file=out)
        else:
            passed += 1
            print("PASS %s" % path, file=out)
    print(
        "%d file(s) checked, %d passed, %d failed"
        % (passed + failed, passed, failed),
        file=out,
    )
    return 1 if failed else 0


def main():
    """Entry point for the command line."""
    sys.exit(run())


if __name__ == "__main__":
    main()
