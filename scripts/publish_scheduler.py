import argparse
import os
import glob
import re
import datetime
import yaml
from dateutil import parser
from datetime import timezone

# Configuration
ARTICLES_DIR = "articles"


def main(dry_run=False):
    # Use UTC for consistency with typical CI environments and frontmatter dates
    now = datetime.datetime.now(timezone.utc)
    mode = " (dry run, no files will be modified)" if dry_run else ""
    print(f"[-] Checking for scheduled articles at {now.isoformat()}...{mode}")

    # Find all markdown files in the articles directory
    search_pattern = os.path.join(ARTICLES_DIR, "*.md")
    files = glob.glob(search_pattern)

    if not files:
        print(f"[!] No articles found in {search_pattern}")
        return

    updated_count = 0

    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"[!] Error reading {filepath}: {e}")
            continue

        # Extract Frontmatter (between first two '---')
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            # Skip files without frontmatter
            continue

        fm_text = match.group(1)

        try:
            # Parse YAML safely
            fm_data = yaml.safe_load(fm_text)
        except yaml.YAMLError as e:
            print(f"[!] Invalid YAML in {filepath}: {e}")
            continue

        if not isinstance(fm_data, dict):
            continue

        # Check 'published' status
        # We only care if 'published' is explicitly False
        if fm_data.get("published") is not False:
            continue

        # Check 'date'
        pub_date_raw = fm_data.get("date")
        if not pub_date_raw:
            continue

        pub_date = None
        try:
            # PyYAML might auto-convert to datetime or date object
            if isinstance(pub_date_raw, datetime.datetime):
                pub_date = pub_date_raw
            elif isinstance(pub_date_raw, datetime.date):
                pub_date = datetime.datetime.combine(pub_date_raw, datetime.time.min)
            else:
                # Fallback to string parsing
                pub_date = parser.parse(str(pub_date_raw))

            # Ensure timezone awareness (assume UTC if missing)
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
            else:
                # Convert to UTC for comparison
                pub_date = pub_date.astimezone(timezone.utc)

        except Exception as e:
            print(f"[!] Date parsing failed for {filepath} ({pub_date_raw}): {e}")
            continue

        # Compare dates
        if pub_date <= now:
            print(f"[+] Publishing: {filepath} (Scheduled: {pub_date.isoformat()})")

            if dry_run:
                updated_count += 1
                continue

            # Update the file content
            # We use regex replacement on the Frontmatter text to preserve comments/style
            new_fm_text = re.sub(
                r"^published:\s*false",
                "published: true",
                fm_text,
                flags=re.MULTILINE | re.IGNORECASE,
            )

            # Reconstruct content
            # Only replace the first occurrence of the frontmatter block
            new_content = content.replace(
                f"---\n{fm_text}\n---", f"---\n{new_fm_text}\n---", 1
            )

            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                updated_count += 1
            except Exception as e:
                print(f"[!] Failed to write {filepath}: {e}")

    if updated_count == 0:
        print("[-] No articles need publishing.")
    elif dry_run:
        print(f"[-] {updated_count} article(s) would be published. Nothing was written.")
    else:
        print(f"[-] Successfully published {updated_count} article(s).")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(
        description="Flip articles whose scheduled UTC date has passed to published: true."
    )
    cli.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be published without modifying any file",
    )
    main(dry_run=cli.parse_args().dry_run)
