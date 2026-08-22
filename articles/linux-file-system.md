---
title: 'Linux File System Architecture: A Deep Dive into VFS, Inodes, and Storage'
published: true
description: 'In Linux, ''everything is a file''—but how does that actually work? I explore the architecture behind VFS, Inodes, and how data lives on Disks vs RAM.'
tags:
  - linux
  - kernel
  - systems
  - learning
id: 3161782
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/linux-file-system/everything-is-a-file.png'
date: '2026-01-10T03:21:42Z'
series: Linux Kernel
---

## Introduction

**"In Linux, everything is a file."**

We hear this quote often, but do we truly understand what it means? This concept is the core design philosophy of the UNIX operating system.

In Linux, processes, directories, hardware devices (like printers or serial ports), data, and even network communications are abstracted as "files." This allows us to handle them using a consistent set of methods: `open`, `read`, `write`, and `close`.

In this article, we will explore the architecture of the Linux file system and investigate how it actually works under the hood, using practical examples with Docker and Go.

## 1. Virtual File System (VFS)

The concept that "everything is a file" is made possible by a technology called **VFS (Virtual File System)**.

VFS acts as an abstraction layer. It provides a unified input/output interface for all computer resources, including data and devices. Thanks to VFS, the user (and applications) can treat everything as a "file" without worrying about the underlying physical medium.

If VFS didn't exist, you would have to be conscious of the **disk format type** every time you saved a file.

![vfs](https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/linux-file-system/vfs.png)

## 2. The Variety of File Systems

While VFS provides a unified interface, the actual data lives on various types of media. It's no longer just about hard drives.

### Exploring Filesystems with Docker

Let's look at what filesystems actually exist in a modern environment. We'll use a Docker container (Rocky Linux 9) because it's the easiest way to see a mix of different filesystem types.

```bash
# We use --privileged to allow mount operations for demonstration
docker run -it --privileged --name fs-lab rockylinux:9 /bin/bash

```

Let's check the disk usage and types:

```bash
# -T: Print file system type (ext4, xfs, tmpfs, etc.)
# -h: Human-readable sizes
[root@container /]# df -Th
Filesystem     Type     Size  Used Avail Use% Mounted on
overlay        overlay   59G   13G   44G  23% /
tmpfs          tmpfs     64M     0   64M   0% /dev
shm            tmpfs     64M     0   64M   0% /dev/shm
/dev/vda1      ext4      59G   13G   44G  23% /etc/hosts

```

We can categorize these into four main types:

### Type 1: Disk-based Filesystems (Persistent)

This is what we typically think of. Data is stored on physical devices like SSDs or HDDs.

* **Examples:** `ext4`, `xfs`, `btrfs`
* **Role:** Storing OS core files, user data (`/home`), and logs (`/var`).
* **Note:** `ext4` is simply the 4th generation of the extended filesystem.

### Type 2: Memory-based Filesystems (Volatile)

Here, the "disk" is actually the system's RAM. It is incredibly fast, but data vanishes on reboot.

* **Examples:** `tmpfs`, `ramfs`
* **Role:** Temporary files (`/tmp`, `/run`).
* **Why?** `/run` stores PID files and sockets that are only valid for the current session. Writing these to a physical disk would be unnecessary overhead.

### Type 3: Pseudo Filesystems (Virtual)

These files do not exist on any persistent storage. They are generated **on-the-fly** by the kernel when you access them. They look like files, but they are actually **windows into the kernel**.

* **Examples:** `/proc`, `/sys`, `/sys/fs/cgroup`, `/devpts`
* **Role:**
* **`/proc`**: Classic interface. Reading `/proc/cpuinfo` causes the kernel to dynamically generate text about your CPU.
* **`/sys` (sysfs)**: Structured view of connected devices and drivers. You can sometimes change device settings (like screen brightness) by writing to these files.
* **`/sys/fs/cgroup`**: The foundation of container technology. It manages resource limits (CPU/Memory) for processes.
* **`/dev/pts`**: Manages Pseudo Terminals (PTY). Every time you open a terminal or SSH session, a virtual file (e.g., `/dev/pts/0`) is created here to handle input/output.

### Type 4: Layered Filesystems (Union Mount)

This is the magic behind Docker. These filesystems allow you to stack multiple directories (layers) and present them as a single unified filesystem.

* **Examples:** `overlay`, `aufs`
* **Role:** Merging a read-only base layer (OS image) with a writable upper layer (container changes).

#### Deep Dive: OverlayFS

OverlayFS uses a specific structure to achieve deduplication and fast startup.

* **Lower Dir (Base):** The Docker image. Read-Only. Shared among all containers.
* **Upper Dir:** The writable layer for your specific container. Starts empty. Changes are copied here (**Copy on Write**).
* **Merged Dir:** The view you see. The Upper layer "overlays" the Lower layer.

![overlayfs](https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/linux-file-system/overlayfs.png)

## 3. What is a "File" really? (The Inode)

Filenames like `example.txt` are just for humans. Linux identifies files by **Inodes**.

### Structure of an Inode

Let's see an inode in action.

```bash
# Create a dummy file
echo "dummy" > example.txt

# 'stat' shows the inode metadata
stat example.txt
```

**Output:**

```text
  File: example.txt
  Size: 6           Blocks: 8          IO Block: 4096   regular file
Device: f5h/245d  Inode: 1714604     Links: 1
...

```

To see just the Inode number:

```bash
ls -i example.txt
# Output: 1714604 example.txt
```

> **Note:** The filename is **NOT** stored in the inode. It is stored in the directory data, pointing to the inode number.

