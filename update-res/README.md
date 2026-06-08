# LubanCat 5 V2 双路 MIPI OLED 修改文件说明

这个目录保存的是本次成功点亮屏幕所需的最小修改文件集合。文件路径按照
`ubuntu-ebf-rk3588` SDK 内的原始路径保留，便于直接对照、复制或移植到其他 SDK。

## 文件列表

- `config/uEnv/lubancat-5-v2.uEnv`
  - 启用 `rk3588-lubancat-5-v2-mipi-dsi0-oled-overlay`。

- `kernel-6.1/arch/arm64/boot/dts/rockchip/overlay/Makefile`
  - 将 `rk3588-lubancat-5-v2-mipi-dsi0-oled-overlay.dtbo` 加入 RK3588 overlay 编译列表。

- `kernel-6.1/arch/arm64/boot/dts/rockchip/overlay/rk3588-lubancat-5-v2-mipi-dsi0-oled-overlay.dts`
  - 新增 OLED 屏幕设备树 overlay。
  - 启用 DSI0 + DSI1 双通道 MIPI 输出。
  - 将显示链路配置为 VP2 输出到 DSI0。
  - 配置 panel timing、DSC、初始化序列、dummy panel power regulator、dummy backlight、
    MIPI DCPHY 节点和 GT911 触摸节点。

- `kernel-6.1/drivers/gpu/drm/rockchip/rockchip_vop2_reg.c`
  - 将 RK3588 VP2 的 `dclk_max` 从 600 MHz 提高到 900 MHz。
  - 将 RK3588 VP2 的 `max_output` 从 `4096x2304` 提高到 `4096x4096`。
  - 目的是让 2664x2880 OLED 模式和 855.638528 MHz 像素时钟通过 DRM/VOP2 校验。

- `scripts/build-rootfs.sh`
  - 修复 Ubuntu 22.04 宿主机构建 Ubuntu 24.04 rootfs 时的 chroot heredoc 展开问题。
  - 让 `check-language-support` 在目标 arm64 rootfs 内执行，而不是在宿主机提前执行。
  - 没有额外语言包时跳过安装，避免空参数或宿主机环境差异导致构建失败。

## 使用方式

这些文件已经应用在仓库中的 `ubuntu-ebf-rk3588/` SDK 源码树内。若要移植到其他同类 SDK，
可以按本目录中的相对路径覆盖对应文件，然后重新构建镜像。

## 结果

应用这些修改后，LubanCat 5 V2 的双路 MIPI OLED 屏幕已经成功点亮。

本次成功方案不依赖 RP2040 在 Linux 阶段重新上电，重点修复的是 Linux 设备树、
显示路由和 RK3588 VOP2 显示能力校验。
