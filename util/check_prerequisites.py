#!/usr/bin/env python3
"""Checks the prerequisites needed to set up the vial-gui development
environment (venv + ``fbs run``) and offers to install any that are missing.

Usage:
    python util/check_prerequisites.py

Nothing is installed without an explicit "yes" from the user for that
specific item; the script only reports status when run non-interactively
(e.g. piped input) or when the user declines a prompt.
"""
import platform
import shutil
import subprocess
import sys

# Debian/Ubuntu package names required to build the hidapi extension that
# requirements.txt pulls in, matching .github/workflows/test.yml.
LINUX_BUILD_PACKAGES = ["libusb-1.0-0-dev", "libudev-dev", "build-essential"]


def confirm(prompt):
    """Ask the user for a yes/no answer; defaults to "no" when input isn't available."""
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def run(cmd):
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd) == 0


class Check:
    def __init__(self, name):
        self.name = name
        self.ok = False
        self.message = ""

    def report(self):
        status = "OK" if self.ok else "MISSING"
        print(f"[{status:7}] {self.name}: {self.message}")


def check_python_version():
    c = Check("Python 3.6.x")
    major, minor = sys.version_info[:2]
    if (major, minor) == (3, 6):
        c.ok = True
        c.message = sys.version.split()[0]
    else:
        c.message = (
            f"found {sys.version.split()[0]}, but fbs officially supports only 3.6.x; "
            "the app may still run on newer versions, use at your own risk"
        )
    c.report()
    return c


def check_command(name, display_name=None, install_hint=None):
    c = Check(display_name or name)
    path = shutil.which(name)
    if path:
        c.ok = True
        c.message = path
    else:
        c.message = install_hint or "not found on PATH"
    c.report()
    return c


def check_venv_module():
    c = Check("venv module")
    try:
        import venv  # noqa: F401
        c.ok = True
        c.message = "available"
    except ImportError:
        c.message = "the 'venv' standard library module is missing from this Python install"
    c.report()
    return c


def offer_git_install(system):
    if not confirm("git is missing. Attempt to install it now?"):
        return
    if system == "Linux" and shutil.which("apt-get"):
        run(["sudo", "apt-get", "update"])
        run(["sudo", "apt-get", "install", "-y", "git"])
    elif system == "Darwin" and shutil.which("brew"):
        run(["brew", "install", "git"])
    elif system == "Windows" and shutil.which("winget"):
        run(["winget", "install", "--id", "Git.Git", "-e"])
    else:
        print("No supported package manager found; install git manually from https://git-scm.com/downloads")


def check_linux_packages():
    if platform.system() != "Linux":
        return []
    checks = []
    missing = []
    has_dpkg = shutil.which("dpkg") is not None
    for pkg in LINUX_BUILD_PACKAGES:
        c = Check(f"apt package {pkg}")
        if has_dpkg:
            installed = subprocess.call(
                ["dpkg", "-s", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ) == 0
        else:
            installed = False
            c.message = "dpkg not found, cannot verify (non-Debian system?)"
        if installed:
            c.ok = True
            c.message = c.message or "installed"
        else:
            c.message = c.message or "not installed"
            missing.append(pkg)
        c.report()
        checks.append(c)

    if missing and has_dpkg and shutil.which("apt-get"):
        if confirm(f"Install missing apt packages ({', '.join(missing)}) now?"):
            run(["sudo", "apt-get", "update"])
            run(["sudo", "apt-get", "install", "-y"] + missing)
    return checks


def check_macos_tools():
    if platform.system() != "Darwin":
        return None
    c = Check("Xcode Command Line Tools")
    installed = subprocess.call(
        ["xcode-select", "-p"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ) == 0
    if installed:
        c.ok = True
        c.message = "installed"
    else:
        c.message = "not installed (needed to build native extensions such as hidapi)"
    c.report()
    if not installed and confirm("Install Xcode Command Line Tools now?"):
        run(["xcode-select", "--install"])
    return c


def check_windows_build_tools():
    if platform.system() != "Windows":
        return None
    c = Check("MSVC build tools")
    vswhere = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    found = False
    if shutil.which("cl"):
        found = True
        c.message = "cl.exe found on PATH"
    elif shutil.which("vswhere") or subprocess.call(
        [vswhere, "-products", "*", "-property", "installationPath"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0:
        found = True
        c.message = "Visual Studio installation detected via vswhere"
    if found:
        c.ok = True
    else:
        c.message = (
            "not detected; needed to build native extensions such as hidapi. "
            "Install 'Desktop development with C++' from Visual Studio Build Tools: "
            "https://visualstudio.microsoft.com/visual-cpp-build-tools/"
        )
    c.report()
    if not found and shutil.which("winget") and confirm(
        "Attempt to install Visual Studio Build Tools via winget now? (large download)"
    ):
        run(["winget", "install", "--id", "Microsoft.VisualStudio.2022.BuildTools", "-e"])
    return c


def main():
    system = platform.system()
    print(f"Checking prerequisites for vial-gui development on {system}...\n")

    results = [check_python_version(), check_venv_module()]

    pip_ok = check_command("pip", install_hint="run 'python -m ensurepip' or reinstall Python with pip")
    results.append(pip_ok)

    git_check = check_command(
        "git", install_hint="required because requirements.txt installs hidapi directly from a git URL"
    )
    results.append(git_check)
    if not git_check.ok:
        offer_git_install(system)

    results.extend(check_linux_packages())

    macos_check = check_macos_tools()
    if macos_check:
        results.append(macos_check)

    windows_check = check_windows_build_tools()
    if windows_check:
        results.append(windows_check)

    print()
    missing = [c for c in results if not c.ok]
    if missing:
        print(f"{len(missing)} prerequisite(s) still missing:")
        for c in missing:
            print(f"  - {c.name}: {c.message}")
        sys.exit(1)
    else:
        print("All checked prerequisites are satisfied.")
        sys.exit(0)


if __name__ == "__main__":
    main()
