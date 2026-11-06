#!/usr/bin/env python3
"""Tests for image_alt_checker. Standard library unittest only."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
EXAMPLES = ROOT / "examples"

sys.path.insert(0, str(SRC))

from image_alt_checker import (  # noqa: E402
    Image,
    check_file,
    check_images,
    collect_files,
    extract_images,
    run,
)


def write(path, text):
    """Write text to a file, making parent folders as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestExtractImages(unittest.TestCase):
    def test_simple_img_with_alt(self):
        images = extract_images('<img src="a.jpg" alt="A photo">')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].line, 1)
        self.assertEqual(images[0].src, "a.jpg")
        self.assertEqual(images[0].alt, "A photo")

    def test_img_without_alt(self):
        images = extract_images('<img src="a.jpg">')
        self.assertEqual(len(images), 1)
        self.assertIsNone(images[0].alt)

    def test_img_empty_alt(self):
        images = extract_images('<img src="a.jpg" alt="">')
        self.assertEqual(images[0].alt, "")

    def test_img_whitespace_alt(self):
        images = extract_images('<img src="a.jpg" alt="   ">')
        self.assertEqual(images[0].alt, "   ")

    def test_line_numbers(self):
        text = (
            "<!doctype html>\n"
            "<html>\n"
            "<body>\n"
            '<img src="a.jpg" alt="A">\n'
            '<img src="b.jpg">\n'
            "</body>\n"
            "</html>\n"
        )
        images = extract_images(text)
        self.assertEqual([img.line for img in images], [4, 5])

    def test_uppercase_tag_and_attrs(self):
        images = extract_images('<IMG SRC="a.jpg" ALT="A photo">')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].src, "a.jpg")
        self.assertEqual(images[0].alt, "A photo")

    def test_single_quotes(self):
        images = extract_images("<img src='a.jpg' alt='A photo'>")
        self.assertEqual(images[0].src, "a.jpg")
        self.assertEqual(images[0].alt, "A photo")

    def test_unquoted_attrs(self):
        images = extract_images('<img src=a.jpg alt=Photo>')
        self.assertEqual(images[0].src, "a.jpg")
        self.assertEqual(images[0].alt, "Photo")

    def test_no_src(self):
        images = extract_images('<img alt="A photo">')
        self.assertEqual(images[0].src, "")
        self.assertEqual(images[0].alt, "A photo")

    def test_img_inside_comment_not_counted(self):
        text = '<!-- <img src="a.jpg"> -->\n<img src="b.jpg" alt="B">'
        images = extract_images(text)
        self.assertEqual([img.src for img in images], ["b.jpg"])

    def test_img_inside_script_not_counted(self):
        text = (
            '<script>var s = \'<img src="a.jpg">\';</script>\n'
            '<img src="b.jpg" alt="B">'
        )
        images = extract_images(text)
        self.assertEqual([img.src for img in images], ["b.jpg"])

    def test_img_inside_style_not_counted(self):
        text = (
            "<style>.x { background: url(a.jpg); }</style>\n"
            '<img src="b.jpg" alt="B">'
        )
        images = extract_images(text)
        self.assertEqual([img.src for img in images], ["b.jpg"])

    def test_img_inside_picture_counted(self):
        text = (
            "<picture>\n"
            '  <source srcset="a.webp" type="image/webp">\n'
            '  <img src="a.jpg" alt="A photo">\n'
            "</picture>\n"
        )
        images = extract_images(text)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].line, 3)

    def test_no_images(self):
        self.assertEqual(extract_images("<p>No images here.</p>"), [])

    def test_empty_document(self):
        self.assertEqual(extract_images(""), [])

    def test_self_closing_img(self):
        images = extract_images('<img src="a.jpg" alt="A" />')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].alt, "A")

    def test_multiline_tag_line_is_tag_start(self):
        text = (
            '<img\n'
            '  src="a.jpg"\n'
            '  alt="A photo">\n'
        )
        images = extract_images(text)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].line, 1)

    def test_alt_with_entity(self):
        images = extract_images('<img src="a.jpg" alt="Fish &amp; chips">')
        self.assertEqual(images[0].alt, "Fish & chips")


