# LubanCat 5 V2 Dual MIPI OLED Update

This directory contains the final files used to enable the dual-MIPI OLED panel
on LubanCat 5 V2 with the Ubuntu EBF RK3588 SDK.

## Files

- `config/uEnv/lubancat-5-v2.uEnv`
  - Enables `rk3588-lubancat-5-v2-mipi-dsi0-oled-overlay`.

- `kernel-6.1/arch/arm64/boot/dts/rockchip/overlay/Makefile`
  - Adds `rk3588-lubancat-5-v2-mipi-dsi0-oled-overlay.dtbo` to RK3588 overlay builds.

- `kernel-6.1/arch/arm64/boot/dts/rockchip/overlay/rk3588-lubancat-5-v2-mipi-dsi0-oled-overlay.dts`
  - Adds the OLED panel device tree overlay.
  - Enables dual-channel MIPI DSI through DSI0 plus DSI1.
  - Routes DSI0 through VP2.
  - Adds panel timing, DSC configuration, init sequence, dummy panel power regulator,
    dummy backlight, MIPI DCPHY nodes, and GT911 touch configuration.

- `kernel-6.1/drivers/gpu/drm/rockchip/rockchip_vop2_reg.c`
  - Raises RK3588 VP2 `dclk_max` from 600 MHz to 900 MHz.
  - Raises RK3588 VP2 `max_output` from `4096x2304` to `4096x4096`.
  - This allows the 2664x2880 OLED mode with an 855.638528 MHz pixel clock to pass
    DRM/VOP2 mode validation.

- `scripts/build-rootfs.sh`
  - Fixes chroot heredoc expansion by using quoted heredocs.
  - Ensures `check-language-support` runs inside the target arm64 rootfs instead of
    on the build host.
  - Uses `apt-get` and skips language package installation if no extra packages are
    returned.

## Result

The screen was successfully lit after applying the device tree overlay and the
RK3588 VP2 display clock/output capability fix.

RP2040 power-cycle changes were not required for the successful result.
