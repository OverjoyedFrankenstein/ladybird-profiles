#!/usr/bin/env python3
"""
Adds profile management to an installed Ladybird: the Profiles menu, the Profile management section of
about:settings, and opening, closing, renaming and deleting profiles.

The features are compiled into Ladybird, so they can't be copied into an app that is already built. This script:

  1. finds the Ladybird that is installed,
  2. gets the Ladybird source (a clone of the upstream repository, or a checkout you give it),
  3. applies patches/profiles.patch to it,
  4. builds it with Ladybird's own build script, Meta/ladybird.py,
  5. backs up the installed Ladybird and puts the new build in its place.

It never touches your profiles. They are kept in your user directories, not in the app, and the new build lists every
profile that is already there. The script lists them before and after it installs, and stops if any went missing.

Run `python3 install.py --help` for the options, and `python3 install.py --restore` to put the backup back.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCH = HERE / "patches" / "profiles.patch"
BASE = HERE / "patches" / "base.json"
UPSTREAM = "https://github.com/LadybirdBrowser/ladybird.git"
PRESET = "Release"
BUILD_DIR_FOR_PRESET = Path("Build") / "release"

IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


class InstallError(Exception):
    pass


def say(message: str = "") -> None:
    print(message, flush=True)


def step(message: str) -> None:
    say(f"\n==> {message}")


def run(command: list, cwd: Path | None = None, check: bool = True, capture: bool = False, env: dict | None = None) -> subprocess.CompletedProcess:
    if not capture:
        say("    $ " + " ".join(str(part) for part in command))
    result = subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and result.returncode != 0:
        details = (result.stderr or "").strip() if capture else ""
        raise InstallError(f"`{' '.join(str(part) for part in command)}` failed" + (f":\n{details}" if details else ""))
    return result


def git(source: Path, *args, check: bool = True) -> str:
    return run(["git", "-C", source, *args], check=check, capture=True).stdout.strip()


# --- Where things are ------------------------------------------------------------------------------------------------


def default_work_dir() -> Path:
    if IS_MACOS:
        return Path.home() / "Library" / "Caches" / "ladybird-profiles"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "ladybird-profiles"


def profile_roots() -> dict[str, Path]:
    """The directories that hold named profiles, as Ladybird's Core::StandardPaths finds them."""
    home = Path.home()
    if IS_MACOS:
        roots = {
            "data": home / "Library" / "Application Support",
            "config": home / "Library" / "Preferences",
            "cache": home / "Library" / "Caches",
        }
    else:
        roots = {
            "data": Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share"),
            "config": Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config"),
            "cache": Path(os.environ.get("XDG_CACHE_HOME") or home / ".cache"),
        }
    return {kind: root / "Ladybird" / "Profiles" for kind, root in roots.items()}


def existing_profiles() -> dict[str, set[str]]:
    """Every profile directory there is, by the kind of directory. Ladybird lists a profile by its data directory."""
    found: dict[str, set[str]] = {}
    for kind, directory in profile_roots().items():
        found[kind] = {entry.name for entry in directory.iterdir() if entry.is_dir()} if directory.is_dir() else set()
    return found


class Installation:
    """The Ladybird that is installed: an app bundle on macOS, or an install prefix on Linux."""

    def __init__(self, path: Path):
        self.path = path

    @property
    def version(self) -> str | None:
        if IS_MACOS:
            info = self.path / "Contents" / "Info.plist"
            try:
                with open(info, "rb") as file:
                    return plistlib.load(file).get("CFBundleShortVersionString")
            except (OSError, plistlib.InvalidFileException):
                return None
        return None

    def describe(self) -> str:
        version = self.version
        return f"{self.path}" + (f" (version {version})" if version else "")


