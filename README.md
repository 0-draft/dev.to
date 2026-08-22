<!-- markdownlint-disable MD033 MD001 -->

<div align="center">

<img alt="dev.to" src="https://d2fltix0v2e0sb.cloudfront.net/dev-badge.svg" width="96">

# dev.to articles

Source for the articles auto-published under [`0-draft/dev.to`](https://github.com/0-draft/dev.to).

<p>
  <a href="https://github.com/0-draft/dev.to/actions/workflows/publish.yml"><img alt="publish workflow" src="https://img.shields.io/github/actions/workflow/status/0-draft/dev.to/publish.yml?branch=main&label=publish&style=for-the-badge&logo=github&logoColor=white&labelColor=0A0A0A&color=10B981"></a>
  <a href="https://github.com/0-draft/dev.to/actions/workflows/schedule.yml"><img alt="schedule workflow" src="https://img.shields.io/github/actions/workflow/status/0-draft/dev.to/schedule.yml?branch=main&label=schedule&style=for-the-badge&logo=githubactions&logoColor=white&labelColor=0A0A0A&color=10B981"></a>
  <a href="https://github.com/0-draft/dev.to/actions/workflows/validate.yml"><img alt="validate workflow" src="https://img.shields.io/github/actions/workflow/status/0-draft/dev.to/validate.yml?branch=main&label=validate&style=for-the-badge&logo=checkmarx&logoColor=white&labelColor=0A0A0A&color=10B981"></a>
  <a href="https://dev.to/kanywst"><img alt="dev.to profile" src="https://img.shields.io/badge/dev.to-kanywst-0A0A0A?style=for-the-badge&logo=devdotto&logoColor=white"></a>
</p>

<!-- stats:start -->

**106** articles (0 unpublished) · **106** live on dev.to · **152** reactions · **27** comments

Most reacted: [RFC 8693 Deep Dive: Token Exchange](https://dev.to/kanywst/rfc-8693-deep-dive-token-exchange-310i) (11 reactions)

<!-- stats:end -->

**[Browse the full article index](./INDEX.md)**

</div>

---

Pushing to `main` triggers `.github/workflows/publish.yml`, which validates the changed `articles/*.md` and syncs them to dev.to in a single `@sinedied/devto-cli` batch. Set `published: true` in the frontmatter when an article is ready, or leave `published: false` with a future `date:` (UTC) and let the hourly `schedule.yml` cron flip it once the scheduled time arrives.

<table>
<tr>
<td width="50%" valign="top">

### Writing

```bash
cp templates/article-template.md articles/<slug>.md
```

The slug becomes part of the dev.to URL (dev.to appends a random suffix on first publish). Local-only drafts and Japanese versions live under `articles/DRAFT/` and `articles/JA/`, both gitignored, so nothing in those directories ever reaches dev.to.

</td>
<td width="50%" valign="top">

### Assets

Images and hands-on resources go under `articles/assets/<slug>/`. The publish step runs `dev push -r ${{ github.repository }}`, which rewrites relative asset paths to `raw.githubusercontent.com` URLs before sending to dev.to. Cover images at the canonical size (1000x420) can be generated with `scripts/gen_cover_image.py`.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### Frontmatter writeback

After publishing, `devto-cli` writes the dev.to `id` and `date` back into the frontmatter, and the bot commits the change as `chore: update article metadata from dev.to [skip ci]`. Pull before the next edit so the local copy doesn't diverge.

</td>
<td width="50%" valign="top">

### API key

A repo secret `DEVTO_API_KEY` is required; generate it from your dev.to account settings and add it under repo Settings → Secrets and variables → Actions. It is passed to the CLI as `DEVTO_TOKEN` in the environment, never as a command-line flag.

</td>
</tr>
</table>

## Checks

`validate.yml` gates every push and pull request that touches an article. It runs three checks against the changed files only, so the pre-linter backlog in older articles never blocks new work:

| Check | Script | Blocks on |
| --- | --- | --- |
| Frontmatter and assets | `scripts/validate_articles.py` | more than 4 tags, non-lowercase tags, a relative or missing `cover_image`, a missing image, an SVG reference, an `<img>` with a relative `src`, a duplicate dev.to id |
| markdownlint | `scripts/lint_ratchet.py` | a change that *adds* markdownlint errors relative to the base revision |
| Links | `scripts/check_links.py` | a dead `dev.to/kanywst/...` cross-link or a dead asset URL in this repo |

`audit.yml` runs weekly and reports rather than blocks: full-corpus validation, third-party link rot, a `dev push --dry-run` drift check against dev.to, and a refresh of `INDEX.md` and the stats block above.

Everything is runnable locally:

```bash
make setup      # .venv + pinned dependencies
make check      # validate + lint + links, whole repo
make lint-changed validate-changed   # exactly what CI gates on
make links-external                  # slow: reports third-party link rot
make index                           # regenerate INDEX.md and README stats
make diagrams                        # re-render every D2 source to PNG
make schedule-dry                    # what the scheduler would publish, writes nothing
```

## License

Tooling (`scripts/`, `.github/`, `Makefile`, `templates/`) is [MIT](./LICENSE). Article content under `articles/`, including diagrams and images, is [CC BY 4.0](./articles/LICENSE).

<div align="center">
  <sub>Built on <a href="https://github.com/sinedied/devto-cli"><code>@sinedied/devto-cli</code></a></sub>
</div>
