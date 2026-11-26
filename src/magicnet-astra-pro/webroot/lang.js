"use strict";

window.strings = (() => {
  const words = {
    "应用与热点分流": ["App and hotspot routing", "Маршрутизация приложений и точки доступа"],
    "选中范围的公网 TCP 连接经过代理。直接访问 DNS 的 53 和 853 端口会被阻止。": ["Public TCP connections in the selection use the proxy. Direct DNS on ports 53 and 853 is blocked.", "Публичные TCP-соединения выбранных клиентов идут через прокси. Прямой DNS на портах 53 и 853 блокируется."],
    "应用包名与 UID（可多选）": ["App packages and UIDs (multiple selection)", "Приложения и UID (можно выбрать несколько)"],
    "热点接口（多个用空格隔开）": ["Hotspot interfaces (space-separated)", "Интерфейсы точки доступа через пробел"],
    "应用分流": ["Apply routing", "Применить"],
    "清除分流": ["Clear routing", "Сбросить"],
    "IPv4 已分流，IPv6 公网 TCP 已阻止": ["IPv4 routed, public IPv6 TCP blocked", "IPv4 через прокси, публичный TCP по IPv6 заблокирован"],
    "分流已启用": ["Routing active", "Маршрутизация включена"],
    "分流已暂停": ["Routing paused", "Маршрутизация приостановлена"],
    "分流已关闭": ["Routing off", "Маршрутизация выключена"],
    "请填写热点的实际接口名称。": ["Enter a hotspot interface name.", "Укажите имя интерфейса точки доступа."],
    "请选择至少一个应用或热点接口。": ["Choose at least one app or interface.", "Выберите приложение или интерфейс."],
    "刷新": ["Refresh", "Обновить"],
    "网络代理": ["Network proxy", "Сетевой прокси"],
    "网络模式": ["Network mode", "Режим сети"],
    "需要恢复": ["Recovery needed", "Требуется восстановление"],
    "应用流量通过 TUN，UDP 需要支持 UDP 的 SOCKS5 上游。": ["App traffic uses TUN. UDP requires a SOCKS5 upstream with UDP support.", "Трафик приложений проходит через TUN. Для UDP нужен сервер SOCKS5 с поддержкой UDP."],
    "模块缺少 TUN 引擎。": ["The TUN engine is missing.", "Движок TUN отсутствует."],
    "TUN 需要 root 权限。": ["TUN requires root access.", "Для TUN нужны права root."],
    "TUN 接口或策略路由表已被占用。": ["The TUN interface or routing policy is already in use.", "Интерфейс TUN или политика маршрутизации уже используется."],
    "设备无法读取策略路由。": ["Could not read the routing policy.", "Не удалось прочитать политику маршрутизации."],
    "TUN 接口未就绪，请查看 tun.log。": ["The TUN interface did not start. Check tun.log.", "Интерфейс TUN не запустился. См. tun.log."],
    "设备未能设置双栈 TUN 路由。": ["Could not set up IPv4 and IPv6 routes.", "Не удалось настроить маршруты IPv4 и IPv6."],
    "设备未能设置应用 UID 路由规则。": ["Could not install UID routing rules.", "Не удалось применить правила маршрутизации по UID."],
    "TUN 策略清理失败，请重试停止操作。": ["Could not remove the TUN policy. Retry stopping.", "Не удалось снять политику TUN. Повторите остановку."],
    "本机代理": ["Local proxy", "Локальный прокси"],
    "读取中": ["Loading", "Загрузка"],
    "运行中": ["Running", "Работает"],
    "已停止": ["Stopped", "Остановлен"],
    "待配置": ["Setup needed", "Нужна настройка"],
    "未连接": ["Disconnected", "Нет подключения"],
    "支持 SOCKS5 与 HTTP CONNECT。请在使用代理的应用内填写本机地址。": [
      "Enter the local address in an app that supports SOCKS5 or HTTP CONNECT.",
      "Укажите локальный адрес в приложении с поддержкой SOCKS5 или HTTP CONNECT."],
    "本机地址": ["Local address", "Локальный адрес"],
    "当前上游": ["Upstream", "Сервер"],
    "未设置": ["Not set", "Не задан"],
    "启动代理": ["Start proxy", "Запустить"],
    "停止代理": ["Stop proxy", "Остановить"],
    "上游节点": ["Upstream proxy", "Прокси-сервер"],
    "Shadowsocks、SOCKS5、HTTP 或 HTTPS 地址": ["Shadowsocks, SOCKS5, HTTP or HTTPS address", "Адрес Shadowsocks, SOCKS5, HTTP или HTTPS"],
    "域名上游使用加密 DNS。HTTPS 上游可添加 ?server_name=证书域名。应用交给代理的域名由上游解析。": [
      "Named upstreams use encrypted DNS. For HTTPS, add ?server_name= with the certificate hostname if needed. The upstream resolves names supplied by your apps.",
      "Имена прокси разрешаются через шифрованный DNS. Для HTTPS при необходимости добавьте ?server_name= с именем из сертификата. Имена, переданные приложением, разрешает прокси."],
    "保存并启动": ["Save and start", "Сохранить и запустить"],
    "保存并应用": ["Apply changes", "Применить"],
    "从订阅导入": ["Import subscription", "Импорт подписки"],
    "订阅来源": ["Source", "Источник"],
    "本地文件": ["Local file", "Файл"],
    "HTTPS 地址": ["HTTPS URL", "Ссылка HTTPS"],
    "订阅文件": ["Subscription file", "Файл подписки"],
    "网页支持 32 KiB 以内的文件。更大的文件可通过 shell 的 import 命令导入。": [
      "The WebUI accepts files up to 32 KiB. Use the shell import command for larger files.",
      "Веб-интерфейс принимает файлы до 32 КиБ. Для больших файлов используйте команду import в оболочке."],
    "订阅地址": ["Subscription URL", "Ссылка подписки"],
    "可选": ["optional", "необязательно"],
    "远程订阅通过运行中的本机代理下载。首次配置可先导入本地文件。": [
      "Remote feeds use the running local proxy. To set up the first node, import a local file.",
      "Удалённая подписка загружается через запущенный прокси. При первой настройке импортируйте файл."],
    "读取节点": ["Load nodes", "Загрузить узлы"],
    "搜索节点": ["Find a node", "Найти узел"],
    "选择节点": ["Choose a node", "Выберите узел"],
    "不可用": ["Unavailable", "Недоступен"],
    "无匹配节点": ["No matching nodes", "Нет подходящих узлов"],
    "当前订阅中没有可用的节点。": ["No supported nodes in this subscription.", "В подписке нет поддерживаемых узлов."],
    "节点列表已更新或过期，请重新读取。": ["Reload the node list before applying.", "Список изменился или устарел. Загрузите его снова."],
    "已配置的节点负责下载订阅。首次导入使用加密 DNS 和 HTTPS。": ["Downloads use the configured proxy. The first import uses encrypted DNS and HTTPS.", "Загрузка идёт через настроенный прокси. При первом импорте используются шифрованный DNS и HTTPS."],
    "节点序号": ["Node number", "Номер узла"],
    "应用订阅节点": ["Apply selected node", "Применить узел"],
    "节点已应用。": ["Proxy applied.", "Прокси настроен."],
    "订阅节点已保存。": ["Subscription node saved.", "Узел подписки сохранён."],
    "请先为模块配置 age 身份文件。": ["Set an age identity file first.", "Сначала укажите файл ключа age."],
    "请检查模块管理器提供的 BusyBox 是否可用。": ["Check the module manager’s BusyBox installation.", "Проверьте BusyBox в менеджере модулей."],
    "当前环境需要可执行的 age 工具来解密文件。": ["Install age to decrypt this file.", "Для расшифровки нужен age."],
    "请从 KernelSU 管理器打开此模块的 WebUI。": ["Open this WebUI from the KernelSU manager.", "Откройте интерфейс из менеджера KernelSU."],
    "模块缺少 magicbox 可执行文件。": ["The module is missing the magicbox binary.", "В модуле отсутствует программа magicbox."],
    "当前环境需要可执行的 curl 工具来下载订阅。": ["Install curl to download a subscription.", "Для загрузки подписок нужен curl."],
    "解密失败，请检查 age 身份文件。": ["Decryption failed. Check the age identity file.", "Ошибка расшифровки. Проверьте ключ age."],
    "订阅下载失败，请检查代理、地址和 User-Agent。": ["Download failed. Check the proxy, URL and User-Agent.", "Ошибка загрузки. Проверьте прокси, ссылку и User-Agent."],
    "无法读取所选文件。": ["Cannot read the selected file.", "Не удалось прочитать выбранный файл."],
    "订阅地址必须以 https:// 开头。": ["Enter an HTTPS subscription URL.", "Укажите ссылку HTTPS."],
    "导入失败，请检查订阅格式及节点序号。": ["Import failed. Check the feed format and node number.", "Ошибка импорта. Проверьте формат и номер узла."],
    "订阅为空或超过 2 MiB。": ["The subscription is empty or exceeds 2 MiB.", "Подписка пуста или превышает 2 МиБ."],
    "节点地址无效。请填写带端口的 IP 地址或域名，支持 Shadowsocks AEAD、SOCKS5、HTTP 和 HTTPS。": [
      "Enter a Shadowsocks AEAD, SOCKS5, HTTP or HTTPS address with a host and port.", "Укажите адрес Shadowsocks AEAD, SOCKS5, HTTP или HTTPS с адресом узла и портом."],
    "请检查模块数据目录中 resolver 文件的地址和权限。": ["Check the address and permissions of the resolver file in the module data directory.", "Проверьте адрес и права файла resolver в каталоге данных модуля."],
    "请输入 1 到 65535 之间的节点序号。": ["Enter a node number from 1 to 65535.", "Введите номер узла от 1 до 65535."],
    "User-Agent 包含不支持的字符。": ["The User-Agent contains invalid characters.", "В User-Agent есть недопустимые символы."],
    "订阅地址格式无效。": ["Invalid subscription URL.", "Недопустимая ссылка подписки."],
    "请先配置上游节点。": ["Set an upstream proxy first.", "Сначала задайте адрес прокси."],
    "操作未完成，请查看模块 CLI 的状态和日志。": ["Operation failed. Check status and log in the CLI.", "Ошибка операции. Проверьте состояние и журнал в CLI."],
    "新配置未能启动，已恢复之前的配置。": ["The new configuration failed to start. The previous one is running.", "Новая конфигурация не запустилась. Предыдущая восстановлена."],
    "请先启动本机代理，或选择本地文件。": ["Start the proxy first, or choose a local file.", "Запустите прокси или выберите локальный файл."],
    "恢复之前的配置失败，请查看模块 CLI 日志。": ["Could not restore the previous configuration. Check the CLI log.", "Ошибка восстановления конфигурации. Проверьте журнал CLI."],
    "启动失败，请检查端口占用和模块规则集。": ["Startup failed. Check port availability and the module rules.", "Ошибка запуска. Проверьте порт и набор правил."],
    "操作超时，请刷新状态。": ["Request timed out. Refresh the status.", "Истекло время ожидания. Обновите состояние."],
    "网页导入上限为 32 KiB。较大文件请用 shell 导入。": ["Web imports are limited to 32 KiB. Use the shell for larger files.", "Предел веб-импорта — 32 КиБ. Для больших файлов используйте оболочку."]
  };
  let selected;
  try { selected = localStorage.getItem("magicnet.language"); } catch {}
  const lang = selected || navigator.language;
  let current = /^ru/i.test(lang) ? "ru" : /^zh/i.test(lang) ? "zh" : "en";
  const elements = Array.from(document.querySelectorAll("[data-i18n]"), el => [el, el.textContent]);
  const t = zh => current === "zh" ? zh : (words[zh]?.[current === "ru" ? 1 : 0] || zh);
  function apply() {
    document.documentElement.lang = current === "zh" ? "zh-CN" : current;
    document.getElementById("language").value = current;
    for (const [el, text] of elements) el.textContent = t(text);
  }
  document.getElementById("language").addEventListener("change", event => {
    current = event.target.value;
    try { localStorage.setItem("magicnet.language", current); } catch {}
    apply();
    document.dispatchEvent(new Event("magicnet-language"));
  });
  apply();
  return {t};
})();