def find_installation(app: str | None, prefix: str | None) -> Installation:
    if IS_MACOS:
        if prefix:
            raise InstallError("--prefix is for Linux. On macOS, give the app with --app.")
        candidates = [Path(app).expanduser()] if app else [
            Path("/Applications/Ladybird.app"),
            Path.home() / "Applications" / "Ladybird.app",
        ]
        for candidate in candidates:
            if (candidate / "Contents" / "MacOS" / "Ladybird").exists():
                return Installation(candidate.resolve())
        raise InstallError(
            f"No Ladybird app was found at {app}." if app else
            "Ladybird.app was not found in /Applications or ~/Applications. Give its path with --app."
        )

    if IS_LINUX:
        if app:
            raise InstallError("--app is for macOS. On Linux, give the install prefix with --prefix, such as /usr/local.")
        if prefix:
            candidate = Path(prefix).expanduser().resolve()
            if not (candidate / "bin" / "Ladybird").exists():
                raise InstallError(f"There is no bin/Ladybird under {candidate}.")
            return Installation(candidate)
        executable = shutil.which("Ladybird") or shutil.which("ladybird")
        if not executable:
            raise InstallError("Ladybird was not found on your PATH. Give its install prefix with --prefix.")
        resolved = Path(executable).resolve()
        if "/.mount_" in str(resolved) or "flatpak" in str(resolved) or "/snap/" in str(resolved):
            raise InstallError(
                f"The Ladybird at {resolved} is an AppImage, Flatpak or Snap, which can't be changed in place. "
                "Install the patched build next to it instead, for example with --prefix ~/.local after creating "
                "~/.local/bin/Ladybird, or run it from the build directory."
            )
        installation_prefix = resolved.parent.parent
        if not (installation_prefix / "bin" / "Ladybird").exists():
            raise InstallError(f"Ladybird at {resolved} is not in a bin/ directory of an install prefix. Use --prefix.")
        return Installation(installation_prefix)

    raise InstallError("Only macOS and Linux are supported.")


def ladybird_is_running() -> bool:
    if not shutil.which("pgrep"):
        return False
    return subprocess.run(["pgrep", "-x", "Ladybird"], stdout=subprocess.DEVNULL).returncode == 0


def wait_for_key(seconds: int) -> None:
    """Count down from `seconds`, returning early if a key is pressed (only when run in a terminal)."""
    import select
    import time

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    old_settings = None
    if interactive:
        import termios
        import tty
        try:
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except termios.error:
            interactive = False
    try:
        for remaining in range(seconds, 0, -1):
            if interactive:
                print(f"\r    Trying again in {remaining:2d}s (press any key to try now, Ctrl+C to stop) ",
                      end="", flush=True)
                ready, _, _ = select.select([sys.stdin], [], [], 1)
                if ready:
                    os.read(sys.stdin.fileno(), 1024)  # Swallow the key press.
                    break
            else:
                if remaining == seconds or remaining % 10 == 0:
                    print(f"    Trying again in {remaining}s...", flush=True)
                time.sleep(1)
    finally:
        if old_settings is not None:
            import termios
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        if interactive:
            print()


def wait_for_ladybird_to_quit() -> None:
    """Block until Ladybird is not running, rechecking every 30 seconds or when a key is pressed."""
    if not ladybird_is_running():
        return
    while ladybird_is_running():
        say("\nClose Ladybird for the patch to take place.")
        say("    Quit every window of every profile (Ladybird > Quit Ladybird, or Cmd+Q).")
        wait_for_key(30)
    say("Ladybird is closed. Continuing.")


# --- The source ------------------------------------------------------------------------------------------------------


def prepare_clone(work_dir: Path, upstream: str) -> Path:
    source = work_dir / "ladybird"
    if (source / ".git").exists():
        step(f"Updating the Ladybird source in {source}")
        run(["git", "-C", source, "fetch", "--tags", "--prune", "origin"])
        run(["git", "-C", source, "remote", "set-head", "origin", "--auto"])
    else:
        step(f"Downloading the Ladybird source to {source}")
        work_dir.mkdir(parents=True, exist_ok=True)
        # Without blobs, the clone is small, and git fetches the files of the commit that is checked out on demand.
        run(["git", "clone", "--filter=blob:none", "--no-checkout", upstream, source])
    return source


def patch_is_applied(source: Path) -> bool:
    return run(["git", "-C", source, "apply", "--reverse", "--check", PATCH], check=False, capture=True).returncode == 0