### When does an Inode change?

Understanding when an inode changes helps you debug issues like "why did my log monitoring stop working?"

#### `cp` vs `mv`

* **`cp` (Copy):** Creates a NEW file with a NEW inode.
* **`mv` (Move):** Renames the file. The inode remains the SAME.

```bash
# cp changes the inode
ls -i example.txt      # 1714604
cp example.txt copy.txt
ls -i copy.txt         # 1714664 (NEW)

# mv keeps the inode
mv copy.txt moved.txt
ls -i moved.txt        # 1714664 (SAME)
```

#### The `sed -i` Trap

Tools like `sed -i` (edit in place) or text editors like Vim often employ a safe saving strategy:

1. Create a temporary file (New Inode).
2. Write changes to the temp file.
3. Rename the temp file to the original name (Overwriting the original).

```bash
# Create file
echo "hello" > config.txt
ls -i config.txt       # 1714736

# Edit with sed
sed -i 's/hello/world/' config.txt

# Inode changed!
ls -i config.txt       # 1714737
```

**Why does this matter?**
If you are monitoring a log file by its inode (e.g., using `inotify`), and the file is rotated or edited via `sed -i`, your monitor might lose track of the file because the original inode is gone!

#### Appending vs. Editing: The Vim Behavior

Let's look at how text editors behave compared to simple redirection. This distinction is crucial for understanding atomic operations.

**1. Appending Data (`>>`)**
When you append to a file, the Inode stays the same because you are just adding data to existing blocks.

```bash
# Create a file
touch target.txt
ls -i target.txt       # 1714736

# Append data
echo "append" >> target.txt

# Inode remains UNCHANGED
ls -i target.txt       # 1714736
```

**2. Editing with Vim**
Text editors like Vim (by default) use a "safe write" strategy to prevent data loss during a crash. They write to a new temporary file and then rename it over the original.

```bash
# Edit with Vim and save (:wq)
vi target.txt

# Inode CHANGED!
ls -i target.txt       # 1714739
```

**What happened?**

1. Vim created a new file with a new Inode.
2. It wrote your content there.
3. It renamed the new file to `target.txt`, overwriting the old one.
4. The old Inode (1714736) was unlinked and deleted.

> **Warning:** If you use tools like `tail -F` or `inotify` to watch logs, you must ensure they can handle this "Inode rotation," or they will keep watching the deleted file!

## 4. Hard Links vs. Symbolic Links

Understanding inodes makes the difference between Hard and Symbolic links crystal clear.

* **Hard Link:** Another directory entry pointing to the **same inode**.
* **Symbolic Link:** A special file pointing to **another path**.

![sym-vs-hard](https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/linux-file-system/sym-vs-hard.png)

Let's verify this:

```bash
echo "Hello" > original.txt
ln original.txt hard.txt      # Hard Link
ln -s original.txt sym.txt    # Symbolic Link

ls -li
# Output:
# 1714669 ... hard.txt
# 1714669 ... original.txt  <-- Same Inode!
# 1714670 ... sym.txt -> original.txt  <-- Different Inode

```

## 5. Process View: File Descriptors

As developers, we rarely touch inodes directly. We manipulate files via **File Descriptors (FD)**.

When a process opens a file, the kernel assigns a non-negative integer (FD). This integer is simply an **index** into the process's table of open files.

Let's check this with Go:

```go
package main

import (
  "fmt"
  "os"
)

func main() {
  // 1. Open a file (System call to Kernel)
  file, err := os.Open("example.txt")
  if err != nil { panic(err) }
  defer file.Close() // Don't forget to close!

  // 2. Check the File Descriptor
  fd := file.Fd()

  fmt.Printf("File Name: %s\n", file.Name())
  fmt.Printf("File Descriptor: %d\n", fd)
}
```

**Result:**

```bash
File Name: example.txt
File Descriptor: 3

```

### Why "3"?

Why did it start at 3? Because Linux processes start with three standard FDs already open:

* **0**: Standard Input (Stdin)
* **1**: Standard Output (Stdout)
* **2**: Standard Error (Stderr)

The kernel assigns the **lowest available number**. Since 0, 1, and 2 are taken, your file gets 3.

![fd](https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/linux-file-system/fd.png)

### File Descriptor Exhaustion

A common production nightmare is the `too many open files` error.

Since **"Everything is a file,"** this applies to more than just text files.

* Database connections
* HTTP Requests (TCP Sockets)
* Log files

They ALL consume File Descriptors.

If a high-traffic web server opens too many sockets (FDs) and hits the limit (check with `ulimit -n`), the application will crash or stop accepting new connections—even if you have plenty of CPU and RAM.

**Solutions:**

1. **Fix Leaks:** Always ensure `Close()` is called (use `defer` in Go).
2. **Tune Limits:** The default limit (often 1024) is too low for servers. Increase it in `/etc/security/limits.conf`.

## Conclusion

By peeling back the layers of the Linux filesystem, we can see it's a beautifully orchestrated architecture:

1. **User Space:** We handle Filenames and File Descriptors.
2. **VFS Layer:** The kernel abstracts the differences between hardware.
3. **Physical Layer:** Data lives on Disks (ext4), RAM (tmpfs), or is calculated on the fly (/proc).

Understanding these layers is critical when debugging performance issues ("Is it disk I/O or a pseudo-fs bottleneck?") or working with containers ("How does my image stay small?").

Please give it a try and let me know what you think in the comments. If you find the project useful, I would really appreciate a star on GitHub!
