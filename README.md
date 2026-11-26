# MagicNet Astra Pro

MagicNet Astra Pro 把 Android 上的配置、启停和订阅选择交给一个 shell 入口，把网络连接交给独立的 Rust 程序 magicbox。管理页直接读取模块内的 HTML、CSS 和 JavaScript。构建模块需要 KAM，手机端运行模块不需要 KAM、kamfw、Node 或前端编译器。

## 连接

在支持 KernelSU WebUI 桥接的管理器内打开模块页面，填写自己的上游或导入订阅。客户端支持 SOCKS5、HTTP CONNECT、带证书验证的 HTTPS CONNECT，以及三种经典 AEAD 加密方式的 Shadowsocks TCP 上游。通过 SOCKS5 上游时，还支持 SOCKS5 UDP ASSOCIATE。SOCKS5 和普通 HTTP 上游使用明文链路；跨公网使用 HTTPS 上游可保护凭据和转发流量。支持 SOCKS5 或 HTTP CONNECT 的客户端也可以直接连接 `127.0.0.1:1080`，通过 `socks5h` 保留域名并让上游解析。

首次安装默认选择 TUN。配置可用上游并启动后，Android 用策略路由把本机应用 UID（10000 起）的 IPv4 和 IPv6 包交给虚拟接口 `magicnet0`。包内的 hev-socks5-tunnel 将 TCP 流和 UDP 数据报交给本机 magicbox，再由 magicbox 连接所选上游。核心及转发器以 root 身份建立连接，使用设备原有路由。UDP 需要支持 UDP ASSOCIATE 的 SOCKS5 上游。系统服务代应用发起的 DNS 查询和热点转发流量有各自的控制路径。

在 WebUI 的「网络模式」或用 `cli mode tun`、`cli mode local` 选择模式。已有上游配置的旧安装升级后沿用本机转发模式，用户可以显式切换。用 `cli mode` 查看选择，`cli status` 中的 `configured_mode` 与 `effective_mode` 分别表示配置和实际运行状态。TUN 数据面的 IP 包携带目标地址；域名拦截表适用于把域名交给本机 SOCKS 入口的请求。

~~~sh
cd /data/adb/modules/magicnet-astra-pro
./cli import /data/local/tmp/my-subscription.txt
./cli start
./cli status
./cli stop
~~~

上游地址、订阅和 age 私钥均属于私有输入。首次配置保存在模块独立的数据目录中。首次远程导入通过核心的 HTTPS 客户端和经过认证的加密 DNS 下载，已连接时可经已启动的转发服务下载。远程订阅允许自定义 User-Agent，age 加密订阅需要可执行的 age 解密器和私有身份文件。各格式的可执行协议以 magicbox 的导入结果为准。

### 自定义模块使用的加密 DNS

如果当前网络无法连接默认解析器，可在 root shell 中为这次安装指定一个可达的 DNS-over-TLS 服务。请将示例中的保留地址和证书名替换为服务商公布并经你验证的值。

~~~sh
umask 077
dir=/data/adb/magicnet-astra-pro
mkdir -p "$dir" && chmod 700 "$dir"
printf '%s\n' 'tls://192.0.2.53:853?server_name=resolver.example' > "$dir/resolver.new" &&
    chmod 600 "$dir/resolver.new" && mv "$dir/resolver.new" "$dir/resolver"
~~~

`resolver` 只存一行，IPv6 地址用方括号包围。文件应由 root 拥有，权限为 600 或 400。使用自定义 `MAGICNET_STATE_DIR` 时文件位于该目录。CLI 优先采用调用进程显式传入的 `MAGICBOX_RESOLVER`，其次读取此文件。两者都未设置时使用核心默认值。修改文件后，重启服务使新设置生效。删除文件并重启可恢复默认。

WebUI、命令行和开机服务共用这个入口。它控制首次获取 HTTPS 订阅及域名节点启动时的 DNS 查询。通过运行中的服务获取订阅时，由上游解析目的域名。选择的 DoT 服务可以看到交给它的名称。核心验证 TLS 证书，解析失败时终止操作。Android 系统与其他应用保留各自的 DNS 设置。

## 按应用或热点转发 TCP

启动上游后，在管理页展开“应用与热点分流”，选中应用包名或填写热点的实际接口名。共享 UID 的包会显示在同一项中。应用通过蜂窝或 Wi-Fi 发起的新公网 TCP 连接，以及指定热点接口进入的新公网 TCP 连接，都会交给 magicbox。也可使用 shell 一次替换整个选择。

~~~sh
./cli start
./cli traffic apps
./cli traffic apply app:com.example.reader tether:wlan1
./cli traffic status
./cli traffic clear
~~~

内核通过连接跟踪保存连接原本要去的 IP 和端口，magicbox 按此地址与上游建立连接。SOCKS5 或 HTTP CONNECT 客户端可以转交域名。透明 TCP 只收到目标 IP，需按域名过滤的应用应使用本机 SOCKS5 的远端解析。IPv4 与 IPv6 都有 NAT 时，状态显示 `dual-stack-redirect`。只有 IPv4 NAT 的内核显示 `ipv4-redirect-ipv6-block`。此时 IPv4 由 magicbox 转发，选中范围的 IPv6 公网 TCP 由过滤表丢弃。IPv6 过滤表也不可用时启用操作失败。

