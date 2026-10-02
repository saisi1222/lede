#!/usr/bin/env python3
"""
给 TimouL/bl-mt798x-dhcpd 的 build.sh 打补丁：强制启用 MTD 核心层。

背景（honor_fur-602 / multi_layout）：
  build.sh 第 75 行 `cp -f configs/$UBOOT_CFG .config` 会覆盖外部对 .config 的一切修改，
  紧接着第 81 行 `make olddefconfig` 会因 Kconfig 循环依赖把 CONFIG_MTD 判成 n：
      MEDIATEK_MULTI_MTD_LAYOUT=y  →  select SYS_MTDPARTS_RUNTIME  →  depends on MTD
  结果 drivers/mtd/Makefile 里 `mtd-$(CONFIG_MTD) += mtdcore.o mtd_uboot.o` 不生效，
  mtdcore/mtd_uboot/mtdpart 三个目标文件不编译，
  而 cmd/nand-ext.c、cmd/nmbm.c、drivers/mtd/nand/spi/core.c、drivers/mtd/nmbm/ 都引用
  mtd_probe_devices / mtd_read_oob / mtd_erase / add_mtd_device 等符号，
  链接阶段全部 undefined reference，ld.bfd 随后段错误 (make Error 139)。

修法：在 build.sh 的 `make -C "$UBOOT_DIR" olddefconfig` 之后，
      强制把 CONFIG_MTD=y / CONFIG_MTD_PARTITIONS=y 写回 .config 再跑一次 olddefconfig，
      并在进入 make all 之前做硬校验，不满足直接退出（早失败，省 10 分钟）。
"""
import sys

BUILD_SH = "build.sh"
ANCHOR = 'make -C "$UBOOT_DIR" olddefconfig'

INJECT = '''\
\t# === force MTD core (fix fur-602 defconfig missing -> ld Error 139) ===
\tsed -i "/^# CONFIG_MTD is not set/d; /^CONFIG_MTD=y/d; /^CONFIG_MTD_PARTITIONS=y/d" "$UBOOT_DIR/.config"
\techo "CONFIG_MTD=y" >> "$UBOOT_DIR/.config"
\techo "CONFIG_MTD_PARTITIONS=y" >> "$UBOOT_DIR/.config"
\tmake -C "$UBOOT_DIR" olddefconfig
\techo "--- MTD config after injection ---"
\tgrep -E "^CONFIG_MTD=|^CONFIG_MTD_PARTITIONS=" "$UBOOT_DIR/.config" || true
\tgrep -q "^CONFIG_MTD=y" "$UBOOT_DIR/.config" || { echo "ERROR: CONFIG_MTD injection failed"; exit 1; }
'''


def main():
    try:
        with open(BUILD_SH, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        print("ERROR: cannot read %s: %s" % (BUILD_SH, e))
        return 1

    if "force MTD core" in src:
        print("build.sh already patched (marker found)")
        return 0

    lines = src.split("\n")
    out = []
    done = False
    for line in lines:
        out.append(line)
        if not done and line.strip() == ANCHOR:
            out.append(INJECT.rstrip("\n"))
            done = True

    if not done:
        print("ERROR: anchor line not found in build.sh: %s" % ANCHOR)
        print("--- build.sh content ---")
        print(src)
        return 1

    with open(BUILD_SH, "w", encoding="utf-8") as f:
        f.write("\n".join(out))

    print("patched build.sh OK (MTD injection inserted after olddefconfig)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
