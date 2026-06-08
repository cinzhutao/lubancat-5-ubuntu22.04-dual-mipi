# LubanCat 5 Ubuntu 22.04 双路 MIPI OLED 点屏记录

这个仓库保存了 LubanCat 5 V2 在野火 EBF RK3588 Ubuntu SDK 上成功点亮双路
MIPI OLED 屏幕的完整源码树和最小修改集。

本次成功点亮的核心不是重新给 RP2040 上电，而是修正 Linux 内核接手后的显示链路：
设备树启用 DSI0 + DSI1 双通道 MIPI，显示路由走 VP2，同时放宽 RK3588 VP2 的显示时钟
和输出尺寸校验。

## 目录说明

- `RP2040/`
  - 转接板 RP2040 供电控制程序，保留在仓库中用于追溯和参考。

- `ubuntu-ebf-rk3588/`
  - 已经应用成功点屏修改的 Ubuntu SDK 源码树。

- `update-res/`
  - 从 SDK 中抽取出来的最小修改文件集合，保留原始路径，便于对照、移植和复用。

## 主要修改

- `ubuntu-ebf-rk3588/config/uEnv/lubancat-5-v2.uEnv`
  - 启用 `rk3588-lubancat-5-v2-mipi-dsi0-oled-overlay`。

- `ubuntu-ebf-rk3588/kernel-6.1/arch/arm64/boot/dts/rockchip/overlay/Makefile`
  - 将双路 MIPI OLED overlay 加入 RK3588 overlay 编译列表。

- `ubuntu-ebf-rk3588/kernel-6.1/arch/arm64/boot/dts/rockchip/overlay/rk3588-lubancat-5-v2-mipi-dsi0-oled-overlay.dts`
  - 配置 DSI0 + DSI1 双通道 MIPI。
  - 配置 DSI0 走 VP2 输出路由。
  - 配置 panel timing、DSC、初始化序列、dummy regulator、dummy backlight、MIPI DCPHY 和 GT911 触摸节点。

- `ubuntu-ebf-rk3588/kernel-6.1/drivers/gpu/drm/rockchip/rockchip_vop2_reg.c`
  - 将 RK3588 VP2 的 `dclk_max` 从 600 MHz 提高到 900 MHz。
  - 将 RK3588 VP2 的 `max_output` 从 `4096x2304` 提高到 `4096x4096`。
  - 这样 2664x2880 OLED 模式及 855.638528 MHz 像素时钟可以通过 DRM/VOP2 模式校验。

- `ubuntu-ebf-rk3588/scripts/build-rootfs.sh`
  - 修复 Ubuntu 22.04 宿主机构建 Ubuntu 24.04 rootfs 时的兼容问题。
  - 使用带引号 heredoc，避免宿主机提前展开 chroot 内部命令。
  - 让 `check-language-support` 在目标 arm64 rootfs 内执行，并在没有额外语言包时跳过安装。

## 构建方法

进入 SDK 目录后构建：

```bash
cd /home/zhutao/mipi/lubancat-5-ubuntu22.04-dual-mipi/ubuntu-ebf-rk3588
```

常用构建命令示例：

```bash
./build.sh lunch
```

选择 LubanCat 5 V2 对应配置后执行完整镜像构建：

```bash
./build.sh
```

如果只需要重新构建设备树/内核相关产物，可按 SDK 菜单或脚本支持的模块化命令执行。
不同 SDK 版本的模块命令可能略有差异，以当前 `./build.sh` 菜单输出为准。

## 不提交的构建产物

以下目录是构建产物，已通过 `.gitignore` 排除：

- `ubuntu-ebf-rk3588/build/`
- `ubuntu-ebf-rk3588/images/`

## 点屏结论

应用当前设备树 overlay 和 RK3588 VP2 显示能力修正后，屏幕已经成功点亮。

RP2040 重新上电流程不是本次成功点亮的必要条件，当前方案重点保留 Linux 设备树、
显示路由和内核 DRM/VOP2 校验相关修改。
