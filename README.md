# Ladybird Profiles

**Ladybird Profiles** is an add-on for the [Ladybird](https://ladybird.org) browser that adds full profile
management. Use it to keep work, personal and testing browsing apart, switch between them from a menu, and choose
which profile Ladybird starts with.

The add-on is a patch to Ladybird's source code plus an installer script, `install.py`. The script builds Ladybird
with the patch applied and installs that build in place of the Ladybird you already have. **Your existing profiles
are kept.** Every profile you already have shows up in the new menus, next to any you create.

## Quick start

Open Terminal, paste this line and press Return:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/OverjoyedFrankenstein/ladybird-profiles/main/install.sh)"
```

That's the whole install. It downloads the latest version of this add-on to a temporary folder and runs it, so
there's nothing to keep around. Run the same line again later to update.

**Undo**, putting back the Ladybird you had before:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/OverjoyedFrankenstein/ladybird-profiles/main/install.sh)" - --restore
```

**Try it first**, checking everything without building or installing:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/OverjoyedFrankenstein/ladybird-profiles/main/install.sh)" - --dry-run
```

The installer checks for the build tools and offers to install any that are missing. If Ladybird is open, it asks
you to close it. It asks once more before it replaces your Ladybird, and it opens the new Ladybird when it's done. The
first build takes an hour or more. See [How to install](#how-to-install) for the details and
[Installer options](#installer-options) for the other options, which go at the end of the command the same way.

## Contents

- [Quick start](#quick-start)
- [What it does](#what-it-does)
- [Features](#features)
- [Requirements](#requirements)
- [How to install](#how-to-install)
- [How to use it](#how-to-use-it)
- [Undoing the install](#undoing-the-install)
- [Installer options](#installer-options)
- [Your existing profiles are safe](#your-existing-profiles-are-safe)
- [Troubleshooting](#troubleshooting)
- [What's in this repository](#whats-in-this-repository)
- [Changing the features](#changing-the-features)

## What it does

Stock Ladybird can already keep separate profiles, but only if you start it from a terminal with `--profile=<name>`.
There is no way to see, create, switch or manage profiles from inside the browser. This add-on adds that: a Profiles
menu, a Profile management section in Settings, and a primary profile that Ladybird starts with.

Each profile keeps its own settings, bookmarks, history, cookies, site data, permissions, saved sessions and cache.
Signing in to a site in one profile does not sign you in to it in another. Several profiles can be open at the same
time, each in its own windows.

### Why it has to be built

Ladybird's features are compiled into the app, so they can't be copied into an app that is already built. The
installer therefore:

1. finds the Ladybird you have installed,
2. downloads the Ladybird source and picks a version the patch applies to,
3. applies `patches/profiles.patch`,
4. builds Ladybird with its own build script,
5. backs up your Ladybird and installs the new build in its place.

## Features

### Profiles menu

A **Profiles** menu in the menu bar, between **History** and **Inspect**, and in the Ladybird menu of every window.

- Lists every profile in alphabetical order, with a check mark next to the profile the window belongs to.
- Marks the primary profile **(Primary)**.
- Choosing a profile opens a window of it. A profile that isn't open starts in its own Ladybird; one that is already
  open gets a new window.
- **Primary Profile** submenu: choose which profile Ladybird starts with.
- **Create…** asks for a name and adds a new, empty profile to the list.

### Profile management in Settings

A **Profile management** section in `about:settings` lists every profile. It notes which one is primary, which one
you're in, and which are open in other windows. Each profile has an **Open** button and a gear menu with:

| Item | What it does |
| --- | --- |
| **Make primary** | Makes this the profile Ladybird starts with. |
| **Close** | Closes every window of the profile. Its windows and tabs come back the next time you open it. |
| **Rename…** | Renames the profile. All of its data moves with it. |
| **Delete…** | Deletes the profile and all of its data, after asking you to confirm. This can't be undone. |

### Primary profile

The primary profile is the one Ladybird opens when you start it normally, from the Dock, the Applications folder or a
launcher. Until you choose another, it's Ladybird's usual `default` profile.

- Renaming the primary profile keeps it primary under its new name.
- Deleting the primary profile makes `default` primary again.
- When Ladybird restarts itself, for example after a settings change, it comes back with the profile it was
  running with.

### Switching safely

- Closing or deleting the profile you're in first asks which profile to switch to. That profile opens, then the one
  you were in closes.
- A profile you delete while it's open disappears from every list at once. Its data is removed as soon as its windows
  have closed.
- A profile that is open can't be renamed, because its files are in use. Close it first.
- A profile is never renamed or deleted while a Ladybird is starting with it. Renaming and deleting lock the profile
  first, and a rename that fails partway is undone, so a profile is never left half-renamed.

### Profile names

Names may contain lowercase letters, digits, `-` and `_`. Uppercase letters you type become lowercase.

### Command line

The existing options still work, and now fit in with the menus:

| Option | Effect |
| --- | --- |
| `--profile=<name>` | Opens the named profile, creating it if it doesn't exist. |
| `--profile-path=<absolute path>` | Uses a self-contained profile in the given folder. |
| `--temporary-profile` | Uses an empty profile that's removed when Ladybird quits. |
| *(none of these)* | Opens the primary profile. |

On macOS, `open -n -a Ladybird --args --profile=work` opens a profile from the terminal.

For how it all works inside Ladybird, see [docs/Profiles.md](docs/Profiles.md).

## Requirements

- **macOS or Linux.** Windows isn't supported by the installer.
- **Ladybird installed.** On macOS, at `/Applications/Ladybird.app` or `~/Applications/Ladybird.app` (or anywhere,
  with `--app`). On Linux, a `Ladybird` on your `PATH` (or any install prefix, with `--prefix`).
- **Python 3.9 or later** and **git**.
- **Ladybird's build tools.** On macOS that means Xcode and the Homebrew packages that Ladybird's
  [build instructions](https://github.com/LadybirdBrowser/ladybird/blob/master/Documentation/BuildInstructionsLadybird.md)
  list; on Linux, the packages listed there for your distribution. Install Rust with [rustup](https://rustup.rs), so
  the build gets the Rust version that Ladybird pins.
- **Time and disk space.** The first build takes a long time, often an hour or more, and needs tens of gigabytes
  free. Later runs reuse the build and are much faster.

You don't have to set up the build tools yourself. Before it downloads or builds anything, the installer checks for
them and lists anything that's missing, with the exact commands that would install it. Answer `y` to run them, or press
Enter to cancel without changing anything.

| Checked | On macOS it offers to | On Linux it offers to |
| --- | --- | --- |
| git | Install the Xcode command line tools | `sudo apt install git` |
| Xcode 26 or newer | Open Xcode in the App Store. Install it, open it once, then run the installer again | – |
| Xcode selected and its license accepted | `sudo xcode-select --switch …`, `sudo xcodebuild -license accept` | – |
| Homebrew | Run Homebrew's official installer | – |
| Ladybird's build packages | `brew install …` for the missing ones | `sudo apt install …` for the missing ones (Debian and Ubuntu) |
| rustup | `brew install rustup` | rustup's official installer |
| A C++23 compiler, CMake 3.30 or newer | – | Tell you what to install |
| 40 GB free for a first build | Tell you to free space or use `--work-dir` | Same |

After installing, it checks again and carries on only when everything is there. `--yes` answers yes to this
question too. A dry run checks only for git.

## How to install

1. Download or clone this repository.
2. From this folder, run:

   ```sh
   python3 install.py
   ```

The script prints each step as it goes:

- It shows the Ladybird it found and the profiles you already have.
- It checks for the build tools, and offers to install any that are missing.
- If Ladybird is open, it says **Close Ladybird for the patch to take place** and waits for you to quit it.
- It downloads the Ladybird source and applies the patch.
- It builds. This is the long part.
- It asks before replacing your Ladybird. Answer `y` to install.
- It backs up your current Ladybird and installs the new one.
- It confirms that all your profiles are still there.
- It opens the new Ladybird. Add `--no-launch` if you don't want that.

You'll find the **Profiles** menu in the menu bar and **Profile management** in `about:settings`.

### Or run it straight from GitHub

The commands in [Quick start](#quick-start) run `install.sh`, which downloads this repository to a temporary folder and
runs `install.py` from there. The build, backups and install record live in the work directory (`~/Library/Caches/ladybird-profiles`), not
next to the script, so `--restore` works from any copy.

If Ladybird is open, the installer says **Close Ladybird for the patch to take place** and counts down from 30. It
checks again when the countdown ends or when you press a key, and carries on once Ladybird is closed. Press Ctrl+C to
stop without changing anything.

To check that everything will work before committing to a long build, start with a dry run. It finds your Ladybird
and profiles, downloads the source and applies the patch, but builds and installs nothing:

```sh
python3 install.py --dry-run
```

## How to use it

| To… | Do this |
| --- | --- |
| Create a profile | **Profiles → Create…**, then type a name. |
| Open a profile | Choose it in the **Profiles** menu, or click **Open** next to it in `about:settings`. |
| Choose the profile Ladybird starts with | **Profiles → Primary Profile → *name***, or **Make primary** in its gear menu in Settings. |
| Close a profile but keep its tabs for next time | **Close** in its gear menu in Settings. |
| Rename a profile | Close it, then **Rename…** in its gear menu in Settings. |
| Delete a profile | **Delete…** in its gear menu in Settings. |

## Undoing the install

```sh
python3 install.py --restore
```

This puts back the Ladybird you had before, from the backup the installer made. Quit Ladybird first.

Your profiles stay as they are, including any you created with the add-on. Stock Ladybird opens its usual profile; it
doesn't know about the primary profile, so it ignores that setting. Your other profiles are still on disk and open
with `--profile=<name>`.

## Installer options

| Option | What it does |
| --- | --- |
| `--dry-run` | Find Ladybird and your profiles, download and patch the source, then stop. Nothing is built or installed. |
| `--build-only` | Build, but don't install. |
| `--yes`, `-y` | Don't ask before installing missing build tools or replacing your Ladybird. |
| `--restore` | Put back the Ladybird that the last install replaced. |
| `--no-launch` | Don't open Ladybird when the install or restore is done. |
| `--app PATH` | macOS: the `Ladybird.app` to upgrade. Default: `/Applications/Ladybird.app`, then `~/Applications/Ladybird.app`. |
| `--prefix DIR` | Linux: the install prefix of Ladybird, such as `/usr/local`. Default: found from the `Ladybird` on your `PATH`. |
| `--source DIR` | Patch and build a Ladybird checkout you already have instead of downloading one. It needs no uncommitted changes. |
| `--ref REF` | Build a particular upstream tag or commit. `--ref base` builds the exact source the patch was made from. |
| `--upstream URL` | Download Ladybird from another repository, such as a fork. |
| `--work-dir DIR` | Where the source, build and backups go. Default: `~/Library/Caches/ladybird-profiles` on macOS, `~/.cache/ladybird-profiles` on Linux. |
| `--jobs N`, `-j N` | How many build jobs to run at once. |
| `--refresh-patch DIR` | For working on the add-on: replace `patches/` with the changes in a Ladybird checkout. See [Changing the features](#changing-the-features). |

### Which version of Ladybird it builds

Unless you pass `--ref`, the installer tries these in order and uses the first one the patch applies to:

1. the release you have installed, if Ladybird's repository has a tag for it,
2. the newest Ladybird,
3. the exact source the patch was made from.

## Your existing profiles are safe

Ladybird keeps profiles in your user folders, not inside the app:

| | macOS | Linux |
| --- | --- | --- |
| Data | `~/Library/Application Support/Ladybird/Profiles/` | `~/.local/share/Ladybird/Profiles/` |
| Settings, bookmarks | `~/Library/Preferences/Ladybird/Profiles/` | `~/.config/Ladybird/Profiles/` |
| Cache | `~/Library/Caches/Ladybird/Profiles/` | `~/.cache/Ladybird/Profiles/` |

- The installer replaces only the app. It never writes to these folders.
- The new build finds profiles by listing these folders, so every profile you already have appears in the Profiles
  menu and in Settings straight away, next to any you create.
- The installer lists your profiles before and after it installs, and stops with an error if any went missing.
- Nothing is made primary until you choose a profile, so Ladybird keeps starting with the profile it always has.
- The add-on only deletes a profile when you choose **Delete…** and confirm it.

## Troubleshooting

**"Ladybird is running."** Quit every Ladybird window, including other profiles' windows, and run the script again.
On macOS, `pgrep -x Ladybird` shows whether one is still running.

**The build fails.** Check that Ladybird's build tools are installed (see [Requirements](#requirements)). If the
newest Ladybird has changed in a way the patch doesn't build against, build the exact source it was made from with
`python3 install.py --ref base`.

**A download hangs during the build.** Ladybird's build downloads the source of each library it uses, and a dropped
connection can leave a download stuck without an error. Press Ctrl+C and run the same command again: the build picks
up where it stopped, and finished libraries are not built again.

**pip says "Can not perform a '--user' install".** The installer already handles this for you. If you build Ladybird
yourself and have `user = true` in your pip config, run the build with `PIP_USER=0`.

**Rust errors such as "use of deprecated method".** Ladybird pins its Rust version, and a newer Rust, such as
Homebrew's, can fail to build it. The installer uses the pinned version through [rustup](https://rustup.rs) when rustup
is installed, so install rustup if you see this.

**"The patch does not apply to any version that was tried."** Ladybird has changed too much since the patch was made.
Install with `--ref base`, or bring the patch up to date (see [Changing the features](#changing-the-features)).

**Permission errors when installing.** On macOS, check you can write to the folder that holds `Ladybird.app`. On
Linux, if the prefix belongs to root, such as `/usr/local`, run `sudo -E python3 install.py` so the work folder stays
in your home.

**AppImage, Flatpak or Snap on Linux.** These can't be changed in place. Install to a prefix you own instead, such as
`--prefix ~/.local`.

**The features disappeared after updating Ladybird.** Ladybird's built-in updater installs a stock Ladybird. Your
profiles are kept. Run `python3 install.py` again to add the features back.

## What's in this repository

| Path | What it is |
| --- | --- |
| `README.md` | This file. |
| `install.sh` | The one-line installer. It downloads this repository and runs `install.py`. |
| `install.py` | The installer. |
| `patches/profiles.patch` | All of the add-on's changes to Ladybird: 22 changed files and 4 new ones. |
| `patches/base.json` | The ids of the original versions of the changed files. The installer uses them to find a matching Ladybird. |
| `docs/Profiles.md` | How profiles work inside Ladybird. The patch also adds it to Ladybird's `Documentation/`. |
| `LICENSE` | Ladybird's BSD 2-clause license, which covers the patch, as it changes Ladybird's code. |

The patch changes these parts of Ladybird:

| Area | Files |
| --- | --- |
| Profile storage: listing, renaming, deleting, locking, primary profile | `Libraries/LibWebView/Profile.{h,cpp}`, `Libraries/LibWebView/Application.{h,cpp}` |
| Settings page | `Base/res/ladybird/about-pages/settings.html`, `settings/profiles.js` (new), `Libraries/LibWebView/WebUI/SettingsUI.{h,cpp}`, `UI/cmake/ResourceFiles.cmake` |
| Opening and closing profiles from Settings | `Services/Hub/Application.{h,cpp}`, `Services/Hub/HubClient.ipc`, `UI/Qt/HubConnection.{h,cpp}` |
| Profiles menu and Create dialog | `UI/Qt/Application.{h,cpp}`, `UI/Qt/ProfileDialog.{h,cpp}` (new), `UI/Qt/BrowserWindow.cpp`, `UI/Qt/ChromeStyle.{h,cpp}`, `UI/Qt/CMakeLists.txt` |
| Tests | `Tests/LibWebView/TestProfile.cpp` |
| Documentation | `Documentation/Profiles.md` (new), `Documentation/README.md`, `README.md` |

## Changing the features

The patch is the source of truth. To change the add-on, get a patched Ladybird checkout, edit it, then write the
changes back to `patches/`:

```sh
python3 install.py --dry-run --work-dir ~/ladybird-profiles-dev
cd ~/ladybird-profiles-dev/ladybird
# Edit, then build and try it out:
./Meta/ladybird.py run
# Run the profile tests:
./Meta/ladybird.py build TestLibWebView
LADYBIRD_SOURCE_DIR="$PWD" Build/release/bin/TestLibWebView --suite TestProfile
cd -
python3 install.py --refresh-patch ~/ladybird-profiles-dev/ladybird
```

`--refresh-patch` writes every change in that checkout, against the commit it has checked out, to
`patches/profiles.patch`. It also records that commit's versions of the changed files in `patches/base.json`. To move
the add-on to a newer Ladybird, check out the newer commit in the checkout, apply and fix the patch, then refresh it.
