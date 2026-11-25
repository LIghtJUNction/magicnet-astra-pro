# MagicNet Astra Pro

MagicNet Astra Pro 把 Android 上的配置、启停和订阅选择交给一个 shell 入口，把网络连接交给独立的 Rust 程序 magicbox。管理页直接读取模块内的 HTML、CSS 和 JavaScript。构建模块需要 KAM，手机端运行模块不需要 KAM、kamfw、Node 或前端编译器。

## 连接

在支持 KernelSU WebUI 桥接的管理器内打开模块页面，填写自己的上游或导入订阅。客户端支持 SOCKS5、HTTP CONNECT、带证书验证的 HTTPS CONNECT，以及三种经典 AEAD 加密方式的 Shadowsocks TCP 上游。通过 SOCKS5 上游时，还支持 SOCKS5 UDP ASSOCIATE。SOCKS5 和普通 HTTP 上游使用明文链路；跨公网使用 HTTPS 上游可保护凭据和转发流量。运行后，支持代理的应用使用本机地址 `127.0.0.1:1080`。SOCKS 客户端选择远端解析，例如使用 `socks5h`。

模块自带域名拦截表。客户端把应用交付的目标域名原样发给上游，默认监听回环地址。没有有效配置时不会自动接管网络。透明 TUN、通用 UDP 数据面、蜂窝切换、旁路 VPN 和热点客户端的完整转发仍属于稳定版验收项。

~~~sh
cd /data/adb/modules/magicnet-astra-pro
./cli import /data/local/tmp/my-subscription.txt
./cli start
./cli status
./cli stop
~~~

上游地址、订阅和 age 私钥均属于私有输入。首次配置保存在模块独立的数据目录中。首次远程导入通过核心的 HTTPS 客户端和经过认证的加密 DNS 下载，已连接时可经运行中的代理下载。远程订阅允许自定义 User-Agent，age 加密订阅需要可执行的 age 解密器和私有身份文件。各格式的可执行协议以 magicbox 的导入结果为准。

## 应用和热点的 DNS 保护

`cli dns apps` 查询应用与 UID。可以限制选定应用 UID 或指定热点接口的 IPv4、IPv6 DNS 流量。此功能依赖设备内核和 xtables。配置按精确范围生效。Android 的系统解析服务、应用自带的 DoH 和隧道流量需要单独验证。

~~~sh
./cli dns apply app:com.example.reader tether:wlan1
./cli dns status
./cli dns clear
~~~

`bin/magicbox-dns-guard` 是独立的 cgroup v2 工具。在支持的 Linux 或 Android 内核，可以将它附着到专用的空子 cgroup，再把待保护进程放入其中。它限制组内 TCP/UDP 的 53 和 853 端口，进程退出时释放自有链接。内核接入边界和实测方法见核心仓库的 `docs/dns-guard.md`。

## 从源码生成一个 ABI 的 KAM ZIP

`core.lock` 指定配套 magicbox 源码提交。`rules/sources.lock.json` 固定规则来源。开发机使用 Rust、Android NDK、KAM 和 Python 标准库。安卓工具链只在构建阶段使用。下例使用已安装的 x86-64 Linux 主机 NDK 和 ARM64 Android 目标。

~~~sh
git clone https://github.com/LIghtJUNction/magicbox-core.git core
git -C core checkout --detach "$(cat core.lock)"
python3 rules/build.py --out build/rules
rustup target add aarch64-linux-android
toolchain="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin"
CC_aarch64_linux_android="$toolchain/aarch64-linux-android23-clang" \
AR_aarch64_linux_android="$toolchain/llvm-ar" \
CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER="$toolchain/aarch64-linux-android23-clang" \
cargo build --manifest-path core/Cargo.toml --release --locked --target aarch64-linux-android
python3 scripts/package.py --abi arm64-v8a --binary core/target/aarch64-linux-android/release/magicbox \
  --rules build/rules --out dist/magicnet-arm64-v8a.zip
~~~

打包器检查 ELF 架构、模块元数据、清单和每个归档成员的内容。规则、原生二进制和 ZIP 作为构建产物分发。规则目录可通过 `--all` 另行生成可复用分类对象。默认安装只带生效的拦截表及其许可证。

## 增量更新

有旧 ZIP 时，发布者可以生成针对该版本的差分。安装者从可信发布渠道取得新 ZIP 的 SHA-256，使用 shell 重建同一份 KAM 文件。旧包或补丁不匹配时，命令保留原有目标文件。重建后的 ZIP 可交给模块管理器。

~~~sh
python3 scripts/delta.py old.zip new.zip change.zip
./cli patch old.zip change.zip rebuilt.zip EXPECTED_NEW_ZIP_SHA256
~~~

## 验收与许可

候选工作流覆盖 Linux、真实 Rust 核心、WebUI 和安卓模拟器。工作流文件和单轮本地结果分别记录。稳定版的替换条件及缺口见 [验收记录](docs/acceptance.md)。

程序采用 MIT 许可。内置域名表随包提供 HaGeZi 来源说明和 GPL 许可文本。可选规则目录保留其各自的上游信息。