class TestCheckImages(unittest.TestCase):
    def test_all_good(self):
        images = [
            Image(1, "a.jpg", "A photo"),
            Image(2, "b.jpg", "B photo"),
        ]
        self.assertEqual(check_images(images), [])

    def test_no_images_passes(self):
        self.assertEqual(check_images([]), [])

    def test_missing_alt(self):
        problems = check_images([Image(5, "a.jpg", None)])
        self.assertEqual(
            problems,
            ['line 5: <img src="a.jpg"> has no alt attribute'],
        )

    def test_empty_alt(self):
        problems = check_images([Image(7, "a.jpg", "")])
        self.assertEqual(
            problems,
            ['line 7: <img src="a.jpg"> has an empty alt attribute'],
        )

    def test_whitespace_only_alt_counts_as_empty(self):
        problems = check_images([Image(3, "a.jpg", "   ")])
        self.assertEqual(len(problems), 1)
        self.assertIn("empty alt", problems[0])

    def test_missing_src_still_reports(self):
        problems = check_images([Image(2, "", None)])
        self.assertEqual(
            problems, ["line 2: <img> has no alt attribute"]
        )

    def test_allow_empty_alt(self):
        images = [Image(7, "a.jpg", "")]
        self.assertEqual(check_images(images, allow_empty_alt=True), [])

    def test_allow_empty_alt_still_fails_missing(self):
        images = [Image(7, "a.jpg", None)]
        problems = check_images(images, allow_empty_alt=True)
        self.assertEqual(len(problems), 1)
        self.assertIn("no alt attribute", problems[0])

    def test_multiple_problems_in_order(self):
        images = [
            Image(2, "a.jpg", None),
            Image(4, "b.jpg", "B photo"),
            Image(6, "c.jpg", ""),
        ]
        problems = check_images(images)
        self.assertEqual(len(problems), 2)
        self.assertIn("line 2", problems[0])
        self.assertIn("line 6", problems[1])


class TestCheckFile(unittest.TestCase):
    def test_good_file(self):
        self.assertEqual(check_file(EXAMPLES / "good.html"), [])

    def test_missing_alt_file(self):
        problems = check_file(EXAMPLES / "missing-alt.html")
        self.assertEqual(len(problems), 1)
        self.assertIn("line 8", problems[0])
        self.assertIn("photo.jpg", problems[0])

    def test_empty_alt_file(self):
        problems = check_file(EXAMPLES / "empty-alt.html")
        self.assertEqual(len(problems), 1)
        self.assertIn("line 8", problems[0])
        self.assertIn("logo.png", problems[0])

    def test_no_images_file_passes(self):
        self.assertEqual(check_file(EXAMPLES / "no-images.html"), [])

    def test_unknown_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.txt"
            write(path, '<img src="a.jpg">')
            problems = check_file(path)
            self.assertEqual(len(problems), 1)
            self.assertIn("unknown file type", problems[0])

    def test_missing_file(self):
        problems = check_file(Path("/nonexistent/page.html"))
        self.assertEqual(len(problems), 1)
        self.assertIn("cannot read file", problems[0])

    def test_non_utf8_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.html"
            path.write_bytes(b'<img src="a.jpg" alt="\xff">')
            problems = check_file(path)
            self.assertEqual(len(problems), 1)
            self.assertIn("not valid UTF-8", problems[0])

    def test_bom_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.html"
            path.write_bytes(
                b'\xef\xbb\xbf<img src="a.jpg" alt="A photo">'
            )
            self.assertEqual(check_file(path), [])


