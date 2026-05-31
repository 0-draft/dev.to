# TIL

Snippet-sized notes that aren't worth a full article. Files under `articles/TIL/**` are intentionally not published to dev.to: the workflow globs `articles/*.md` non-recursively (see `.github/workflows/publish.yml` and `scripts/publish_scheduler.py`).

## Workflow

1. Open an issue with `status/idea` when something catches my attention.
2. While digging in, flip the label to `status/researching`.
3. Once it's worth keeping, write a markdown file under the matching category here and label the issue `status/seed`.
4. If it grows into a full article, move the content to `articles/<slug>.md` and flip the issue to `status/article-wip`. Close on merge.

## File convention

- Filename: `YYYY-MM-DD-kebab-slug.md`.
- No YAML frontmatter. dev.to metadata belongs only on published articles.
- End the body with a `source:` line (URL, book, command output) and an optional `related:` line referencing issues or other TIL files.

## Example

```markdown
# STS AssumeRole default TTL is one hour

Omitting `DurationSeconds` on `sts:AssumeRole` gives a 3600s session.
The upper bound is the role's `MaxSessionDuration`, but the default
stays at 1h until you ask for more.

source: aws cli `help assume-role`, verified locally
related: #42
```

## Categories

- [aws/](./aws/)
- [supply-chain/](./supply-chain/): sigstore, slsa, sbom, vex, fulcio, guac, kyverno, tuf, athenz
- [identity/](./identity/): oauth, oidc, spiffe, spire, dexidp, authzen, zanzibar
- [cloud-native/](./cloud-native/): kubernetes, cilium, docker, kubelet, networking
- [runtime/](./runtime/): go, rust, linux, kernel
- [ai-agent/](./ai-agent/): mcp, agents, llm internals
- [web-security/](./web-security/): web hacking, tor, anonymity
- [meta/](./meta/): mental models, learning techniques