def try_to_apply(source: Path) -> bool:
    """Applies the patch, merging it in where the files changed since. Leaves the tree as it was if it can't."""
    new_files = [source / name for name in json.loads(BASE.read_text())["new_files"]]
    already_there = {path for path in new_files if path.exists()}
    result = run(["git", "-C", source, "apply", "--3way", "--whitespace=nowarn", PATCH], check=False, capture=True)
    if result.returncode == 0:
        return True
    git(source, "reset", "--hard", "-q")
    for path in new_files:
        if path.exists() and path not in already_there:
            path.unlink()
    return False


def exact_base(source: Path, tip: str) -> str | None:
    """The newest commit at which every file that the patch changes is just as it was when the patch was made."""
    base_blobs: dict[str, str] = json.loads(BASE.read_text())["base_blobs"]
    paths = list(base_blobs)

    def matches(commit: str) -> bool:
        listing = git(source, "ls-tree", commit, "--", *paths, check=False)
        blobs = {line.split("\t", 1)[1]: line.split()[2] for line in listing.splitlines() if "\t" in line}
        return blobs == base_blobs

    commits = git(source, "rev-list", tip, "--", *paths).splitlines()
    for index, commit in enumerate(commits):
        if not matches(commit):
            continue
        # The files stay this way until the next commit that changes one of them, so take the commit before that one.
        if index > 0:
            newest = git(source, "rev-parse", f"{commits[index - 1]}^", check=False)
            if newest and matches(newest):
                return newest
        return commit
    return None


def checkout(source: Path, commit: str) -> None:
    git(source, "checkout", "-q", "--detach", "-f", commit)


def describe_commit(source: Path, commit: str) -> str:
    return git(source, "log", "-1", "--format=%h %cs %s", commit)


def patch_source(source: Path, managed: bool, ref: str | None, installed_version: str | None) -> None:
    """Checks out a commit that the patch applies to, and applies it."""
    if not managed:
        # A checkout of yours: patch what is checked out, and never switch commits or throw away changes in it.
        step(f"Patching your Ladybird checkout at {source}")
        if patch_is_applied(source):
            say("    The profile features are already applied.")
            return
        if git(source, "status", "--porcelain", "--untracked-files=no"):
            raise InstallError(f"{source} has uncommitted changes. Commit or stash them, or leave out --source.")
        if not try_to_apply(source):
            raise InstallError(
                f"The patch does not apply to {describe_commit(source, 'HEAD')}. Leave out --source to let this "
                "script pick a matching version of Ladybird."
            )
        say(f"    Applied to {describe_commit(source, 'HEAD')}")
        return

    step("Finding a version of Ladybird that the profile features apply to")
    tip = git(source, "rev-parse", "refs/remotes/origin/HEAD")
    candidates: list[tuple[str, str]] = []
    if ref == "base":
        found = exact_base(source, tip)
        if not found:
            raise InstallError("No upstream commit matches the source the patch was made from.")
        candidates.append(("the source the patch was made from", found))
    elif ref:
        candidates.append((ref, git(source, "rev-parse", f"{ref}^{{commit}}")))
    else:
        # Prefer the release you have installed, then the newest Ladybird, then the exact source the patch was made from.
        if installed_version:
            for tag in git(source, "tag", "--list", f"*{installed_version}", "--sort=-creatordate").splitlines()[:1]:
                candidates.append((f"your installed version, {tag}", git(source, "rev-parse", f"{tag}^{{commit}}")))
        candidates.append(("the newest Ladybird", tip))
        found = exact_base(source, tip)
        if found:
            candidates.append(("the source the patch was made from", found))

    tried = set()
    for label, commit in candidates:
        if commit in tried:
            continue
        tried.add(commit)
        say(f"    Trying {label}: {describe_commit(source, commit)}")
        checkout(source, commit)
        if try_to_apply(source):
            say("    The patch applies.")
            return
        say("    The patch does not apply here.")
    raise InstallError(
        "The patch does not apply to any version that was tried. Ladybird has changed too much since it was made; "
        "it needs to be brought up to date (see README.md)."
    )


# --- Building --------------------------------------------------------------------------------------------------------


