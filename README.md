# LubanCat 5 Ubuntu 22.04 Dual MIPI OLED

This repository records the working dual-MIPI OLED enablement for LubanCat 5 V2
on the EBF RK3588 Ubuntu SDK.

The successful screen bring-up uses the SDK source tree under
`ubuntu-ebf-rk3588` plus the extracted patch set under `update-res`.

## Contents

- `RP2040/`: RP2040 power controller files kept with the project for reference.
- `ubuntu-ebf-rk3588/`: Ubuntu SDK source tree with the working dual-MIPI OLED
  changes applied.
- `update-res/`: minimal extracted change set, preserving the original SDK paths
  for each modified file.

## Main Changes

- Enable the LubanCat 5 V2 MIPI overlay in
  `config/uEnv/lubancat-5-v2.uEnv`.
- Register the dual-MIPI OLED overlay in the Rockchip overlay `Makefile`.
- Add `rk3588-lubancat-5-v2-mipi-dsi0-oled-overlay.dts` to configure the
  dual-channel DSI0/DSI1 panel route, DPHYs, panel timing, backlight/regulator
  placeholders, and GT911 touch node.
- Raise the RK3588 VP2 display clock/output limits in
  `rockchip_vop2_reg.c` so the kernel can drive the selected panel mode.
- Patch `scripts/build-rootfs.sh` for Ubuntu 22.04 host compatibility while
  building the Ubuntu 24.04 SDK rootfs.

Build outputs are intentionally excluded:

- `ubuntu-ebf-rk3588/build/`
- `ubuntu-ebf-rk3588/images/`

## Notes

The confirmed working result does not require RP2040 power cycling during Linux
bring-up. The fix is kept focused on the Linux device tree/display path and the
host build script compatibility issue.
