# Manager GUI Guide

Walltext includes a fully-featured graphical desktop manager. 

## Launching the Manager
You can launch the manager from your terminal via:
```powershell
walltext manager
```
Or by double-clicking the generated `walltext_manager.bat` helper.

## Interface Overviews

### List Mode
Allows you to build your rotation playlist for wallpapers.
- **Move Up / Down**: Reorder sequence priority.
- **Duplicate & Remove**: Manage the rotation items.
- **Import / Export**: Move configurations between machines using JSON or TXT formats.
- **Scheduler**: Allows setting intervals (e.g. `Every 30 Minutes`) or daily clocks (`Once Per Day at 09:00`) for auto-rotation.

### Markdown Mode
An integrated text editor specialized for designing Walltext Markdown files.
- **Live Previewing**: Analyzes syntax to show block counts and properties.
- **Native Toolbar**: Insert tags like bold, headers, colors (`🎨`), and quotes at the click of a button.
- **Render & Apply**: Test changes to the wallpaper cleanly without touching rotation configuration.

## Actions
The GUI has simple buttons for stopping and starting the background listener services or setting the listener up to run silently the moment you log onto your Windows machine.
