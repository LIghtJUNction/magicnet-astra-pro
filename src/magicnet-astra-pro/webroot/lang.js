"use strict";

window.strings = (() => {
  const words = {
    "刷新": ["Refresh", "Обновить"],
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
    "请使用 IP 地址。HTTPS 上游可添加 ?server_name=证书域名。应用交给代理的域名由上游解析。": [
      "Use an IP address. For HTTPS, add ?server_name= with the certificate hostname if needed. The upstream resolves names supplied by your apps.",
      "Укажите IP-адрес. Для HTTPS при необходимости добавьте ?server_name= с именем из сертификата. Имена, переданные приложением, разрешает прокси."],
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
    "节点地址无效。请填写带端口的 IP 地址，支持 Shadowsocks AEAD、SOCKS5、HTTP 和 HTTPS。": [
      "Enter a Shadowsocks AEAD, SOCKS5, HTTP or HTTPS address with an IP and port.", "Укажите адрес Shadowsocks AEAD, SOCKS5, HTTP или HTTPS с IP и портом."],
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