分流自动阻止选中 UID 和热点客户的 TCP/UDP 53、853。系统解析器代应用发起的查询归系统 UID，需独立验证。常规 UDP、QUIC、已有连接和未选应用沿用原有路径。magicbox 进程使用 root UID。规则保留本地、私有、常见覆盖网地址及已有 NAT 规则的优先级。显式 IP 上游可在防火墙中直接绕过；域名上游由核心安全解析并检查启动时固定的对端地址。应用流量在常见 VPN 隧道接口上继续使用原有路由。热点入口在路由选择前处理。模块读取内核本地路由表以保留分配给本机的地址，接口地址变化后可执行 `cli traffic sync` 刷新。任意自定义 VPN 公网分流策略仍需单独验收。

Android 执行模块的 `service.sh` 后，模块先恢复已启用范围的 DNS 过滤，再解析上游和启动转发服务。上游启动失败时，已恢复的过滤继续生效。更早的开机阶段取决于管理器的启动时机。

`stop` 暂停转发并保留选择，下一次启动恢复。 `traffic clear` 清除分流以及与之配套的 DNS 规则。独立配置的 `dns apply` 规则继续生效。

## 应用和热点的 DNS 保护

`cli dns apps` 查询应用与 UID。可以限制选定应用 UID 或指定热点接口的 IPv4、IPv6 DNS 流量。此功能依赖设备内核和 xtables。配置按精确范围生效。Android 的系统解析服务、应用自带的 DoH 和隧道流量需要单独验证。

~~~sh
./cli dns apply app:com.example.reader tether:wlan1
./cli dns status
./cli dns clear
~~~

`bin/magicbox-dns-guard` 是独立的 cgroup v2 工具。在支持的 Linux 或 Android 内核，可以将它附着到专用的空子 cgroup，再把待保护进程放入其中。它限制组内 TCP/UDP 的 53 和 853 端口，进程退出时释放自有链接。内核接入边界和实测方法见核心仓库的 `docs/dns-guard.md`。

## 从源码生成一个 ABI 的 KAM ZIP

`core.lock` 指定配套 magicbox 源码提交，`tun.lock` 固定 hev-socks5-tunnel 及其 Git 子模块所用的源码版本。`rules/sources.lock.json` 固定规则来源。开发机使用 Rust、Android NDK、KAM 和 Python 标准库。安卓工具链只在构建阶段使用。下例使用已安装的 x86-64 Linux 主机 NDK 和 ARM64 Android 目标。

~~~sh
git clone https://github.com/LIghtJUNction/magicbox.git core
git -C core checkout --detach "$(cat core.lock)"
python3 rules/build.py --out build/rules
rustup target add aarch64-linux-android
toolchain="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin"
CC_aarch64_linux_android="$toolchain/aarch64-linux-android23-clang" \
AR_aarch64_linux_android="$toolchain/llvm-ar" \
CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER="$toolchain/aarch64-linux-android23-clang" \
cargo build --manifest-path core/Cargo.toml --release --locked --target aarch64-linux-android
sh scripts/build-tun.sh android
python3 scripts/package.py --abi arm64-v8a --binary core/target/aarch64-linux-android/release/magicbox \
  --rules build/rules --out dist/magicnet-arm64-v8a.zip
~~~

打包器检查 ELF 架构、模块元数据、清单和每个归档成员的内容。规则、原生二进制和 ZIP 作为构建产物分发。规则目录可通过 `--all` 另行生成可复用分类对象。默认安装只带生效的拦截表及其许可证。

## 在 Linux 验证默认 TUN

在已检出 `core.lock` 指定核心的模块目录执行以下命令。测试在新建的网络命名空间中以应用 UID 发送数据，本机 SOCKS5 测试上游返回响应。需要可用的 `/dev/net/tun`、iproute2 和创建网络命名空间的权限。

~~~sh
cargo build --manifest-path core/Cargo.toml --locked --release --target-dir build/host
sh scripts/build-tun.sh linux
sudo python3 tests/tun-netns.py build/host/release/magicbox build/tun/jni/bin/hev-socks5-tunnel
~~~

## 增量更新

有旧 ZIP 时，发布者可以生成针对该版本的差分。安装者从可信发布渠道取得新 ZIP 的 SHA-256，使用 shell 重建同一份 KAM 文件。旧包或补丁不匹配时，命令保留原有目标文件。重建后的 ZIP 可交给模块管理器。

~~~sh
python3 scripts/delta.py old.zip new.zip change.zip
./cli patch old.zip change.zip rebuilt.zip EXPECTED_NEW_ZIP_SHA256
~~~

## 验收与许可

候选工作流覆盖 Linux、真实 Rust 核心、WebUI 和安卓模拟器。工作流文件和单轮本地结果分别记录。稳定版的替换条件及缺口见 [验收记录](docs/acceptance.md)。

模块程序采用 MIT 许可。安装包随 TUN 转发器附带各组件的许可文本。内置域名表随包提供 HaGeZi 来源说明和 GPL 许可文本。可选规则目录保留其各自的上游信息。
