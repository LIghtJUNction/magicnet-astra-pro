"use strict";

const {t} = window.strings;
const api = window.magicnet;
const $ = id => document.getElementById(id);
const errors = {
  invalid_interface: "请填写热点的实际接口名称。",
  invalid_scope: "请选择至少一个应用或热点接口。",
  age_identity_required: "请先为模块配置 age 身份文件。",
  busybox_required: "请检查模块管理器提供的 BusyBox 是否可用。",
  age_required: "当前环境需要可执行的 age 工具来解密文件。",
  bridge_unavailable: "请从 KernelSU 管理器打开此模块的 WebUI。",
  core_missing: "模块缺少 magicbox 可执行文件。",
  curl_required: "当前环境需要可执行的 curl 工具来下载订阅。",
  decrypt_failed: "解密失败，请检查 age 身份文件。",
  fetch_failed: "订阅下载失败，请检查代理、地址和 User-Agent。",
  file_unreadable: "无法读取所选文件。",
  https_required: "订阅地址必须以 https:// 开头。",
  import_failed: "导入失败，请检查订阅格式及节点序号。",
  input_too_large_or_empty: "订阅为空或超过 2 MiB。",
  invalid_config: "节点地址无效。请填写带端口的 IP 地址或域名，支持 Shadowsocks AEAD、SOCKS5、HTTP 和 HTTPS。",
  invalid_index: "请输入 1 到 65535 之间的节点序号。",
  invalid_ua: "User-Agent 包含不支持的字符。",
  invalid_url: "订阅地址格式无效。",
  no_upstream: "请先配置上游节点。",
  operation_failed: "操作未完成，请查看模块 CLI 的状态和日志。",
  previous_config_restored: "新配置未能启动，已恢复之前的配置。",
  proxy_required: "请先启动本机代理，或选择本地文件。",
  rollback_failed: "恢复之前的配置失败，请查看模块 CLI 日志。",
  start_failed: "启动失败，请检查端口占用和模块规则集。",
  timeout: "操作超时，请刷新状态。",
  stale_preview: "节点列表已更新或过期，请重新读取。",
  no_ready_nodes: "当前订阅中没有可用的节点。",
  web_limit: "网页导入上限为 32 KiB。较大文件请用 shell 导入。"
};
let snapshot;
let busy = false;
let notice = "";

function render() {
  const connected = Boolean(snapshot);
  const running = snapshot?.state === "running";
  const upstream = snapshot?.upstream;
  document.body.dataset.running = running ? "yes" : "no";
  $("state").textContent = t(connected ? (running ? "运行中" : upstream ? "已停止" : "待配置") : "未连接");
  $("listen").textContent = snapshot?.listen || "—";
  $("upstream").textContent = upstream || t(connected ? "未设置" : "—");
  $("toggle").textContent = t(running ? "停止代理" : "启动代理");
  $("toggle").disabled = busy || !(connected && (running || upstream));
  $("save").textContent = t(running ? "保存并应用" : "保存并启动");
  $("save").disabled = busy || !connected;
  $("preview").disabled = busy || !connected;
  $("import").disabled = busy || !connected || !$("node").value;
  $("refresh").disabled = busy || !api.available();
  $("message").textContent = t(notice);
  document.dispatchEvent(new Event("magicnet-state"));
}

async function readState() {
  const fields = {};
  for (const line of (await api.status()).trim().split("\n")) {
    const split = line.indexOf("=");
    if (split >= 0) fields[line.slice(0, split)] = line.slice(split + 1);
  }
  if (!["running", "stopped"].includes(fields.state)) throw new Error("operation_failed");
  if ($("routing").open) {
    const info = await api.routeStatus().catch(() => "");
    fields.redirect = info.includes("redirect=running");
    fields.blockIPv6 = info.includes("mode=ipv4-redirect-ipv6-block");
  }
  snapshot = fields;
}

async function perform(action, message = "") {
  if (busy) return;
  busy = true;
  notice = "";
  render();
  try {
    await action();
    await readState();
    notice = message;
  } catch (error) {
    try { await readState(); } catch { snapshot = undefined; }
    notice = errors[error.message] || errors.operation_failed;
  } finally {
    busy = false;
    render();
  }
}

$("refresh").addEventListener("click", () => perform(() => {}));
$("toggle").addEventListener("click", () => perform(() => snapshot.state === "running" ? api.stop() : api.start()));
$("endpoint-form").addEventListener("submit", event => {
  event.preventDefault();
  perform(async () => {
    await api.configure($("endpoint").value.trim());
    $("endpoint").value = "";
    if (snapshot.state !== "running") await api.start();
  }, "节点已应用。");
});
document.addEventListener("magicnet-language", render);
perform(() => {});
