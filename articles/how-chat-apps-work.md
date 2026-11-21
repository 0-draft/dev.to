---
title: 'One Chat Message, Followed From Send to Read'
published: true
description: 'how-chat-apps-work follows a single message through a chat app one frame at a time: the always-on connection, the seq number, the lost ACK and the retry that is safe, the push that wakes a closed app, E2EE and group fan-out. English and Japanese.'
tags:
  - showdev
  - webdev
  - architecture
  - security
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/how-chat-apps-work/cover.png?v=e41713a7'
id: 5089043
date: '2026-11-21T15:35:06Z'
---

You tap send. Under a second later the message is on someone else's phone, and a little after that yours says Read. I wanted a page that shows everything that happens in between, frame by frame, so I built one.

- Source: <https://github.com/0-draft/how-chat-apps-work>
- Site: <https://0-draft.github.io/how-chat-apps-work/> (Japanese at `/ja/`)

![The "From send to read" sequence diagram at step 6: the messaging service pushes EVENT seq=1042 to B's phone](./assets/how-chat-apps-work/screenshot.png?v=d5e32ec2)

## The protocol is made up, the apps are not

The diagrams use one protocol for the whole site. It is a composite of what most chat apps do, with field names picked to be readable (`clientMsgId`, `seq`, `READ upTo=1042`) rather than to match any one product. Copying LINE's or WhatsApp's wire format would have meant explaining their quirks before the idea.

Claims about real apps are kept apart, in one file, `src/lib/apps.ts`. Each claim sits next to the primary source it came from: a vendor whitepaper, an engineering blog post, a spec. A weekly lychee job checks that those links still resolve.

## What a message goes through

The chapters follow the message, not a list of technologies.

- **From send to read**: the phone picks a `clientMsgId`, the server stamps a `seq`, and a read receipt is a position (`READ upTo=1042`), not a flag on every message.
- **The always-on connection**: DNS, TCP, TLS 1.3, auth, heartbeats, and reconnecting without every client hammering the server at once.
- **Why it never arrives twice**: covered below.
- **Delivered while the app is closed**: APNs and FCM, the Notification Service Extension, and syncing from a cursor.
- **A letter the server can't read**: ECDH, AES-GCM, and what the Double Ratchet adds.
- **Groups**: fan-out on read vs. fan-out on write, and "read by N" as a count of members whose position is past the message.
- **Photos and video**: the file goes to blob storage first, and the message carries a pointer and a key.

On a desktop, the diagram follows the text as you scroll. On a phone, you step through it with buttons. Every step has its own link (`#retry-6`), so you can send someone the exact moment you mean.

## The chapter I wanted most: the lost ACK

The send works and the server stores the message as 1042, but the ACK back to A never arrives. Maybe A went into a tunnel. A can't tell whether the server got the message, so it sends again.

If the retry got a new ID, B would see the message twice. So the retry reuses the original `clientMsgId`, and the server checks it before inserting:

```sql
SELECT seq FROM messages
 WHERE chat_id = 'c_8f2a'
   AND sender = 31337
   AND client_msg_id = 'a-7d1c9e';
```

It finds 1042 and returns the same ACK it sent the first time. The sender has to be part of the key, because phones pick `clientMsgId` and two phones can pick the same one.

The simulator chapter lets you cause this yourself. There are two phones and a server. You can take a phone offline, tick "Drop the next ACK", send, and watch the retry get deduplicated.

## Real apps

The last chapter compares LINE, WhatsApp, Signal, iMessage, Messenger, Telegram and Discord on transport, E2EE and groups, but only where the vendor has published something. Where nothing has been published, the cell shows a dash instead of a guess.

That file goes stale quickly. In its first maintenance pass, five days after launch, two lines were already out of date. Discord had made DAVE (its MLS-based E2EE) mandatory for every voice and video call except Stage channels in March 2026. Apple and Google had started a beta of E2EE RCS between iPhone and Android in May 2026. Both are fixed now. The RCS line says that neither announcement names the protocol, because I couldn't find a primary source that ties the beta to MLS.

If you know a vendor has said otherwise, open an issue with the link.

## How it's built

Astro renders every diagram to SVG at build time, so the page reads fine with JavaScript off. A small custom element, `<seq-player>`, adds the stepping. The simulator is a Svelte island on top of a pure reducer, which made the dedup and offline cases easy to unit test.

English and Japanese share the same step data. Each string is stored as `{ en, ja }`, and the tests fail if one language is missing or the two drift apart in structure. Playwright runs both languages on desktop, on a phone and in dark mode, with axe checking accessibility as it goes.

Code is MIT. The writing and diagrams are CC BY 4.0, so reuse them in your own docs or slides with attribution.
