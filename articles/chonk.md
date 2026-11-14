---
title: Disk Viewers Show Sizes. I Wanted One That Says Who Put the Bytes There.
published: true
description: 'An 81G file on my Mac was a VM disk whose guest used 3.6G. No disk viewer told me that, and docker system prune would not have freed it. chonk groups every byte by owner and reclaims with that owner''s own command.'
tags:
  - showdev
  - go
  - macos
  - cli
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/chonk/cover.png?v=6318e3a0'
id: 5038048
date: '2026-11-14T21:50:32Z'
---

My Mac was out of space, and the biggest single file was `~/Library/Application Support/rancher-desktop/lima/0/diffdisk`: 81G. That is Rancher Desktop's VM disk. Inside the VM, Docker used 3.4G and the filesystem 3.6G. The other 77G was space the guest had already freed and never handed back to macOS.

`docker system prune` does not touch that. `fstrim` inside the guest does. No disk viewer I had would tell me either fact; they list directories and sizes. Cleaners delete a fixed list of caches, and a VM disk is not on it.

Same machine: a 54G `podman-machine-default-arm64.raw` that took 16G on disk because it is sparse. Tools that add up file lengths reported 54.

So I wrote chonk. It groups every byte by who put it there, says why it exists, and gets it back with that owner's own command.

- Source: <https://github.com/kanywst/chonk>
- Install: `brew install --cask kanywst/tap/chonk` or `go install github.com/kanywst/chonk/cmd/chonk@latest`

![chonk's terminal UI on a canned machine: owners grouped by kind, a Rancher Desktop VM with 77G trapped, and the fstrim confirmation](./assets/chonk/demo.gif?v=b7d4cdf5)

The recording runs on a canned machine (`CHONK_DEMO=1`), so none of it is a real disk.

## Walk first, attribute second

Before chonk I had a Caches tab in another tool, sweep. It knew eight caches: Go, npm, pnpm, yarn, uv, pip, Homebrew. The things actually eating my disk were a VM disk, a Podman machine, a Rust `target/`, a project `.cache` and the Nix store. A fixed list will always miss the big ones.

chonk walks everything first and attributes second. Rules claim subtrees (Rancher Desktop's `lima` dir, `~/.rustup`, `~/Library/Caches/go-build`, a git working tree and the `target/` or `node_modules/` inside it). Whatever no rule claims is still listed as "unclaimed", at the directory where its size concentrates, so nothing big hides behind an unknown name.

Sizes are allocated blocks (`st_blocks * 512`), not file lengths, and a hard-linked file counts once. That is what fixes the 54G-vs-16G Podman image, and it keeps the Nix store from being counted several times over.

## Asking why one path exists

`chonk why PATH` does not scan the disk. It asks the rules about each directory from the top down to PATH and measures only what the owner claims.

To get output without putting my own home in an article, I pointed `HOME` at a throwaway directory: a Rust project `tally` with 437M in `target/`, a 20G sparse Podman image with 512M written into it, and three rustup toolchains.

```text
$ chonk why ~/src/tally/target | sed "s#$HOME#~#g"
~/src/tally/target
  Cargo target/, 437M on disk
  build output of the project ~/src/tally

why:     Compiled Rust: every profile, every dependency, incremental caches.
regen:   Rebuilt by the next `cargo build`.
safety:  safe
written: 1m ago

biggest inside:
     437M  debug

reclaim:
  [safe] cargo clean
      cargo clean --manifest-path ~/src/tally/Cargo.toml --target-dir ~/src/tally/target
  [safe] Move to the Trash
      move to the Trash
```

The project around it is a different answer. chonk asks git what the tree holds that no remote has. `tally` has one commit that was never pushed:

```text
$ chonk why ~/src/tally
~/src/tally
  ~/src/tally, 437M on disk

why:     A git working tree with work that only this disk has.
regen:   Only here: 1 commit on main that no remote has.
safety:  danger
written: 0s ago

biggest inside:
     437M  target
```

A tree that is clean and fully pushed says so and names the remote it would come back from. Uncommitted work, a stash, or a commit no remote has (on a branch, a detached HEAD or a tag) makes it danger. A remote on the same disk does not count as a backup.

The sparse image:

```text
$ chonk why ~/.local/share/containers/podman/machine/applehv/podman-machine-default-arm64.raw
~/.local/share/containers/podman/machine/applehv/podman-machine-default-arm64.raw
  Podman machine, 512M on disk
  claimed at ~/.local/share/containers/podman/machine
...
inside:
  Disk image: 512M on disk (20.0G maximum), podman-machine-default-arm64.raw
  Sparse: 20.0G of file lengths take 512M on disk; tools that add up lengths overstate this
  Podman has no machine any more. What is left here is leftover files; moving them to the Trash is safe.
```

The last line is real too: `podman` is installed here, but with `HOME` swapped it has no machine registered, so chonk calls the image leftovers.

For toolchains it reads the pins in your projects (`.nvmrc`, `rust-toolchain.toml`, `.tool-versions` and a few more) plus each manager's default. My fake home has `stable` as rustup's default, `1.79.0` pinned by `tally`, and a nightly nobody asks for:

```text
$ chonk why --json ~/.rustup | jq '.parts[] | {path, command: .actions[0].command}' | sed "s#$HOME#~#g"
{
  "path": "~/.rustup/toolchains/nightly-2025-06-01-aarch64-apple-darwin",
  "command": "RUSTUP_HOME=~/.rustup rustup toolchain uninstall nightly-2025-06-01-aarch64-apple-darwin"
}
```

That one is marked careful, not safe. A shell script chonk never read could still want that nightly.

## Getting it back

Every action is the owner's own command: `cargo clean`, `go clean -cache`, `brew cleanup --prune=all`, `rdctl shell -- sudo fstrim -v /mnt/data` for Rancher Desktop, `podman machine rm`. Or a move to the Trash, which chonk tells you frees nothing until you empty it. chonk itself never deletes a file, and the commands come from rules compiled into the binary, never from anything it finds on disk.

Nothing runs without `y` on a confirmation that shows the exact command and its risk. `enter` does not confirm. If a process is running from what the action removes (the VM's host agent, a dev server in a project), the dialog says so.

After a run, chonk compares the volume's free space before and after, and appends what was expected and what actually came back to a ledger. When a VM prune frees blocks inside the guest, it runs the trim too, because otherwise the Mac sees nothing.

## Things no directory shows

The header compares what the walk counted with what `statfs` says the volume uses, so the gap (swap, logs, other users, `/Library`) is not mistaken for nothing. Time Machine local snapshots, which keep deleted files' blocks alive, are listed as their own item. A running app's code-sign clone in `/var/folders` shows up as the second copy of the bundle that it is.

`chonk schedule on` installs a launchd agent that runs `chonk snapshot` once a day at low I/O priority, so `chonk diff` always has a baseline to say what grew since last week.

## Speed

On macOS chonk reads directories with `getattrlistbulk(2)`: one call returns names and allocated sizes for a batch of entries. On a home with three million files that took a full scan from 38 seconds (ReadDir plus lstat) to about 30. The rest is APFS metadata I/O, and more workers only contend on it.

## Not yet

Purgeable space, which needs Foundation's volume capacity keys, and per-snapshot sizes, which APFS does not expose.

Source and issues: <https://github.com/kanywst/chonk>
