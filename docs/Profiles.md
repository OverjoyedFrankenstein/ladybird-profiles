# Profiles

A profile holds everything that Ladybird keeps for one person or one purpose: settings, bookmarks, history, cookies,
site data, permissions, saved sessions and the HTTP cache. Profiles are kept apart from each other, so signing in to a
site in one profile does not sign you in to it in another.

Each profile runs in a Ladybird of its own, with its own Hub and helper processes. Several profiles can be open at the
same time, each in its own windows.

## Using profiles

### The Profiles menu

The **Profiles** menu is in the menu bar, between **History** and **Inspect**, and in the Ladybird menu of each window,
above **History**. It lists every profile, in alphabetical order, and checks the one that the window belongs to. The
primary profile is marked **(Primary)**.

* Choosing a profile opens a window of it. A profile that is not open is started in a new Ladybird. A profile that is
  already open gets a new window.
* **Primary Profile** lists every profile again, and checks the primary one. Choosing a profile there makes it primary.
* **Create…** asks for the name of a new profile and adds it to the list.

### The primary profile

The primary profile is the one that Ladybird starts with when it is started without a profile option, such as from the
Dock, the Applications folder or a desktop launcher. It is the usual profile (`default`, or `developer` in builds made
from source) until another one is made primary, from the Profiles menu or from Settings. A Ladybird that is already
running is not affected: the choice applies the next time Ladybird starts.

* Renaming the primary profile keeps it primary under its new name.
* Deleting the primary profile makes the usual profile primary again.
* A Ladybird that restarts, such as after an update or a settings change that needs one, comes back with the profile
  it was running with, even if another profile has been made primary since.

### Profile management in Settings

The **Profile management** section of `about:settings` lists every profile, and notes which one is primary. Each profile has an **Open** button and a
gear button, whose menu has the following items:

| Item | What it does |
| --- | --- |
| **Make primary** | Makes the profile the one that Ladybird starts with. It is greyed out for the profile that is already primary. |
| **Close** | Closes every window of the profile. Its windows and tabs come back, and are loaded again, the next time the profile is opened, whatever the startup settings say. |
| **Rename…** | Gives the profile a new name. All of its data moves with it. |
| **Delete…** | Deletes the profile and all of its data from this computer. This cannot be undone. |

A profile that a Ladybird is running with cannot be renamed, as its files are in use. Close it first.

Closing or deleting the profile of the window that you are in first asks for another profile to switch to. That profile
opens, and the one you were in closes. A profile that is deleted this way disappears from every list at once, and its
data is removed as soon as its Ladybird has ended.

**Close** is only offered for profiles that are open in the same build of Ladybird. An older build does not know how to
close while keeping its windows, so its profiles have to be closed from their own windows.

### Profile names

Profile names are the names of directories, so they may only contain lowercase ASCII letters, digits, `-` and `_`.
Uppercase letters that are typed into a name become lowercase.

### From the command line

| Option | Effect |
| --- | --- |
| `--profile=<name>` | Opens the named profile, creating it if it does not exist. |
| `--profile-path=<absolute path>` | Uses a self-contained profile in the given directory. |
| `--temporary-profile` | Uses an empty profile that is removed when Ladybird quits. |

Without any of these, Ladybird uses the primary profile. Until another profile is made primary, that is the `default`
profile in release builds, and the `developer` profile in builds made from source. A profile with one of those names
that was renamed or deleted is created again, empty, the next time Ladybird starts with it as the primary profile.

On macOS, `open -n -a Ladybird --args --profile=work` starts a profile from the terminal. Without `-n`, macOS brings the
Ladybird that is already running to the front, and ignores the arguments.

## Where profiles are stored

A named profile has a directory in each of three places. On macOS, these are:

| Directory | Contents |
| --- | --- |
| `~/Library/Application Support/Ladybird/Profiles/<name>/` | History, sessions, crash reports, content blocking lists, and the files that mark a running profile |
| `~/Library/Preferences/Ladybird/Profiles/<name>/` | `Settings.json`, `Bookmarks.json` and `Permissions.json` |
| `~/Library/Caches/Ladybird/Profiles/<name>/` | The HTTP cache |

Which profile is primary is kept in `~/Library/Application Support/Ladybird/PrimaryProfile`, beside the profiles rather
than in any one of them. The file holds the profile's name. A missing file, or one that names a profile that does not
exist, means the usual profile.

On Linux, the same layout is under `$XDG_DATA_HOME`, `$XDG_CONFIG_HOME` and `$XDG_CACHE_HOME`, and the files that
mark a running profile are under `$XDG_RUNTIME_DIR`.

## How it works

`WebView::Profile` in `Libraries/LibWebView/Profile.h` lists, creates, renames and removes profiles. The UI uses it for
the Profiles menu, and `WebView::SettingsUI` uses it for the Profile management section.

### Telling whether a profile is in use

A Ladybird that runs with a profile writes the PID of its Hub to `Ladybird.pid` in the profile, and removes the file
when it ends. A Ladybird that is starting with a profile holds an exclusive lock on `startup.lock` in the profile until
it has started. A profile is in use while the process named in `Ladybird.pid` is running, or while its startup lock is
held. A PID file left behind by a Ladybird that crashed does not keep the profile in use.

Renaming and removing a profile take its startup lock first, and keep it for as long as they change its directories, so
that no Ladybird starts with the profile meanwhile. A rename that fails partway renames back the directories that it had
renamed, so that a profile is never left split between two names.

### Opening a profile

The Profiles menu and the **Open** button both end up in `Ladybird::Application::open_profile()` in the UI process. The
settings page runs in the Hub, which asks the UI with the `app_open_profile` message. A profile that the window belongs
to gets a new window. Any other profile is started by running the Ladybird executable with `--profile=<name>`. A Ladybird
that is already running with that profile takes the request, and opens a window, as it does for any other launch.

### Closing a profile

To close a profile, the settings page sends `SIGUSR1` to the Hub of the Ladybird that runs with it. The Hub passes the
request on to its UI with the `app_close_keeping_session` message, and the UI quits the way it does when it restarts:
the session store records that every window is to come back on the next launch. Only a Ladybird whose Hub runs the same
executable as the one asking is sent the signal, as an older build would end at once on it, and lose its windows.

Closing the profile of the window that asks opens the profile chosen to switch to first. The UI receives both requests
in order, so the other profile has been started by the time this one quits.

### Deleting a profile that is open

A Ladybird cannot remove the profile that it runs with, so deleting the profile of the window that asks marks the
profile with a `RemoveWhenClosed` file before it closes it. A marked profile is not listed any more. Each Ladybird
removes the marked profiles that nothing uses as it starts, every 15 seconds afterwards, and whenever the settings page
lists the profiles. Opening a marked profile by name with `--profile` removes the mark, and keeps the profile.
Ladybirds that run tests, run headless, or are driven by WebDriver never remove profiles.

## Testing

The tests in `Tests/LibWebView/TestProfile.cpp` cover listing, renaming and removing profiles, refusing to change a
profile that is in use or starting, removing profiles that were deleted while they were open, and choosing the primary
profile, including keeping it through a rename and falling back to the usual profile once it is deleted:

```sh
cmake --build Build/release --target TestLibWebView
LADYBIRD_SOURCE_DIR="$PWD" Build/release/bin/TestLibWebView --suite TestProfile
```