def build_environment(source: Path) -> tuple[dict, Path | None]:
    """The environment to build in, which fixes two ways that a developer's machine can break Ladybird's build."""
    env = {**os.environ}

    # Ladybird's dependencies install Python packages into virtual environments of their own, which a pip that is set
    # to install for the user only (PIP_USER, or user = true in pip.conf) refuses to do.
    env["PIP_USER"] = "0"
    toolchain_bin = None

    # Ladybird pins its Rust version in rust-toolchain.toml and treats warnings as errors, so a newer Rust can fail to
    # build it. Only rustup follows the pin, and a Rust from a package manager may come first on the PATH, so the
    # pinned toolchain is put first.
    if shutil.which("rustup"):
        def pinned_cargo() -> subprocess.CompletedProcess:
            return run(["rustup", "which", "cargo"], cwd=source, check=False, capture=True, env=env)

        cargo = pinned_cargo()
        if cargo.returncode != 0:
            say("    Installing the Rust version that Ladybird pins")
            run(["rustup", "toolchain", "install"], cwd=source, check=False, env=env)
            cargo = pinned_cargo()
        if cargo.returncode == 0 and cargo.stdout.strip():
            toolchain_bin = Path(cargo.stdout.strip()).parent
            env["PATH"] = str(toolchain_bin) + os.pathsep + env.get("PATH", "")
            say(f"    Using Rust from {toolchain_bin}")
    return env, toolchain_bin


def build(source: Path, jobs: str | None, stage: Path) -> Path:
    step("Building Ladybird with the profile features (the first build takes a long time)")
    command = [sys.executable, "Meta/ladybird.py", "build", "--preset", PRESET]
    if jobs:
        command += ["--jobs", jobs]
    env, toolchain_bin = build_environment(source)

    # CMake looks for Rust in package managers' folders before the PATH, so it is told where the pinned Rust is. A new
    # build gets it in the cache that it starts from; one that was configured before is configured again.
    build_dir = source / BUILD_DIR_FOR_PRESET
    cache = build_dir / "CMakeCache.txt"
    if toolchain_bin:
        cargo, rustc = toolchain_bin / "cargo", toolchain_bin / "rustc"
        if not cache.exists():
            build_dir.mkdir(parents=True, exist_ok=True)
            cache.write_text(f"RUST_CARGO:FILEPATH={cargo}\nRUST_RUSTC:FILEPATH={rustc}\n")
        elif f"RUST_CARGO:FILEPATH={cargo}" not in cache.read_text(errors="replace"):
            run(["cmake", "-S", source, "-B", build_dir, f"-DRUST_CARGO={cargo}", f"-DRUST_RUSTC={rustc}"], env=env)

    run(command, cwd=source, env=env)

    step(f"Collecting the built Ladybird in {stage}")
    if stage.exists():
        shutil.rmtree(stage)
    components = ["ladybird_Runtime"] if IS_MACOS else ["ladybird_Runtime", "ladybird_Freedesktop", "ladybird_SystemIntegration"]
    for component in components:
        run(["cmake", "--install", source / BUILD_DIR_FOR_PRESET, "--prefix", stage, "--component", component])

    if IS_MACOS:
        app = stage / "bundle" / "Ladybird.app"
        if not (app / "Contents" / "MacOS" / "Ladybird").exists():
            raise InstallError(f"The build did not produce {app}.")
        # Ladybird's install rules copy the libraries into the app before its own libraries are installed, so on a
        # first install those are missing from the app, and it can't start. Copy whatever was left out.
        app_lib = app / "Contents" / "lib"
        app_lib.mkdir(exist_ok=True)
        missing = [library for library in sorted((stage / "lib").glob("*.dylib")) if not (app_lib / library.name).exists()]
        for library in missing:
            shutil.copy2(library, app_lib / library.name, follow_symlinks=False)
        if missing:
            say(f"    Added {len(missing)} libraries that Ladybird's install rules left out of the app")
        sign_macos_app(app, source / "Meta" / "Entitlements.plist")
        return app
    if not (stage / "bin" / "Ladybird").exists():
        raise InstallError(f"The build did not produce {stage / 'bin' / 'Ladybird'}.")
    return stage


def is_mach_o(path: Path) -> bool:
    try:
        with open(path, "rb") as file:
            magic = file.read(4)
    except OSError:
        return False
    return magic in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca")


