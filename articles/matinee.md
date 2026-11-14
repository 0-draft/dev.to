---
title: I Already Had a VHS Tape for Every README GIF. matinee Turns It Into a Narrated Video.
published: true
description: 'My CLI repos each record their README GIF from a VHS .tape. matinee runs the same tape and renders a chaptered, narrated, captioned video in 16:9 and 9:16, with no timestamps written by hand.'
tags:
  - showdev
  - cli
  - terminal
  - video
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/matinee/cover.png?v=836278fc'
id: 5038073
---

Most of my CLI repos record their README GIF with [VHS](https://github.com/charmbracelet/vhs). The `.tape` is already in the repo, it already knows every keystroke, and it already has comments like `# 3. Search` above each step.

A GIF has no sound and no chapters, and it is unreadable on a phone. I wanted a real demo video, but not a second script that drifts from the tape the first time I change the demo. So matinee takes the tape as the only source.

- Source: <https://github.com/kanywst/matinee>
- Stack: VHS, ffmpeg, macOS `say` / piper / VOICEVOX, whisper.cpp, [Remotion](https://www.remotion.dev). All local, no API key.

![matinee's 16:9 cut of the y509 demo: a chapter chip at the top, the terminal in the middle, word-by-word captions at the bottom](./assets/matinee/demo.gif?v=4e5e9872)

That is the [y509](https://dev.to/kanywst/y509-a-terminal-user-interface-tui-tool-for-viewing-and-analyzing-x509-certificate-chains-5fn6) tape, unchanged. The chip in the corner, the timings and the captions all came out of the pipeline. The README has the version with sound.

It is a personal tool: projects are added by committing a `script.yaml` into the matinee repo itself, and the README says up front it may break without notice.

## Chapters come from the comments

This is the top of y509's tape:

```text
# Launch
Type "y509 testdata/demo/certs.pem"
Sleep 500ms
Enter
Sleep 2s

# 1. Navigate certificate list
Type "j"
...

# 2. Switch to details pane and browse tabs (last tab is Misc with the
# new lipgloss table-based chain view)
Right
```

`tape_timeline.py` reads it and prints the sections:

```text
$ uv run scripts/tape_timeline.py tests/fixtures/y509.tape
     0  Launch
  4675  Navigate certificate list
  6575  Switch to details pane and browse tabs
 12525  Search
 16050  Filter
 19800  Validate
 22950  Yank current cert as PEM
 25400  Export via huh form
 31550  Help
 34200  Quit
```

(Reformatted from its JSON output to fit.)

A numbered comment is always a section, even when it wraps to a second line. An unnumbered one counts only if it stands alone; a block of comment lines is prose, which is how the eight-line note about the hidden build step above `# Launch` stays out. Titles are trimmed at the first `" ("`, so the wrapped `# 2.` becomes "Switch to details pane and browse tabs". `Quit` starts in the last second of the recording and gets dropped as teardown, which is why the video says `01/09`, not `01/10`. A tape with no sections is an error, not an empty video:

```text
$ uv run scripts/tape_timeline.py tests/fixtures/no-sections.tape
error: no section comments found in tape
```

## The only thing I write

```yaml
source:
  repoDir: ~/y509
  tapeRel: demo.tape

narration:
  Launch: y509 opens any certificate chain in your terminal.
  Search: Search jumps straight to a certificate.

crop:
  Search: { x: 0.14, y: 0.24, w: 0.72, h: 0.46 }
```

Narration is keyed by chapter title, not by position, so reordering the tape cannot hand a line to the wrong shot. A chapter left out plays silent. `crop` applies only to the 9:16 cut: it zooms to the pane that chapter is about, so a two-pane TUI is still readable on a phone.

## Running it

`hello` is the example that works from a bare clone: a two-section tape that only echoes. I ran each step on a Mac.

```text
$ make record PROJECT=hello
==> recording hello (scale 2x, 24fps)
==> 169 frames
==> encoding
==> terminalDurationMs: 7041
==> chapter marks at frames [1, 70] -> .../public/projects/hello/marks.json

$ make narrate PROJECT=hello
  [1/2] Say hello
  [2/2] Say goodbye
==> wrote .../public/projects/hello/narration.wav (7041ms)
==> wrote projects/hello/project.json
    2 chapters (measured), 7041ms, 18 captions
```

`make render` then writes both cuts. Same frame, 16:9 and 9:16:

![The hello project at 16:9: chip "02/02 Say goodbye", the terminal, and the caption "Narration comes from this file, and the" with the current word highlighted](./assets/matinee/hello-16x9.png?v=82b344a9)

![The same frame at 9:16, with the terminal card centred and the caption wrapped to two lines](./assets/matinee/hello-9x16.png?v=24313b12)

I skipped `make captions` because it needs a whisper model I didn't download, so these frames use the transcription checked into the repo.

## Measured, not estimated

The first version estimated chapter starts by walking the tape: typing speed times characters, plus every `Sleep`, scaled to the clip length. That fixes the total but not one slow step in the middle. For `hello` the estimate puts "Say goodbye" at 2760ms. The recording says frame 70 at 24fps, which is 2875ms.

To get the real frame, `record.sh` inserts a VHS `Screenshot` before each chapter's first statement. VHS notes which frame that lands on and later asks ffmpeg to render it. A stand-in `ffmpeg` first on VHS's `PATH` logs the frame number instead of rendering anything, and passes every other call through. If `marks.json` is missing or doesn't match the tape, `build_project.py` warns and falls back to the estimate.

## Captions come from the audio

Captions are whisper.cpp word timings on the narration that was actually synthesized, so they follow the pauses the voice chose. The cost is mishearing: whisper heard "y509" as "Wi-5009" and "a cert" as "assert". The fix is per word, after transcription:

```yaml
captionFixes:
  Wi-5009: y509
  assert: a cert
```

`lang: ja` switches narration to VOICEVOX and expects the multilingual whisper model.

## Limits

The recording is not reproducible. A tape that builds before it records takes as long as the machine takes, and narration that fits a chapter on one machine can overrun it on a slower one. Remotion, which does the rendering, is not MIT: companies with more than three employees need a company licence.

Source: <https://github.com/kanywst/matinee>
