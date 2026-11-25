# 重建验收记录

基线为 MagicNet v1.9.3 的公开产品行为清单。只依据外部可观察行为设计与比较。下列编号用于回溯原要求。原行包括多个成功和故障分支，只有全部有证据时才能将该项标为通过。[固定基线](https://github.com/LIghtJUNction/MagicNet/blob/ef24ce30de68f6e46d99f6c54736c004b372c71f/recipes/magicnet/ACCEPTANCE.md)

## 可验证的实现

| 环境 | 已完成的测量 | 适用边界 |
| --- | --- | --- |
| Linux 主机 | Rust lint、单元、黑盒 TCP、HTTPS 引导、DoT、三个 SOCKS5 UDP 用例组 | 显式使用代理的应用。UDP 通过 SOCKS5 上游，带域名的数据报要求应用保留域名 |
| Linux 虚拟机 | 以 Debian shadowsocks-libev 为对端，三个 SIP004 AEAD 方法，双入口、传输、错误密码 | 支持 TCP 客户端。连接阶段没有来自 Shadowsocks 服务器的目标成功回执 |
| Linux 网络命名空间 | TCP/UDP 与 IPv4/IPv6，DNS 端口与对照端口，其他 UID 隔离、故障回滚；经虚拟热点接口转发 | 验证内核规则的效果，全设备流量路径仍需端到端验证 |
| Linux cgroup v2 | 独立内核 eBPF 守卫，144 个套接字结果，正常与异常退出、自有链接清理 | 单独 cgroup 及其后代。53 和 853 的控制范围不包含应用自定义 DoH |
| Android 6 API 23 x86_64 | 在实际 Android 来宾运行 KAM、BusyBox、模块和较早的核心；真实 TLS 1.3 上游，SOCKS5/HTTP CONNECT 各 256 KiB 回显；规则命中、重复应用、坏配置和五轮启停。另测 Android 防火墙 | KAM 包 SHA-256 为 `0a2d09c139f915151c72172118205b995cce70971cb4fca5e749a9aea2d53ad8`。只将这些证据归于当时构建。Android 用户空间服务精简运行，未加载真实手机管理器 |
| Chromium | 320、390、768、1280 像素宽，三种语言，真实 DOM，模拟 KernelSU 调用接口 | Android 实机管理器、TalkBack 与软键盘仍需独立测试 |
| Unix / Android 交付 | shell CLI，原生 Web 文件，单 ABI KAM 打包与文件核对。ZIP 差分重建需可信目标 SHA-256 | 自动在线升级、旧版状态迁移和新项目 GitHub Actions 均有独立验收条件 |
| 性能 | 两个二进制各七个进程，记录 RSS、吞吐和往返分位数 | 早期核心、单 TCP 回环负载、无外部规则，详细条件见核心源树 docs/bench-qemu.json |

第一份本地 Android 结果早于 Shadowsocks TCP、SOCKS5 UDP、独立 cgroup 守卫打包等改动。API 29、35 的工作流文件可随仓库提交触发。正式发布需要同一源码提交及同一安装包在对应环境获得结果。

## 对照范围

- M02、M04、M07、M08、M16、M22、M27、M28、M41、M42、M46、M52、M67、M68、M69、M70、M79、M80、M87。配置、进程或订阅的部分行为已有覆盖。涵盖重复应用、坏输入、文件回滚、节点凭据与命令状态；仍需逐项跑原验收的并发、中断及迁移组合。
- M14、M73、M78、M81、M82、M84。真实 Chromium 验证静态页面和桥接夹具，覆盖多宽度与三语。仍需 Android 管理器的实际 WebView、读屏、软键盘、旧入口和整条导航测试。
- M01、M05、M06、M15、M19、M20、M23、M60、M63、M74、M85、M86。已有显式代理、指定 UID 或热点接口的 DNS 端口测试。完整设备流量、透明接管、路由归属、真实热点下游及恢复流程仍需独立证明。
- M12、M17、M37、M39、M40、M48、M58、M59、M64、M65、M72。源码重建、固定输入、KAM 产物、差分、协议负例或基准已有证据。旧版完整交付契约、同功能吞吐与候选远端发布验证尚缺。
- 表中“待验证”包括未实现以及缺少足够观测的项目。替换旧版前需要完整执行原行的可观察预期。M54 的旧工具链要求应按新版明确去除 kamfw 的要求改为相同行为验收。

| 基线编号 | 状态 | 场景索引（完整条件见固定基线） |
| --- | --- | --- |
| M01 | 部分验证 | 新 root 设备安装 full ZIP，重启，打开引导，提供合法合成测试订阅 |
| M02 | 部分验证 | 对相同有效配置重复 apply |
| M03 | 待验证 | tun→ebpf，注入启动/attachment/提交失败 |
| M04 | 部分验证 | URL→本地→URL |
| M05 | 部分验证 | 多用户安装/卸载同包 |
| M06 | 部分验证 | Wi-Fi 名单命中/未命中、禁用 |
| M07 | 部分验证 | 覆写对象/数组/null |
| M08 | 部分验证 | WebUI 操作超时后立刻第二次写，关闭再重开 |
| M09 | 待验证 | 未认证 MCP、错误类型/未知字段、私密文件及 symlink 别名（含 .state/hotspot、应用 UID/包名/sel |
| M10 | 待验证 | 手动停止核心后保存配置、暂停/恢复 Tailscale |
| M11 | 待验证 | network-access 检查、缺少确认、stale 候选、成功 repair、第三方改策略、部分 repair/rollba |
| M12 | 部分验证 | 替换组件 ZIP 字节、路径穿越、缺组件、网络中断、移动文件时强杀 |
| M13 | 待验证 | 更新同 ID 同意图、同 ID 不同意图、并发请求、成功 staging 后未重启 |
| M14 | 部分验证 | 320/360/390/430、横屏、桌面 |
| M15 | 部分验证 | TLS/DNS/真实 App UID 流量、前后台与网络切换、TUN/eBPF、热点客户端 |
| M16 | 部分验证 | 故意植入凭据的合成配置，导出 support/backup、状态与发布包 |
| M17 | 部分验证 | 依照 PERFORMANCE.md 在相同 workload 复测 |
| M18 | 待验证 | 新手按应用名称和域名建立自定义分流，选择或创建可读策略组/出口 |
| M19 | 部分验证 | hotspot reconcile 持锁期间发起 service start/stop/restart，含核心已运行的 no-op |
| M20 | 部分验证 | 热点拓扑变化、长时间配置应用、WebUI 超时后连续操作 |
| M21 | 待验证 | 安装器迁移清单新增路径、显式排除项、备份/恢复/复制故障 |
| M22 | 部分验证 | 连续五轮启动/优雅停止 |
| M23 | 部分验证 | TUN/eBPF 热点下游 IPv4、IPv6 TCP/UDP |
| M24 | 待验证 | 真实 Google Play、GMS、GSF 的 DNS 与应用请求，含至少两种 OEM 策略环境 |
| M25 | 待验证 | Tailscale 发现、TSMP/ICMP 与实际 Tailnet 应用访问 |
| M26 | 待验证 | 同设备重复冷/热启动、空闲扫描、不少于 600 秒公网稳定性观察 |
| M27 | 部分验证 | 活动 config 为空/损坏、last-known-good 缺失/损坏、事务中断 |
| M28 | 部分验证 | 订阅下载超时、解析失败、核心启动失败及重试/取消 |
| M29 | 待验证 | sing-box 1.15 原生 TUN stack 迁移与锁定核心的性能比较 |
| M30 | 待验证 | 1/2/5 个来源逐个成功后一起导入，经 UI 私有payload、CLI列表和命名MCP工具，再重排与回读 |
| M31 | 待验证 | scheme/host大小写、默认443、空path、fragment、LF/CRLF/CR、Unicode path/query |
| M32 | 待验证 | A/B各一个同名不同端点的复杂节点，分别/一起导入 |
| M33 | 待验证 | A fresh+B cached、B无可信缓存、B缓存属于C、混合JSON/YAML/分享文本、每个激活/回滚阶段中断 |
| M34 | 待验证 | 已保存1源但候选2源失败 |
| M35 | 待验证 | 两源只一条metadata、保存B后继续编辑C、旧成功晚回调、UA保存后来源失败、本地8MiB边界、清空来源 |
| M36 | 待验证 | VE-005全部层级：VLESS普通/空/none/启用值、分享链接与YAML、结构化出站编辑、32/1184字节公钥、长字段、非 |
| M37 | 部分验证 | 从配方归档生成完整提示词，在无旧MagicNet源码的空上下文开始重建 |
| M38 | 待验证 | POLICY-A01–07、A26–A29：边界/重复/环/目标缺失/DNS模板/外部修改、订阅新增后物化与reset、保护与准备 |
| M39 | 部分验证 | 比较MagicNet-core.zip、MagicNet.zip、magicnet_installer.zip，再用各别名安装升级 |
| M40 | 部分验证 | delivery/RELEASE_CONTRACT：固定源码构建、错误身份/版本/摘要、缺少验收和草稿恢复 |
| M41 | 部分验证 | LIFE-A01–A04：短启动预算、长命守护、就绪前控制方退出/超时、就绪后 worker 组终止与回滚 |
| M42 | 部分验证 | LIFE-A05–A07：真实 mksh、POSIX sh、Bash/BusyBox 的 PID 边界，配置/订阅锁恢复及信号路径 |
| M43 | 待验证 | control 验收 12：常规与密集短行日志、CRLF/UTF-8/截断/追加、相同输入的分配与时间对比 |
| M44 | 待验证 | SUB-A19：异端点同名 HK，分别无引用、只有指向无冲突 base 的引用、实际引用冲突 HK、可确认同源身份的重写 |
| M45 | 待验证 | SUB-A20：A 原生已知 2 个不同有效节点但转换 1 个，B 有额外节点 |
| M46 | 部分验证 | C-SUB-008：status/inspect 的 URL 64 KiB、本地 8 MiB 边界、坏编码、NUL、链接/目录/F |
| M47 | 待验证 | 配方迁移、合并及发布前检查主仓库根 module.yaml、description/icon 引用资源和正式资产目录 |
| M48 | 部分验证 | CORE-A01–A06：固定上游同步、TCP/UDP 握手失败、AttachFlow/CloseFlow 重叠与竞态、资源回收和 |
| M49 | 待验证 | POLICY-A08–A12：精确目标、端口、模式/应用/用户增量重叠、DNS 优先、新装/升级和订阅刷新 |
| M50 | 待验证 | POLICY-A13–A15：Voice 维护入口、规则库存、构建/刷新与普通 ChatGPT 分流 |
| M51 | 待验证 | 同时存在 .local/state、.state、.tmp、.cache |
| M52 | 部分验证 | 嵌套或后台锁 owner 被终止、父进程仍活 |
| M53 | 待验证 | Android CLI 系统路由无默认接口观测、显式接口绑定、图形客户端、失网后恢复 |
| M54 | 待验证 | delivery 启动器合同：干净检出初始化 `kamfw`，执行安装、卸载、当前用户浏览器选择与错误回退 |
| M55 | 待验证 | POLICY-A16–A20：16 个教育后缀的根域名/子域名、边界负例、前序保护及后续分类重叠 |
| M56 | 待验证 | CON-A01–A07：Google正常/故障2小时/时钟跳变/worker重启、差异探测、并发与用户停止、无系统curl的实际A |
| M57 | 待验证 | DIAG-A01–A08：WebUI一键/双击、CLI机器/人类、坏配置/工具缺失/超时、并发/写失败与私密canary、HTTP |
| M58 | 部分验证 | 核心/完整/全部组件最终ZIP嵌套tests/fixtures/benchmarks/coverage/node_modules反 |
| M59 | 部分验证 | REWRITE_CONTRACT：固定原版与候选，覆盖 kamfw、运行时、CLI/MCP、WebUI、安装和打包 |
| M60 | 部分验证 | POLICY-A21–A25、A30–A33：本地mDNS正反例、全部profile/Tailscale物化、规则资产校验、未知域 |
| M61 | 待验证 | delivery 0.2.7：core/full/installer 的 SKIPUNZIP 新装、旧目录恢复、自定义/缺失/链接 |
| M62 | 待验证 | SUB-A22、LIFE-A12：fswatch on/off、初始恢复/激活/回滚/信号、无关和真实未知 PID、热点及 DNS |
| M63 | 部分验证 | control 验收 16：TUN 接口存在但规则/路由缺失、仅热点残留、标记/表/优先级变化、IPv4/IPv6、Android |
| M64 | 部分验证 | delivery 0.2.7：TLS 受控时钟偏差、错误主机名/信任、GET 不符、数据面未知和失败脱敏产物 |
| M65 | 部分验证 | delivery 0.2.8：主/源码不同版、bump/自定义版本、固定快照、同版本构建与Android门禁、原artifact上 |
| M66 | 待验证 | CON-A08–A09：运行中自有 RPDB 丢失、一次性 x86_64 AVD 的单 eth0 上联断续、unknown/sto |
| M67 | 部分验证 | 订阅初始/读取失败/旧响应、写入忙碌/排队/后台超时、空设备/原始缓存/本地成功无缓存 |
| M68 | 部分验证 | api select 缺参 |
| M69 | 部分验证 | SUB-A23–A26、C-SUB-009、UI-SUB-013：默认拒绝与显式可信 origin/CIDR、HTTP 80/HT |
| M70 | 部分验证 | watcher 退出/并发启动/启动中停止 |
| M71 | 待验证 | control 验收第 24 项与 POLICY-A34–A37 |
| M72 | 部分验证 | 固定依赖刷新、规则重复安装、损坏下载缓存、HTTP 200 错误页面、新草稿暂未列出、eCapture 文本诊断、生产/AVD/W |
| M73 | 部分验证 | WebUI 验收 20、31、34–35 与 UI-NAV-001–002：四项日常直达、更多十页、深链接/历史/快速跳转 |
| M74 | 部分验证 | CON-A10、LIFE-A16：核心退出后残留自有 DNS/热点资源、此时手动检查留下待处理请求 |
| M75 | 待验证 | 所选代理和 network-test/mixed 路径结果不同 |
| M76 | 待验证 | 超过三个候选、跨组/虚拟出站、保存/PUT/读回/复验失败与外部新选择 |
| M77 | 待验证 | 长退避中显式 check、手动切换即时复验、并发/停止、普通读取与机器写拒绝 |
| M78 | 部分验证 | UI 36–38、C-UI-001–003：首页/面板/宽屏顶栏、新旧 CLI、资源/API 失败、旧快照、非法地址、重复点击及三 |
| M79 | 部分验证 | HK/JP/US 合成订阅排除 HK |
| M80 | 部分验证 | control 的订阅 JSON/完整性场景：多 awk 三模式、1 VMess+2 legacy SS、转换器坏端点/空认证、未 |
| M81 | 部分验证 | UI-HOME-001–002、UI-QUICK-001、UI 19/20/34/38：三语、主题、手机/横屏/桌面、停止/未知/ |
| M82 | 部分验证 | UI-MOBILE-001–004：全部 14 页、360/390/430px、浅深主题与三语 |
| M83 | 待验证 | 不开启 errexit 的实际工具构建入口：yq 准备失败而 jq 可成功、yq 成功后 jq 失败、两项成功 |
| M84 | 部分验证 | webui UI-POLISH-001、UI-MODAL-001：手机、短视口与桌面首页 |
| M85 | 部分验证 | runtime LIFE-A17–A19：数值表 2022 的命名、命名变化、另一表的名称为 2022、相同优先级及重复规则 |
| M86 | 部分验证 | runtime LIFE-A20–A21：自有热点循环持续提交 reconcile |
| M87 | 部分验证 | runtime LIFE-A22–A23：运行中 start/ensure |