def sign_macos_app(app: Path, entitlements: Path) -> None:
    """Signs the installed app again, as installing it rewrites its binaries, and macOS won't run an app whose
    signature doesn't match. It is signed the way Ladybird's build signs it: ad hoc, inside out, with its entitlements."""
    step("Signing the new Ladybird")
    contents = app / "Contents"

    def sign(path: Path, *options) -> None:
        run(["codesign", "--sign", "-", "--force", *options, path], capture=True)

    # Libraries and Qt's plugins first, as the code that loads them is signed over them.
    for directory in (contents / "lib", contents / "PlugIns"):
        if directory.is_dir():
            for path in sorted(directory.rglob("*")):
                if path.is_file() and not path.is_symlink() and is_mach_o(path):
                    sign(path)

    sparkle = contents / "Frameworks" / "Sparkle.framework"
    if sparkle.is_dir():
        for nested in ("Autoupdate", "Updater.app"):
            if (sparkle / "Versions" / "B" / nested).exists():
                sign(sparkle / "Versions" / "B" / nested, "--options", "runtime")
        sign(sparkle)

    entitlement_options = ("--entitlements", entitlements) if entitlements.exists() else ()
    main_executable = contents / "MacOS" / "Ladybird"
    for path in sorted((contents / "MacOS").iterdir()):
        if path != main_executable and path.is_file() and is_mach_o(path):
            sign(path, *entitlement_options)
    sign(app, *entitlement_options)

    result = run(["codesign", "--verify", "--deep", "--strict", app], check=False, capture=True)
    if result.returncode != 0:
        raise InstallError(f"The new Ladybird could not be signed, so macOS would not run it:\n{result.stderr.strip()}")
    say("    Signed and verified")


# --- Installing and restoring ----------------------------------------------------------------------------------------


def state_file(work_dir: Path) -> Path:
    return work_dir / "installed.json"


def install_macos(installation: Installation, built_app: Path, backups: Path) -> dict:
    app = installation.path
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backups / f"Ladybird-{installation.version or 'unknown'}-{stamp}.app"
    backups.mkdir(parents=True, exist_ok=True)

    step(f"Backing up {app} to {backup}")
    run(["ditto", app, backup])

    step(f"Installing the new Ladybird at {app}")
    incoming = app.with_name(".Ladybird.app.installing")
    outgoing = app.with_name(".Ladybird.app.replaced")
    for leftover in (incoming, outgoing):
        if leftover.exists():
            shutil.rmtree(leftover)
    try:
        run(["ditto", built_app, incoming])
        app.rename(outgoing)
        incoming.rename(app)
    except (OSError, InstallError) as error:
        if outgoing.exists() and not app.exists():
            outgoing.rename(app)
        raise InstallError(f"Could not replace {app}: {error}. If it needs administrator rights, move the app "
                           f"somewhere you can write to, or run with --app pointing at a copy.")
    shutil.rmtree(outgoing, ignore_errors=True)
    return {"platform": "macos", "app": str(app), "backup": str(backup)}


def install_linux(installation: Installation, stage: Path, backups: Path) -> dict:
    prefix = installation.path
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backups / f"prefix-{stamp}"
    files = sorted(path.relative_to(stage) for path in stage.rglob("*") if path.is_file() or path.is_symlink())

    def writable(path: Path) -> bool:
        while not path.exists() and not path.is_symlink():
            path = path.parent
        return os.access(path, os.W_OK)

    unwritable = [prefix / rel for rel in files if not writable(prefix / rel)]
    if unwritable:
        raise InstallError(f"Can't write to {unwritable[0]} (and {len(unwritable) - 1} more). Run with sudo, "
                           "keeping your home directory: sudo -E python3 install.py ...")

    step(f"Backing up the files that will be replaced to {backup}")
    replaced, added = [], []
    for rel in files:
        target = prefix / rel
        if target.exists() or target.is_symlink():
            (backup / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup / rel, follow_symlinks=False)
            replaced.append(str(rel))
        else:
            added.append(str(rel))

    step(f"Installing the new Ladybird into {prefix}")
    for rel in files:
        target = prefix / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or target.exists():
            target.unlink()
        shutil.copy2(stage / rel, target, follow_symlinks=False)
    say(f"    {len(replaced)} files replaced, {len(added)} added")
    return {"platform": "linux", "prefix": str(prefix), "backup": str(backup), "replaced": replaced, "added": added}


