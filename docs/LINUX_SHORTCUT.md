# Linux application shortcut

StatBridge can register a standard, per-user XDG desktop entry. It launches the GUI from the extracted project's local Python environment, works with regular Linux application menus and with Rofi's **drun** mode in i3wm, and requires no administrator privileges.

## Automatic registration

After downloading or cloning StatBridge and installing its Python dependencies:

```sh
./install-and-run.sh
```

On Linux, this installs or refreshes the desktop entry after a successful package installation and before launching the GUI. It does **not** change your i3wm configuration or create a keybinding. To skip automatic shortcut registration:

```sh
STATBRIDGE_NO_DESKTOP_SHORTCUT=1 ./install-and-run.sh
```

A shortcut installation failure is reported but does not prevent StatBridge itself from starting. This is an optional integration.

## Manual registration, status and removal

After the local `.venv` exists, run from the extracted source directory:

```sh
python3 tools/linux_shortcut.py install
python3 tools/linux_shortcut.py status
python3 tools/linux_shortcut.py uninstall
```

Uninstall removes the shortcut only, leaving your datasets, application files, dependencies and settings intact. The program refuses to replace or delete a desktop entry that it does not recognize as its own.

By default, the entry is written to:

```text
~/.local/share/applications/io.github.cbstatsoft.StatBridge.desktop
```

When `XDG_DATA_HOME` is an absolute path, the entry is written instead to `$XDG_DATA_HOME/applications/`. This is a per-user application menu entry, **not** a file or icon placed on the desktop background.

The shortcut uses the installed virtual environment's Python interpreter, the bundled `launch.py`, the project working directory, and the SVG icon supplied in `statbridge/assets/statbridge.svg`. It launches the Qt GUI with `Terminal=false`. The same SVG is loaded as the application's window icon and packaged with the Python distribution.

## Opening in desktop environments and i3wm

For GNOME, KDE Plasma, Xfce, Cinnamon, MATE and similar environments, search the application menu for **StatBridge**. Menu refreshes usually happen automatically, though some launchers may need to be reopened.

For i3wm with Rofi:

```sh
rofi -show drun
```

Search for **StatBridge**. Rofi `drun` discovers `.desktop` entries. The default i3wm `dmenu_run` and Rofi `run` discover commands on `PATH` instead; they do **not** use this desktop-entry listing. You can assign your own preferred launcher keybinding, but installation deliberately does not edit your window-manager configuration.

If an existing keyboard shortcut already opens Rofi `drun`, no changes are needed.

## Troubleshooting

- If the entry is absent, check `python3 tools/linux_shortcut.py status` and confirm your launcher supports XDG applications (`drun` in Rofi).
- If using a manually created Python virtual environment, ensure `.venv/bin/python` exists. The shortcut installer refuses to create an entry pointing to a missing environment.
- If you move or rename the extracted project directory, run `python3 tools/linux_shortcut.py install` again from the new location.
- If `desktop-file-validate` is installed, validate the generated file with `desktop-file-validate ~/.local/share/applications/io.github.cbstatsoft.StatBridge.desktop` (adjust for `XDG_DATA_HOME`).
- If the launcher opens but Qt reports an XCB/EGL platform-plugin error, install the missing system Qt libraries for your distribution; the desktop shortcut cannot provide system runtime libraries.
- The launcher does not install Python or Qt packages. `./install-and-run.sh` remains the supported installation path.

The implementation follows the [freedesktop Desktop Entry Specification](https://specifications.freedesktop.org/desktop-entry/latest-single/), including quoted executable paths and XDG per-user application registration.