class TestCollectFiles(unittest.TestCase):
    def test_single_file(self):
        files, problems = collect_files([str(EXAMPLES / "good.html")])
        self.assertEqual(problems, [])
        self.assertEqual(files, [EXAMPLES / "good.html"])

    def test_directory_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.html", '<img src="a.jpg" alt="A">')
            write(root / "sub" / "b.html", '<img src="b.jpg" alt="B">')
            write(root / "sub" / "c.md", "# Title")
            write(root / "d.txt", "plain text")
            files, problems = collect_files([str(root)])
            self.assertEqual(problems, [])
            self.assertEqual(
                files,
                [root / "a.html", root / "sub" / "b.html"],
            )

    def test_directory_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.html", '<img src="a.jpg" alt="A">')
            write(root / "sub" / "b.html", '<img src="b.jpg" alt="B">')
            files, problems = collect_files([str(root)], recursive=False)
            self.assertEqual(problems, [])
            self.assertEqual(files, [root / "a.html"])

    def test_htm_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.htm", '<img src="a.jpg" alt="A">')
            files, problems = collect_files([str(root)])
            self.assertEqual(problems, [])
            self.assertEqual(files, [root / "a.htm"])

    def test_missing_path(self):
        files, problems = collect_files(["/nonexistent/page.html"])
        self.assertEqual(files, [])
        self.assertEqual(len(problems), 1)
        self.assertIn("no such file", problems[0])

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            files, problems = collect_files([tmp])
            self.assertEqual(problems, [])
            self.assertEqual(files, [])


