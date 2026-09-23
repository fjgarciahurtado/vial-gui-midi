### vial-gui

# Docs and getting started

### Please visit [get.vial.today](https://get.vial.today/) to get started with Vial

Vial is an open-source cross-platform (Windows, Linux and Mac) GUI and a QMK fork for configuring your keyboard in real time.


![](https://get.vial.today/img/vial-win-1.png)


---


#### Releases

Visit https://get.vial.today/ to download a binary release of Vial.

#### Development

##### Prerequisites

Python 3.6 is recommended (3.6 is the latest version that is officially supported by `fbs`).
You will also need:

- `pip` and the standard library `venv` module.
- `git` (dependencies are installed directly from a git URL).
- A C build toolchain, since `pip install` compiles the `hidapi` native extension:
  - Linux: `build-essential`, `libusb-1.0-0-dev`, `libudev-dev`.
  - macOS: Xcode Command Line Tools.
  - Windows: Visual Studio Build Tools ("Desktop development with C++").

Run the helper script below to check for these and optionally install anything missing
(it will always ask for confirmation before installing or running any command):

```
python util/check_prerequisites.py
```

##### Setup and running

Install dependencies:

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

To launch the application afterwards:

```
source venv/bin/activate
fbs run
```
