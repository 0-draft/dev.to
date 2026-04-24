# Dev.to Articles Management

This repository is set up to manage and automatically publish articles to [dev.to](https://dev.to).

## Directory Structure

- `articles/`: Place your markdown article files here.
- `articles/assets/`: Store images and static assets here.
- `templates/`: Contains `article-template.md` to start new posts.
- `.github/workflows/`: Contains the automation script to publish to dev.to.

## How to use

The source code for this setup is hosted here: [kanywst/dev.to.kanywst](https://github.com/kanywst/dev.to.kanywst)

1. **Create a new article**:
   Copy `templates/article-template.md` to `articles/my-new-post.md`.

   ```bash
   cp templates/article-template.md articles/my-new-topic.md
   ```

2. **Write your content**:
   Edit the file using standard Markdown.
   - Keep `published: false` while drafting.
   - Set `published: true` when ready to publish.

3. **Publishing**:
   - Get your API Key from Dev.to (Settings > Extensions).
   - Add it to this GitHub repository's Secrets as `DEVTO_API_KEY`.
   - Push your changes to the `main` branch.
   - The GitHub Action will automatically publish (or update) the article.
   - **Note**: The Action will modify your local file to add an `id` and `date`. Pull these changes back to your local machine.

## Images

You can place images in `articles/assets/`. Note that for Dev.to to see them, they usually need to be hosted publicly (like on this repo's `raw.githubusercontent.com` URL) or uploaded to an external host.
