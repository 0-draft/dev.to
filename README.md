<!-- markdownlint-disable MD033 MD001 -->

<div align="center">

<img alt="dev.to" src="https://d2fltix0v2e0sb.cloudfront.net/dev-badge.svg" width="96">

# dev.to articles

Source for the articles auto-published under [`0-draft/dev.to`](https://github.com/0-draft/dev.to).

<p>
  <a href="https://github.com/0-draft/dev.to/actions/workflows/publish.yml"><img alt="publish workflow" src="https://img.shields.io/github/actions/workflow/status/0-draft/dev.to/publish.yml?branch=main&label=publish&style=for-the-badge&logo=github&logoColor=white&labelColor=0A0A0A&color=10B981"></a>
  <a href="https://github.com/0-draft/dev.to/actions/workflows/schedule.yml"><img alt="schedule workflow" src="https://img.shields.io/github/actions/workflow/status/0-draft/dev.to/schedule.yml?branch=main&label=schedule&style=for-the-badge&logo=githubactions&logoColor=white&labelColor=0A0A0A&color=10B981"></a>
  <a href="https://dev.to/kanywst"><img alt="dev.to profile" src="https://img.shields.io/badge/dev.to-kanywst-0A0A0A?style=for-the-badge&logo=devdotto&logoColor=white"></a>
</p>

</div>

---

Pushing to `main` triggers `.github/workflows/publish.yml`, which syncs changed `articles/*.md` to dev.to through `@sinedied/devto-cli`. Set `published: true` in the frontmatter when an article is ready, or leave `published: false` with a future `date:` (UTC) and let the hourly `schedule.yml` cron flip it once the scheduled time arrives.

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

A repo secret `DEVTO_API_KEY` is required; generate it from your dev.to account settings and add it under repo Settings → Secrets and variables → Actions.

</td>
</tr>
</table>

<div align="center">
  <sub>Built on <a href="https://github.com/sinedied/devto-cli"><code>@sinedied/devto-cli</code></a></sub>
</div>
