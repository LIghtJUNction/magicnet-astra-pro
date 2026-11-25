"use strict";

// KernelSU's exec bridge joins option values into shell text. Only fixed
// commands, checked decimal indices and base64 can cross that boundary.
window.magicnet = (() => {
  const cli = "/data/adb/modules/magicnet-astra-pro/cli";
  let sequence = 0;

  function call(command, bytes) {
    return new Promise((resolve, reject) => {
      if (typeof window.ksu?.exec !== "function") {
        reject(new Error("bridge_unavailable"));
        return;
      }
      let options = {};
      if (bytes !== undefined) {
        if (bytes.length > 32768) {
          reject(new Error("web_limit"));
          return;
        }
        const encoded = btoa(String.fromCharCode(...bytes));
        options = {env: {MAGICNET_INPUT_B64: encoded}};
      }
      const callback = "magicnet_reply_" + ++sequence;
      const timer = setTimeout(() => {
        delete window[callback];
        reject(new Error("timeout"));
      }, 45000);
      const cleanup = () => { clearTimeout(timer); delete window[callback]; };
      window[callback] = (code, output, stderr) => {
        cleanup();
        if (Number(code) === 0) resolve(String(output || ""));
        else reject(new Error(String(stderr || "").match(/magicnet: ([a-z_]+)\s*$/)?.[1] || "operation_failed"));
      };
      try { window.ksu.exec(command, JSON.stringify(options), callback); }
      catch { cleanup(); reject(new Error("bridge_unavailable")); }
    });
  }

  const text = value => new TextEncoder().encode(value);
  return Object.freeze({
    available: () => typeof window.ksu?.exec === "function",
    status: () => call(cli + " status"),
    routeStatus: () => call(cli + " traffic status"),
    routeApps: () => call(cli + " traffic apps"),
    routeClear: () => call(cli + " traffic clear"),
    routeApply: items => call(cli + " web-traffic", text(items.join("\n") + "\n")),
    start: () => call(cli + " start"),
    stop: () => call(cli + " stop"),
    configure: value => call(cli + " web-configure", text(value)),
    previewFile: bytes => call(cli + " web-preview-file", bytes),
    previewUrl: (url, ua) => {
      if ([url, ua].some(field => /[\r\n\0]/.test(field))) throw new Error("invalid_url");
      return call(cli + " web-preview-url", text([url, ua, ""].join("\n")));
    },
    applyNode: (token, index) => {
      if (!/^[a-f0-9]{24}$/.test(token) || !Number.isInteger(index) || index < 1 || index > 4096)
        throw new Error("stale_preview");
      return call(cli + " web-apply " + token + " " + String(index));
    }
  });
})();
