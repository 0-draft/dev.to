---
title: 'GitHub Profile: A "Guest Book" Anyone Can Sign'
published: true
description: 'I built a fully automated, interactive guest book using Issue Forms and GitHub Actions, where visitors can leave a message in just 10 seconds.'
tags:
  - showdev
  - github
  - python
  - automation
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/guestbook-github-profile/cover.png'
series: ShowDev
id: 3389902
date: '2026-03-23T15:07:01Z'
---

> **Update (2026-11-08):** the guest book moved out of my profile README into [0-draft/guestbook](https://github.com/0-draft/guestbook) on 2026-10-02 and is now retired: nobody but me ever signed it. The repository is frozen and will be archived, so new entries no longer do anything; everything below still describes how it worked.

How do you use your GitHub Profile README?

There are so many approaches out there—listing your skill set, showcasing GitHub Stats badges, or dropping in a snake animation that eats your contribution graph.

But I wanted something **more interactive to engage with people visiting my profile.**

So, I implemented a **"Guest Book"** where anyone can leave a message.
By hacking the GitHub Issue feature, I completely automated the entire flow: from form submission, to updating the profile README, and automatically closing the issue.

![Github Profile](./assets/guestbook-github-profile/github-profile.png)

## How Does It Work?

Here is all a visitor has to do:

1. Click the "Sign the Guest Book" button on the profile.
2. A streamlined Issue form opens.
3. Write a quick message and click "Submit new issue".

A few seconds later, a bot automatically adds the new message to the table on my profile, comments "Thank you!" on the issue, and casually closes it.

## Conclusion

This setup is incredibly simple, but it perfectly captures the pure "joy of automation" in programming.
Instead of just maintaining a static portfolio page, adding a little playful touch like this might spark a new connection with another engineer who happens to stumble upon your repository.

If you want to see it in action, please drop by my GitHub profile and leave a trace!

📝 **[Check out my GitHub Profile here!](https://github.com/kanywst)**
