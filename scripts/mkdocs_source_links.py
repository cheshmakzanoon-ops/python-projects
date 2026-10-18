"""Keep checkout-relative source links usable in the generated documentation site."""

import re
from pathlib import Path
from urllib.parse import quote, urlsplit


def on_page_markdown(markdown, page, config, files):
    docs = Path(config["docs_dir"]).resolve()
    root = docs.parent
    source = Path(page.file.abs_src_path).parent

    def replace(match):
        target = match.group(1)
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match.group(0)
        destination = (source / parsed.path).resolve()
        if not destination.is_relative_to(root) or destination.is_relative_to(docs):
            return match.group(0)
        if not destination.exists():
            return match.group(0)  # The separate local-link validator reports this as an error.
        suffix = ("?" + parsed.query if parsed.query else "") + (
            "#" + parsed.fragment if parsed.fragment else ""
        )
        url = config["repo_url"].rstrip("/") + "/blob/main/"
        return "](" + url + quote(destination.relative_to(root).as_posix()) + suffix + ")"

    return re.sub(r"\]\(([^\s)]+)\)", replace, markdown)
