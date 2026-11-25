"use strict";

(() => {
  const apps = $("route-apps");
  const tethers = $("route-tethers");
  let loaded = false;
  let configured = false;

  function renderRouting() {
    const running = snapshot?.state === "running";
    const active = snapshot?.blockIPv6 ? "IPv4 已分流，IPv6 公网 TCP 已阻止" : "分流已启用";
    $("route-status").textContent = loaded
      ? t(configured ? (snapshot?.redirect ? active : "分流已暂停") : "分流已关闭") : "";
    $("route-apply").disabled = busy || !loaded || !running;
    $("route-clear").disabled = busy || !loaded || !configured;
  }

  async function loadRouting() {
    const [raw, packages] = await Promise.all([api.routeStatus(), api.routeApps().catch(() => "")]);
    const uids = new Set();
    const interfaces = [];
    for (const row of raw.split("\n")) {
      const [kind, value] = row.split(" ");
      if (kind === "uid" && /^[1-9]\d{4,9}$/.test(value)) uids.add(value);
      if (kind === "tether" && /^[\w.-]{1,15}$/.test(value)) interfaces.push(value);
    }
    // Shared app UIDs are one firewall selection. Keep previously selected
    // UIDs even if PackageManager can no longer report their package names.
    const labels = new Map();
    for (const line of packages.split("\n")) {
      const [uid, name] = line.split(" ");
      if (!/^[1-9]\d{4,9}$/.test(uid) || !/^[a-zA-Z0-9_.]+$/.test(name || "")) continue;
      labels.set(uid, [...(labels.get(uid) || []), name]);
    }
    for (const uid of uids) if (!labels.has(uid)) labels.set(uid, []);
    apps.replaceChildren(...Array.from(labels, ([uid, names]) =>
      new Option([names.join(", "), "UID " + uid].filter(Boolean).join(" · "), uid, false, uids.has(uid))));
    tethers.value = interfaces.join(" ");
    configured = uids.size > 0 || interfaces.length > 0;
    loaded = true;
  }

  $("routing").addEventListener("toggle", () => {
    if ($("routing").open && snapshot) perform(loadRouting);
  });
  $("route-form").addEventListener("submit", event => {
    event.preventDefault();
    perform(async () => {
      const interfaces = tethers.value.trim().split(/\s+/).filter(Boolean);
      if (interfaces.some(name => !/^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,14}$/.test(name)))
        throw new Error("invalid_interface");
      const items = [...Array.from(apps.selectedOptions, o => "uid:" + o.value),
                     ...interfaces.map(name => "tether:" + name)];
      if (!items.length || items.length > 64) throw new Error("invalid_scope");
      await api.routeApply(items);
      await loadRouting();
    });
  });
  $("route-clear").addEventListener("click", () => perform(async () => {
    await api.routeClear();
    await loadRouting();
  }));
  document.addEventListener("magicnet-state", renderRouting);
})();