def restore(work_dir: Path) -> None:
    state_path = state_file(work_dir)
    if not state_path.exists():
        raise InstallError(f"There is no record of an install in {work_dir}, so there is nothing to restore.")
    wait_for_ladybird_to_quit()
    state = json.loads(state_path.read_text())

    if state["platform"] == "macos":
        app, backup = Path(state["app"]), Path(state["backup"])
        if not backup.exists():
            raise InstallError(f"The backup {backup} is gone.")
        step(f"Putting back {backup} at {app}")
        incoming = app.with_name(".Ladybird.app.installing")
        if incoming.exists():
            shutil.rmtree(incoming)
        run(["ditto", backup, incoming])
        if app.exists():
            shutil.rmtree(app)
        incoming.rename(app)
    else:
        prefix, backup = Path(state["prefix"]), Path(state["backup"])
        step(f"Restoring the files in {prefix} from {backup}")
        for rel in state["added"]:
            target = prefix / rel
            if target.exists() or target.is_symlink():
                target.unlink()
        for rel in state["replaced"]:
            target = prefix / rel
            if target.exists() or target.is_symlink():
                target.unlink()
            shutil.copy2(backup / rel, target, follow_symlinks=False)

    state_path.rename(state_path.with_suffix(".restored.json"))
    say("\nThe Ladybird you had before is back. Your profiles were not changed.")


def report_profiles(profiles: dict[str, set[str]]) -> None:
    names = sorted(profiles["data"])
    if names:
        say(f"    {len(names)} existing profile(s), which will all be listed in the Profiles menu: {', '.join(names)}")
    else:
        say("    No named profiles yet. Ladybird creates its usual one the first time it starts.")
    say(f"    (in {profile_roots()['data']})")


def check_profiles_kept(before: dict[str, set[str]]) -> None:
    after = existing_profiles()
    missing = {kind: names - after[kind] for kind, names in before.items() if names - after[kind]}
    if missing:
        raise InstallError(f"Profile directories went missing during the install: {missing}. Nothing in this script "
                           "removes them, so check whether something else did.")


def refresh_patch(source: Path) -> None:
    """Writes the changes in a Ladybird checkout, against its HEAD, to patches/ as the new profile features."""
    if not (source / "Meta" / "ladybird.py").exists():
        raise InstallError(f"{source} is not a Ladybird checkout.")
    step(f"Taking the profile features from {source}, against {describe_commit(source, 'HEAD')}")
    git(source, "add", "--intent-to-add", "--all")
    patch = git(source, "diff", "--binary", "--full-index", "HEAD") + "\n"
    if patch.strip() == "":
        raise InstallError(f"{source} has no changes against HEAD.")
    changed = git(source, "diff", "--name-only", "--diff-filter=M", "HEAD").splitlines()
    added = git(source, "diff", "--name-only", "--diff-filter=A", "HEAD").splitlines()
    if git(source, "diff", "--name-only", "--diff-filter=DRC", "HEAD"):
        raise InstallError("Deleted or renamed files aren't supported in the patch.")
    listing = git(source, "ls-tree", "HEAD", "--", *changed)
    base_blobs = {line.split("\t", 1)[1]: line.split()[2] for line in listing.splitlines()}
    description = json.loads(BASE.read_text())["description"] if BASE.exists() else ""
    PATCH.parent.mkdir(exist_ok=True)
    PATCH.write_text(patch)
    BASE.write_text(json.dumps({"description": description, "new_files": added, "base_blobs": base_blobs}, indent=2) + "\n")
    say(f"    {len(changed)} changed and {len(added)} new files written to {PATCH.relative_to(HERE)}")


