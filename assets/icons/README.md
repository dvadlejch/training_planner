# App icon designs

Original geometric artwork, maintained as editable SVG sources. Colors echo the
app's forest, cream and sage interface; gold adds an outdoor accent. No external
fonts, stock artwork or image-generation service are used for the icons.

| Summit Calendar (default) | Training Pulse | Progress Trail |
| --- | --- | --- |
| ![Summit Calendar](summit-calendar.png) | ![Training Pulse](training-pulse.png) | ![Progress Trail](progress-trail.png) |
| A calendar and mountain ridge: planning plus outdoor endurance. | A warm coral pulse: energy and varied training. | Teal ascending steps with a gold destination: steady progress. |

Each design includes an SVG, a 256px PNG preview, and a Windows ICO containing
16, 20, 24, 32, 40, 48, 64, 128 and 256px frames with transparent corners.

Summit Calendar is used by PyInstaller for the application executable (and hence
its shortcuts), Inno Setup for Setup/Uninstall, and the browser favicon.
Shortcuts explicitly select the first icon embedded in the installed executable.
After successful installation, Setup notifies the Windows Shell to refresh its
icon cache, so upgrades at the same executable path can show updated artwork.
`installer-panel.png` is a matching 492 x 942 welcome/completion panel. The wizard
also displays the square icon in its header. Welcome is explicitly enabled so the
branding is visible during interactive installation. Silent installation is unchanged.

Regenerate the committed exports after editing the SVGs, on Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-icon-assets.ps1
```

This uses Windows .NET System.Drawing, with no new package dependencies. The small
renderer supports the rect, circle and polyline elements used by these sources;
it fails on other element types. Keep fills and strokes explicit on each shape.
It also refreshes `frontend/public/favicon.svg` from the default SVG. Normal builds
consume the committed exports and do not need to regenerate them.

To adopt another design, change the icon paths in `scripts/build-windows.ps1` and
`installer/windows.iss`, and update the selected design for the panel and favicon
in `scripts/build-icon-assets.ps1`, then regenerate and rebuild the installer.

![Installer welcome and completion panel](installer-panel.png)
