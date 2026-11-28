// Proximity Fear Badge - slim case (front shell + back cover + button plunger).
//
// Frame: board coordinates as seen from the FRONT (x right, y up, origin = board
// centre, from proximity_fear/designs/badge.py); z = 0 at the board's front face,
// +z toward the wearer's front. Everything except the LEDs, ToF and IR parts is on the
// board's back.
//
// Stack, front to back:
//   front lip (covers the acrylic's outer 1 mm)           z  +4.0 .. +3.0
//   acrylic diffuser ring, OD 50 / ID 15, 2 mm             z  +3.0 .. +1.0
//   spacer step on the board's 1 mm rim keep-out band     z  +1.0 ..  0   (LEDs 0.84 tall)
//   PCB 1.6 mm                                            z   0   .. -1.6
//   back parts (nRF module 3.0, USB-C 3.26)               z  -1.6 .. -5.2
//   back cover 1.6 mm (JST window, button plunger hole)    z  -5.2 .. -6.8
// Total thickness 10.8 mm. The JST header (5.4 mm) pokes 0.2 mm through its window;
// the battery plug goes in through that window / the 3 o'clock wall notch.
//
// Print: shell front-face down, back cover outer-face down, plunger flange down;
// PETG or PLA, 0.2 mm layers, no supports.
//
// part = "shell" | "back" | "plunger" | "assembly" | "section"
part = "assembly";

$fn = 128;

// ---- Board (proximity_fear/designs/badge.py, main.py) --------------------------------
board_r   = 25.0;     // 50 mm circle
board_t   = 1.6;      // JLC04161H 4-layer 1.6 mm
tab_w     = 12.0;     // USB-C tab at 6 o'clock
tab_y     = -29.14;   // tab edge (4.14 mm proud of the circle)
rim_band  = 1.0;      // copper keep-out band at the edge, for the case to bear on

// Parts that the case must clear or open onto (board coordinates).
usb_xy    = [0, -25.2];   usb_h = 3.26;   usb_mouth_z = -board_t - 1.63;  // TYPE-C-31-M-12
jst_box   = [[13.9, -4.35], [23.6, 4.35]];  jst_h = 5.4;  // SHOU HAN 2.0-2P WT, mates toward +x
sw_xy     = [-20.2, 0];   sw_h = 1.5;     sw_travel = 0.25;                 // TS-1187A, on the back
mod_box   = [[-7.75, 1.43], [7.75, 23.68]];  mod_h = 3.0;                    // E73 module

// ---- Diffuser -----------------------------------------------------------------------
acr_t     = 2.0;
acr_od    = 50.0;
acr_id    = 15.0;
led_h     = 0.84;

// ---- Case ---------------------------------------------------------------------------
clr       = 0.25;              // radial clearance board/acrylic to bore
wall      = 1.6;
lip_t     = 1.0;
lip_cover = 1.0;               // how far the lip overlaps the acrylic edge
spacer_h  = 1.0;               // acrylic sits 0.16 mm above the LED tops
back_gap  = 3.6;               // board back to back-cover inner face
back_t    = 1.6;

r_in      = board_r + clr;     // bore
r_out     = r_in + wall;
z_front   = spacer_h + acr_t + lip_t;          // +4.0
z_back_in = -board_t - back_gap;               // -5.2
z_back    = z_back_in - back_t;                // -6.8

// USB-C bump around the tab, and the plug opening (overmold ~12.4 x 6.5 mm).
bump_hw   = 7.2;                                // inner half-width
bump_y_in = tab_y - clr;                        // inner bottom
usb_open_w = 13.4;
usb_open_h = 7.6;                               // centred on the receptacle mouth

// JST access: window in the back cover + notch in the 3 o'clock wall.
jst_win_hw = 5.0;
jst_win_x0 = 13.5;

// Button plunger.
pl_hole_d   = 3.3;
pl_pin_d    = 2.9;
pl_flange_d = 5.0;
pl_flange_t = 0.8;
pl_proud    = 1.0;              // how far the pin stands out of the back cover

// Back cover retention: 4 small bumps that click into a groove in the shell bore.
snap_d      = 0.3;
snap_z      = z_back_in - back_t / 2;