# --- Main ------------------------------------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add profile management to an installed Ladybird. Your existing profiles are kept.",
        epilog="Building Ladybird needs its build tools; see https://github.com/LadybirdBrowser/ladybird/blob/master/"
               "Documentation/BuildInstructionsLadybird.md",
    )
    parser.add_argument("--app", help="macOS: the Ladybird.app to upgrade (default: /Applications/Ladybird.app)")
    parser.add_argument("--prefix", help="Linux: the install prefix of Ladybird, such as /usr/local (default: from PATH)")
    parser.add_argument("--source", help="Patch and build this Ladybird checkout instead of downloading one")
    parser.add_argument("--ref", help="Build this upstream tag or commit. 'base' is the exact source the patch was made from")
    parser.add_argument("--upstream", default=UPSTREAM, help=f"The repository to download Ladybird from (default: {UPSTREAM})")
    parser.add_argument("--work-dir", help=f"Where the source, build and backups are kept (default: {default_work_dir()})")
    parser.add_argument("--jobs", "-j", help="How many build jobs to run at once")
    parser.add_argument("--dry-run", action="store_true", help="Get and patch the source, but don't build or install")
    parser.add_argument("--build-only", action="store_true", help="Build, but don't install")
    parser.add_argument("--yes", "-y", action="store_true", help="Don't ask before replacing the installed Ladybird")
    parser.add_argument("--restore", action="store_true", help="Put back the Ladybird that the last install replaced")
    parser.add_argument("--refresh-patch", metavar="DIR", help="For working on the features: replace patches/ with the changes in this checkout")
    args = parser.parse_args()

    work_dir = Path(args.work_dir).expanduser().resolve() if args.work_dir else default_work_dir()

    try:
        if args.restore:
            restore(work_dir)
            return 0
        if args.refresh_patch:
            refresh_patch(Path(args.refresh_patch).expanduser().resolve())
            return 0

        if not shutil.which("git"):
            raise InstallError("git is needed.")
        if not PATCH.exists() or not BASE.exists():
            raise InstallError(f"{PATCH.parent} is incomplete. Download this project again.")
        if args.source and args.ref:
            raise InstallError("--ref picks a commit to download, so it can't be combined with --source.")

        step("Looking for your Ladybird")
        installation = None
        if not args.build_only and not args.dry_run:
            installation = find_installation(args.app, args.prefix)
        else:
            try:
                installation = find_installation(args.app, args.prefix)
            except InstallError:
                pass
        say(f"    {installation.describe()}" if installation else "    None found (not needed to build only)")

        step("Looking for your profiles")
        profiles_before = existing_profiles()
        report_profiles(profiles_before)

        if installation and not args.build_only and not args.dry_run:
            wait_for_ladybird_to_quit()

        if args.source:
            source = Path(args.source).expanduser().resolve()
            if not (source / "Meta" / "ladybird.py").exists():
                raise InstallError(f"{source} is not a Ladybird checkout.")
            patch_source(source, managed=False, ref=None, installed_version=None)
        else:
            source = prepare_clone(work_dir, args.upstream)
            patch_source(source, managed=True, ref=args.ref, installed_version=installation.version if installation else None)

        if args.dry_run:
            say(f"\nDry run: the patched source is ready in {source}. Nothing was built or installed.")
            return 0

        built = build(source, args.jobs, work_dir / "stage")
        if args.build_only:
            say(f"\nBuilt: {built}. Nothing was installed.")
            return 0

        if not args.yes:
            answer = input(f"\nReplace {installation.describe()} with the new build? A backup is kept. [y/N] ")
            if answer.strip().lower() not in ("y", "yes"):
                say("Nothing was installed.")
                return 1

        wait_for_ladybird_to_quit()

        backups = work_dir / "backups"
        state = install_macos(installation, built, backups) if IS_MACOS else install_linux(installation, built, backups)
        state["source_commit"] = git(source, "rev-parse", "HEAD")
        state["installed_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        state_file(work_dir).write_text(json.dumps(state, indent=2))

        check_profiles_kept(profiles_before)
        step("Done")
        report_profiles(existing_profiles())
        say("    Open the Profiles menu, or about:settings > Profile management, to use them.")
        say(f"    To undo: python3 {Path(__file__).name} --restore")
        if IS_MACOS:
            say("    Updating Ladybird from its own updater puts back a Ladybird without these features; run this "
                "script again afterwards. Your profiles are kept either way.")
        return 0
    except InstallError as error:
        say(f"\nerror: {error}")
        return 1
    except KeyboardInterrupt:
        say("\nStopped. The installed Ladybird was not changed unless the last step said it was being installed.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
