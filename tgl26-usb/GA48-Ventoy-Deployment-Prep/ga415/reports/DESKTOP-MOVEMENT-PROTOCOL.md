# Bounded GUI capture protocol

The SSH responsible process lacks Screen Recording access. The native tool exits
3 with `CAPTURE_PATH_UNVERIFIED`, without constructing a blank PNG. It records
CoreGraphics window bounds and display modes even when capture is unavailable.

Run `bash /private/tmp/ga415-runtime/capture-in-gui.command` in the HP's logged-in
Terminal. If macOS requests Screen Recording permission, grant it through the
normal UI and relaunch Terminal/tool as macOS requires. No TCC database editing.
Alternatively use the system screenshot keyboard shortcut and keep the original PNG.

Use only a few manual actions, one at a time, with a capture before and after:

1. Settings showing an affected sidebar: baseline.
2. Move that same window horizontally once; record old/new window bounds.
3. Scroll once, then capture; record scroll direction and approximate amount.
4. Switch away/back once to cause repaint, then capture.
5. If still necessary, minimize/restore once or briefly reveal the Dock once.

For a particular ordinary application window, find its ID in `windows.json` and
run `desktop-capture --window ID --output NEW_DIR`. This also captures the full
display. Window and display snapshots are sequential, not simultaneous.

Compare registered window-local ROIs as well as unchanged screen-coordinate
ROIs. Keep pixel scale, PNG dimensions, ICC profile and capture API with every
pair. Moving wallpaper behind transparent UI may legitimately change colors.
Do not compare raw CPU linear RGBA to color-managed screenshots as exact expected.

The current single screenshot cannot answer whether errors track windows,
scrolling content or the display. These observations remain `NOT_OBSERVED` until
paired actual images exist. Black rectangles, repeated tiles and line edges are
only candidates without an independent expected reference.