// Lanyard tab at 12 o'clock, flush with the front face (prints on the bed).
lan_w = 9;  lan_len = 6;  lan_t = 3;  lan_hole = 3.6;

// ---- 2D outlines --------------------------------------------------------------------
module outline(r, hw, ybot) {          // circle plus the USB-C bump
  union() {
    circle(r = r);
    translate([-hw, ybot]) square([2 * hw, -ybot]);
  }
}
module bore2d()  { outline(r_in, bump_hw, bump_y_in); }
module outer2d() { outline(r_out, bump_hw + wall, bump_y_in - wall); }

// ---- Shell ---------------------------------------------------------------------------
module shell() {
  difference() {
    union() {
      translate([0, 0, z_back]) linear_extrude(z_front - z_back) outer2d();
      lanyard_tab();
    }
    // Bore from the back up to the acrylic's front face.
    translate([0, 0, z_back - 1]) linear_extrude(spacer_h + acr_t + 1 - z_back) bore2d();
    // Front window: the lip leaves the acrylic open inside r = acrylic edge - lip_cover.
    translate([0, 0, spacer_h + acr_t - 0.01]) cylinder(r = acr_od / 2 - lip_cover, h = lip_t + 1);
    // USB-C plug opening through the bump's bottom wall (open to the back).
    translate([-usb_open_w / 2, bump_y_in - wall - 1, z_back - 1])
      cube([usb_open_w, wall + 2, (usb_mouth_z + usb_open_h / 2) - z_back + 1]);
    // JST notch in the 3 o'clock wall, from the board's back face to the back edge.
    translate([r_in - 1, -jst_win_hw, z_back - 1]) cube([wall + 2, 2 * jst_win_hw, -board_t - z_back + 1]);
    // Snap groove for the back cover.
    translate([0, 0, snap_z - 0.6]) difference() {
      cylinder(r = r_in + snap_d + 0.1, h = 1.2);
      translate([0, 0, -1]) cylinder(r = r_in - 1, h = 3.4);
    }
  }
  // Spacer step on the rim band: the board bears on its back, the acrylic on its front.
  difference() {
    linear_extrude(spacer_h) bore2d();
    translate([0, 0, -1]) cylinder(r = board_r - rim_band + 0.1, h = spacer_h + 2);
    // keep the tab region open in front of the USB-C (nothing to bear on there)
    translate([-bump_hw - 1, bump_y_in - 1, -1]) cube([2 * bump_hw + 2, -bump_y_in - board_r + rim_band + 1.5, spacer_h + 2]);
  }
}

module lanyard_tab() {
  translate([0, 0, z_front - lan_t]) difference() {
    hull() {
      translate([-lan_w / 2, r_out - 2, 0]) cube([lan_w, 1, lan_t]);
      translate([0, r_out + lan_len - lan_w / 2, 0]) cylinder(d = lan_w, h = lan_t);
    }
    translate([0, r_out + lan_len - lan_w / 2, -1]) cylinder(d = lan_hole, h = lan_t + 2);
  }
}

// ---- Back cover ----------------------------------------------------------------------
module back_cover() {
  fit = 0.15;  // radial clearance in the bore
  difference() {
    union() {
      // Plate.
      translate([0, 0, z_back]) linear_extrude(back_t) offset(delta = -fit) bore2d();
      // Bearing ring on the rim band, pressing the board against the spacer step.
      intersection() {
        translate([0, 0, z_back_in]) linear_extrude(back_gap) difference() {
          circle(r = r_in - fit);
          circle(r = board_r - rim_band + 0.1);
        }
        // not where the JST plug or the USB-C tab are
        translate([0, 0, z_back_in - 1]) linear_extrude(back_gap + 2) difference() {
          circle(r = r_out + 5);
          translate([jst_win_x0 - 2, -jst_win_hw - 1]) square([20, 2 * jst_win_hw + 2]);
          translate([-bump_hw - 1, -40]) square([2 * bump_hw + 2, 40 - board_r + rim_band + 1]);
        }
      }
      // Snap bumps at 45 / 135 / 225 / 315 deg.
      for (a = [45, 135, 225, 315]) rotate(a)
        translate([r_in - fit - 0.2, -2.5, snap_z - 0.35]) cube([0.2 + snap_d, 5, 0.7]);
    }
    // JST window (open to the 3 o'clock edge).
    translate([jst_win_x0, -jst_win_hw, z_back - 1]) cube([20, 2 * jst_win_hw, back_t + back_gap + 2]);
    // Plunger hole.
    translate([sw_xy[0], sw_xy[1], z_back - 1]) cylinder(d = pl_hole_d, h = back_t + 2);
    // USB-C plug clearance where the plate meets the bump.
    translate([-usb_open_w / 2, bump_y_in - 2, z_back - 1]) cube([usb_open_w, 2.5, back_t + 2]);
  }
}