class TestCli(unittest.TestCase):
    def run_cli(self, argv):
        out = io.StringIO()
        err = io.StringIO()
        code = run(argv, stdout=out, stderr=err)
        return code, out.getvalue(), err.getvalue()

    def test_good_files_exit_0(self):
        code, out, err = self.run_cli(
            [str(EXAMPLES / "good.html"), str(EXAMPLES / "no-images.html")]
        )
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("PASS %s" % (EXAMPLES / "good.html"), out)
        self.assertIn("2 file(s) checked, 2 passed, 0 failed", out)

    def test_bad_files_exit_1(self):
        code, out, err = self.run_cli(
            [
                str(EXAMPLES / "good.html"),
                str(EXAMPLES / "missing-alt.html"),
                str(EXAMPLES / "empty-alt.html"),
                str(EXAMPLES / "no-images.html"),
            ]
        )
        self.assertEqual(code, 1)
        self.assertEqual(err, "")
        self.assertIn("4 file(s) checked, 2 passed, 2 failed", out)
        self.assertIn("missing-alt.html", out)
        self.assertIn("empty-alt.html", out)

    def test_missing_alt_alone(self):
        code, out, err = self.run_cli([str(EXAMPLES / "missing-alt.html")])
        self.assertEqual(code, 1)
        self.assertIn(
            'line 8: <img src="photo.jpg"> has no alt attribute', out
        )

    def test_empty_alt_alone(self):
        code, out, err = self.run_cli([str(EXAMPLES / "empty-alt.html")])
        self.assertEqual(code, 1)
        self.assertIn(
            'line 8: <img src="logo.png"> has an empty alt attribute',
            out,
        )

    def test_allow_empty_alt_flag(self):
        code, out, err = self.run_cli(
            ["--allow-empty-alt", str(EXAMPLES / "empty-alt.html")]
        )
        self.assertEqual(code, 0)
        self.assertIn("PASS", out)

    def test_missing_path_exit_2(self):
        code, out, err = self.run_cli(["/nonexistent/page.html"])
        self.assertEqual(code, 2)
        self.assertIn("error: no such file", err)

    def test_no_args_exit_2(self):
        code, out, err = self.run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_bad_flag_exit_2(self):
        code, out, err = self.run_cli(["--no-such-flag", "x.html"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, err = self.run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("image_alt_checker 1.0.0", out)

    def test_directory_scan(self):
        code, out, err = self.run_cli([str(EXAMPLES)])
        self.assertEqual(code, 1)
        self.assertIn("4 file(s) checked, 2 passed, 2 failed", out)

    def test_files_unchanged_after_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.html"
            text = '<img src="a.jpg">\n'
            write(path, text)
            code, out, err = self.run_cli([str(path)])
            self.assertEqual(code, 1)
            self.assertEqual(path.read_text(), text)


class TestExamples(unittest.TestCase):
    def test_sample_output_matches_fresh_run(self):
        # The saved output uses relative paths, so run from the repo
        # root, whatever directory the tests were started from.
        old_cwd = os.getcwd()
        try:
            os.chdir(ROOT)
            out = io.StringIO()
            err = io.StringIO()
            code = run(
                [
                    "examples/good.html",
                    "examples/missing-alt.html",
                    "examples/empty-alt.html",
                    "examples/no-images.html",
                ],
                stdout=out,
                stderr=err,
            )
        finally:
            os.chdir(old_cwd)
        self.assertEqual(code, 1)
        saved = (EXAMPLES / "sample-output.txt").read_text()
        self.assertEqual(out.getvalue(), saved)

    def test_run_example_script(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("2 passed, 2 failed", result.stdout)

    def test_readme_quoted_outputs(self):
        readme = (ROOT / "README.md").read_text()
        saved = (EXAMPLES / "sample-output.txt").read_text()
        self.assertIn(saved.strip(), readme)


class TestRepoHygiene(unittest.TestCase):
    def test_stdlib_only_imports(self):
        allowed = {
            "argparse", "contextlib", "os", "sys", "html",
            "pathlib", "io", "subprocess", "tempfile", "unittest",
        }
        for path in list(SRC.rglob("*.py")) + list(
            (ROOT / "tests").rglob("*.py")
        ):
            for line in path.read_text().splitlines():
                if line.startswith("import "):
                    for name in line[7:].split(","):
                        top = name.strip().split(".")[0].split(" ")[0]
                        self.assertIn(
                            top,
                            allowed | {"image_alt_checker"},
                            "%s in %s" % (top, path),
                        )
                elif line.startswith("from "):
                    top = line.split()[1].split(".")[0]
                    self.assertIn(
                        top,
                        allowed | {"image_alt_checker"},
                        "%s in %s" % (top, path),
                    )

    def test_no_placeholders_or_secrets(self):
        banned = (
            "TODO",
            "FIXME",
            "lorem",
            "coming soon",
            "API_KEY",
            "api_key",
            "password =",
        )
        # The tests directory is excluded from this scan: the test file
        # itself names the banned words in its own check list, and it
        # uses temp paths. The shipped content is what must be clean.
        # .git is excluded too: GitHub's checkout ships sample hooks
        # under .git/hooks/ that contain "TODO" (Day 21 CI failure).
        shipped = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and "__pycache__" not in str(path)
            and ".git" not in path.parts
            and "tests" not in path.parts
        ]
        for path in shipped:
            text = path.read_text(errors="ignore")
            for word in banned:
                self.assertNotIn(word, text, "%s in %s" % (word, path))

    def test_no_absolute_paths(self):
        # Same exclusion as the placeholder scan: the test file itself
        # names temp paths in its own check list.
        shipped = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and "__pycache__" not in str(path)
            and ".git" not in path.parts
            and "tests" not in path.parts
        ]
        for path in shipped:
            text = path.read_text(errors="ignore")
            self.assertNotIn(
                "/home/hatch", text, "absolute path in %s" % path
            )
            self.assertNotIn("/tmp/", text, "absolute path in %s" % path)

    def test_gitignore_lists_env_first(self):
        lines = (ROOT / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_the_tests(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("python3 tests/test_image_alt_checker.py", ci)
        self.assertIn('python-version: "3.12"', ci)

    def test_readme_contains_sample_output(self):
        readme = (ROOT / "README.md").read_text()
        saved = (EXAMPLES / "sample-output.txt").read_text()
        self.assertIn(saved.strip(), readme)


if __name__ == "__main__":
    unittest.main()
