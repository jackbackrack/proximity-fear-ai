# Badge case (slim, v1)

OpenSCAD model `badge_case.scad` (parametric; dimensions at the top). STLs in `stl/`,
renders in `preview/`.

| Part | Print orientation | Notes |
|---|---|---|
| `stl/shell.stl` | front face down | Front lip holds the 50 mm / 15 mm-hole 2 mm acrylic diffuser over a 1.0 mm spacer step that bears on the board's rim band; USB-C bump and plug opening at 6 o'clock; JST notch at 3 o'clock; lanyard tab at 12 o'clock. |
| `stl/back.stl` | outer face down | Snaps into the shell (4 bumps into a groove); bearing ring presses the board onto the spacer; JST window; plunger hole at the button. |
| `stl/plunger.stl` | flange down | Captive button pin: flange inside the back cover, pin stands 1 mm proud of the back. |

Assembly: acrylic into the shell, board face-down onto it, plunger into the back cover's
hole from the inside, back cover clicked in. Total 10.8 mm thick, ~54 mm round
(~62 mm tall including the USB bump and lanyard tab). The SWD pads are reached by
taking the back off.

Re-export after editing:

    O=/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD
    for p in shell back plunger; do $O -o stl/$p.stl -D "part=\"$p\"" badge_case.scad; done

Fit values to tune after a test print: `clr` (board/acrylic in the bore, 0.25),
`fit` in `back_cover()` (0.15), `snap_d` (0.3), `pl_hole_d` / `pl_pin_d`,
`usb_open_w` / `usb_open_h` (USB-C overmold opening, 13.4 x 7.6).