// ---- Plunger (captive: flange inside the cover, pin through it onto the button) ------
module plunger() {
  sw_top = -board_t - sw_h;                 // actuator top (z)
  nub_len = (sw_top - 0.1) - (z_back_in + pl_flange_t);   // flange to 0.1 mm short of the button
  pin_len = back_t + pl_proud;
  // modelled in place; printed flange-down (see plunger_print)
  translate([sw_xy[0], sw_xy[1], 0]) {
    translate([0, 0, z_back - pl_proud]) cylinder(d = pl_pin_d, h = pin_len);
    translate([0, 0, z_back_in]) cylinder(d = pl_flange_d, h = pl_flange_t);
    translate([0, 0, z_back_in + pl_flange_t]) cylinder(d = 2.0, h = nub_len);
  }
}
module plunger_print() {
  translate([-sw_xy[0], -sw_xy[1], -z_back_in]) plunger();
}

// ---- Reference models (assembly preview only) ----------------------------------------
module board_ref() {
  color("darkgreen") translate([0, 0, -board_t]) linear_extrude(board_t) union() {
    circle(r = board_r);
    translate([-tab_w / 2, tab_y]) square([tab_w, -tab_y]);
  }
  color("silver") translate([usb_xy[0] - 4.47, -29.0, -board_t - usb_h]) cube([8.94, 7.35, usb_h]);
  color("white") translate([jst_box[0][0], jst_box[0][1], -board_t - jst_h])
    cube([jst_box[1][0] - jst_box[0][0], jst_box[1][1] - jst_box[0][1], jst_h]);
  color("dimgray") translate([sw_xy[0] - 2.55, sw_xy[1] - 2.55, -board_t - sw_h]) cube([5.1, 5.1, sw_h]);
  color("steelblue") translate([mod_box[0][0], mod_box[0][1], -board_t - mod_h])
    cube([mod_box[1][0] - mod_box[0][0], mod_box[1][1] - mod_box[0][1], mod_h]);
  // LED rings (10 / 16 / 24 on r 9.5 / 15.5 / 21.5)
  for (ring = [[9.5, 10, 90], [15.5, 16, 62.8], [21.5, 24, 34.5]])
    for (k = [0 : ring[1] - 1]) rotate(ring[2] + 360 * k / ring[1])
      color("gold") translate([ring[0] - 1.1, -1.0, 0]) cube([2.2, 2.0, led_h]);
  color("black") translate([-4.5 - 2.0, -2.5, 0]) cube([4.0, 5.0, 2.5]);   // IR receiver
  color("black") translate([-2.2, -1.2, 0]) cube([4.4, 2.4, 1.0]);         // ToF
}
module acrylic_ref() {
  color("white", 0.45) translate([0, 0, spacer_h]) difference() {
    cylinder(d = acr_od, h = acr_t);
    translate([0, 0, -1]) cylinder(d = acr_id, h = acr_t + 2);
  }
}

// ---- Output --------------------------------------------------------------------------
if (part == "shell") shell();
else if (part == "back") translate([0, 0, -z_back]) back_cover();
else if (part == "plunger") plunger_print();
else if (part == "assembly") {
  color("orange", 0.55) shell();
  color("orange") back_cover();
  color("red") plunger();
  board_ref();
  acrylic_ref();
}
else if (part == "section") {          // cut along y = 0 (through button, ToF and JST)
  intersection() {
    union() {
      color("orange") shell();
      color("darkorange") back_cover();
      color("red") plunger();
      board_ref();
      acrylic_ref();
    }
    translate([-40, -40, -20]) cube([80, 40, 40]);
  }
}
