# image-alt-checker-cli

Check every image has alt text, fail CI on missing or empty alt.

[![CI](https://github.com/haiderstudio/image-alt-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/image-alt-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`image_alt_checker` reads local HTML files and checks one rule
per image:

- **Every `<img>` must have an `alt` attribute, and the alt text
  must not be empty.** An image with no `alt` attribute fails,
  and one with `alt=""` (or only spaces) fails too.

- It prints `PASS` or `FAIL` per file, with the exact line of each
  problem and the image's `src`, and a summary line. It exits 1
  when any file fails, so it can fail a CI run.
- It checks one file, several files, or a whole directory
  (directories are scanned for `.html` and `.htm` files,
  including subdirectories, unless you pass `--no-recursive`).
- `--allow-empty-alt` allows an empty `alt` attribute
  (`alt=""`), for images that are decorative on purpose. A
  missing `alt` attribute still fails.
- It is report-only and runs fully offline: it never rewrites a
  file, sends nothing anywhere, and needs no API key.
- Images are found with the standard-library `html.parser`, so an
  `<img>` inside a comment, a `<script>` block, or a `<style>`
  block is not counted. An `<img>` inside a `<picture>` element
  is counted.

## What it does NOT do

- It does not judge whether the alt text is good. `alt="image"`
  passes; only a missing or empty alt fails. Writing good alt
  text is the author's job.
- It does not make an exception for decorative images on its own.
  An empty `alt` is reported unless you pass
  `--allow-empty-alt`.
- It does not check images in Markdown files (`![alt](src)`),
  `<input type="image">`, CSS background images, or images on a
  live site. Only `<img>` tags in local HTML files.
- It does not check links, headings, or anything else about the
  page. Those are other tools' jobs.
- It does not fix a file. A missing alt is reported, not repaired.
- It does not fetch a live site. Only files on your own machine.

## Who it is for

Anyone who keeps HTML files that need every image described
before a build: a docs site where a missing alt breaks
accessibility, a blog where every post image needs alt text, or
a team adding a CI step that fails the build when a page ships
with an image that has no alt. If the files are right, you get
a quiet pass; if one is wrong, the report says exactly which
file, which line, and which image.

## How this differs from similar tools

Alt text already exists as one check inside bigger tools, but no
small tool owns it on its own for local files. The quoted GitHub
search for the exact name, `"image-alt-checker"`, returns 4
results. The top one, ridetored/image-alt-checker (Python, 1
star), checks images on a webpage — live URLs, not local files.
The others are a WordPress ALT scanner (PHP, 0 stars), an HTML
alt tag checker (0 stars), and a vanilla-JS SEO checker
(1 star). The unquoted search `alt text checker cli` returns
4 results, all 0 stars, and all of them check live sites or
whole sites: a social-card metadata checker (JavaScript), a
full WCAG checker with AI judgement (TypeScript), a
pre-deployment website checker (TypeScript), and a site health
checker (Python) that audits any website for broken links,
slow pages, missing alt text, and redirect chains. The
`seo-meta-audit-skill` (Day 9 in this same series) notes
image-alt gaps on one page as part of a wider single-page SEO
audit; this is the standalone, multi-file, CI version of that
one check.

This tool does a narrower job: a Python standard-library-only
CLI that checks one thing — every `<img>` has alt text — on
one file or a whole folder of local HTML, reports the exact
line per failure, and exits 1 for CI. No install beyond Python,
no browser, no Node, no network, no fixing.

## Install

Python standard library only — no packages to download. Clone the
repo and run it in place:

```sh
git clone https://github.com/haiderstudio/image-alt-checker-cli.git
cd image-alt-checker-cli
```

Python 3.10 or newer.

## Usage

Check the example files:

```sh
python3 src/image_alt_checker.py examples/good.html examples/missing-alt.html examples/empty-alt.html examples/no-images.html
```

Real output:

```text
PASS examples/good.html
FAIL examples/missing-alt.html: line 8: <img src="photo.jpg"> has no alt attribute
FAIL examples/empty-alt.html: line 8: <img src="logo.png"> has an empty alt attribute
PASS examples/no-images.html
4 file(s) checked, 2 passed, 2 failed
```

The command exits 1, because two files fail. The same output is
saved in `examples/sample-output.txt`.

Check the good files alone:

```sh
python3 src/image_alt_checker.py examples/good.html examples/no-images.html
```

Real output:

```text
PASS examples/good.html
PASS examples/no-images.html
2 file(s) checked, 2 passed, 0 failed
```

The command exits 0.

Check a whole folder:

```sh
python3 src/image_alt_checker.py docs/
```

Directories are scanned for `.html` and `.htm` files,
including subdirectories. Add `--no-recursive` to stay in the
top folder only.

## Examples

### 1. An image with no alt attribute fails CI

`examples/missing-alt.html` has an image with no `alt` at all:

```sh
python3 src/image_alt_checker.py examples/missing-alt.html
```

```text
FAIL examples/missing-alt.html: line 8: <img src="photo.jpg"> has no alt attribute
1 file(s) checked, 0 passed, 1 failed
```

The exit code is 1. Put the same command in CI and the build
fails until the alt text is added. With the attribute added the
same command prints `PASS examples/missing-alt.html` and exits 0.

### 2. An empty alt attribute fails too

`examples/empty-alt.html` has an image with `alt=""`:

```sh
python3 src/image_alt_checker.py examples/empty-alt.html
```

```text
FAIL examples/empty-alt.html: line 8: <img src="logo.png"> has an empty alt attribute
1 file(s) checked, 0 passed, 1 failed
```

If the image is decorative on purpose, pass
`--allow-empty-alt` and the same file passes:

```sh
python3 src/image_alt_checker.py --allow-empty-alt examples/empty-alt.html
```

```text
PASS examples/empty-alt.html
1 file(s) checked, 1 passed, 0 failed
```

A missing `alt` attribute still fails with that flag — only
an empty one is allowed.

### 3. A page with no images passes

`examples/no-images.html` has no `<img>` tags at all:

```sh
python3 src/image_alt_checker.py examples/no-images.html
```

```text
PASS examples/no-images.html
1 file(s) checked, 1 passed, 0 failed
```

A file with nothing to check is a pass, not an error.

## How it is tested

```sh
python3 tests/test_image_alt_checker.py
```

61 tests, standard library `unittest` only. They cover image
extraction (line numbers, uppercase tags, single and unquoted
attributes, missing `src`, comments, script and style blocks
ignored, `<picture>` counted, entities), the alt rule (missing,
empty, whitespace-only, `--allow-empty-alt`), file checks (good
and bad files, unknown extension, missing file, non-UTF-8, BOM),
directory collection (recursive, `--no-recursive`, `.htm`),
the command line (exit codes 0, 1 and 2, `--version`, bad
flags, files unchanged after a run), the bundled examples, and
the repo hygiene checks (standard-library imports only, no
placeholder text, no secrets, no absolute paths).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Small, focused
improvements are welcome. Run the tests before opening a pull
request.

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea — a
small checker for one image-alt rule — follows the same
pattern as the other single-job tools in this series; no code was
copied from any other project.
