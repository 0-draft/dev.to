# dev.to articles

Source for the articles published under [github.com/0-draft/dev.to](https://github.com/0-draft/dev.to). Pushing to `main` triggers `.github/workflows/publish.yml`, which syncs changed `articles/*.md` files to dev.to via `@sinedied/devto-cli`.

To start a new article, copy the template:

```bash
cp templates/article-template.md articles/<slug>.md
```

The slug becomes part of the dev.to URL (with a random suffix dev.to appends on first publish). Local-only drafts and Japanese versions live under `articles/DRAFT/` and `articles/JA/`, both gitignored, so anything in those directories never reaches dev.to.

Set `published: true` in the frontmatter when an article is ready. For time-released posts, leave `published: false` and add a future `date:` (UTC). The hourly `schedule.yml` cron runs `scripts/publish_scheduler.py`, which flips matching articles to `published: true` once the date has passed and pushes the commit, which in turn triggers the publish workflow.

Images and hands-on assets go under `articles/assets/<slug>/`. The publish step runs `dev push -r ${{ github.repository }}`, so relative asset paths in the source are rewritten to `raw.githubusercontent.com` URLs before being sent to dev.to. Cover images at the dev.to canonical size (1000x420) can be generated with `scripts/gen_cover_image.py`.

After publishing, `devto-cli` writes the dev.to `id` and `date` back into the frontmatter, and the bot commits the change as `chore: update article metadata from dev.to [skip ci]`. Pull before the next edit so your local copy doesn't diverge.

A repo secret `DEVTO_API_KEY` is required; generate it from your dev.to account settings.
