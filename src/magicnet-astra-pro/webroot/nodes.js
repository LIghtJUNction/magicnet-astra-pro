"use strict";

(() => {
  let rows = [];
  let token = "";
  let generation = 0;
  function reset() {
    generation++;
    rows = [];
    token = "";
    $("picker").hidden = true;
    $("filter").value = "";
    $("node").replaceChildren();
    render();
  }
  function selectRows() {
    const previous = $("node").value;
    const words = $("filter").value.trim().toLocaleLowerCase();
    const options = document.createDocumentFragment();
    for (const row of rows) {
      const label = (row.label ? row.label + " · " : "") + row.protocol.toUpperCase() + " · #" + row.index;
      if (!label.toLocaleLowerCase().includes(words)) continue;
      const option = document.createElement("option");
      option.value = row.index;
      option.disabled = !row.ready;
      option.textContent = label + (row.ready ? "" : " · " + t("不可用"));
      if (previous === row.index) option.selected = true;
      options.appendChild(option);
    }
    if (!options.childNodes.length) {
      const none = document.createElement("option");
      none.value = "";
      none.textContent = t("无匹配节点");
      options.appendChild(none);
    }
    $("node").replaceChildren(options);
    if ($("node").selectedOptions[0]?.disabled) $("node").value = "";
    render();
  }
  ["file", "url", "ua"].forEach(id => $(id).addEventListener("input", reset));
  $("source").addEventListener("change", () => {
    const remote = $("source").value === "remote";
    $("remote-fields").hidden = !remote;
    $("local-fields").hidden = remote;
    reset();
  });
  $("filter").addEventListener("input", selectRows);
  $("node").addEventListener("change", render);
  document.addEventListener("magicnet-language", selectRows);

  $("preview").addEventListener("click", () => {
    reset();
    const which = generation;
    perform(async () => {
      let raw;
      if ($("source").value === "remote") {
        raw = await api.previewUrl($("url").value.trim(), $("ua").value);
      } else {
        const file = $("file").files[0];
        if (!file) throw new Error("file_unreadable");
        if (file.size > 32768) throw new Error("web_limit");
        raw = await api.previewFile(new Uint8Array(await file.arrayBuffer()));
      }
      if (which !== generation) return;
      const [header, ...lines] = raw.trimEnd().split("\n");
      const match = /^preview=([a-f0-9]{24})$/.exec(header);
      if (!match) throw new Error("import_failed");
      token = match[1];
      rows = lines.map(line => {
        const [index, protocol, status, label = ""] = line.split("\t");
        return {index, protocol, ready: status === "ready", label};
      }).filter(row => /^\d{1,4}$/.test(row.index) && /^[a-z0-9+-]{1,32}$/.test(row.protocol));
      $("picker").hidden = false;
      selectRows();
      if (!rows.some(row => row.ready)) throw new Error("no_ready_nodes");
    });
  });
  $("import-form").addEventListener("submit", event => {
    event.preventDefault();
    perform(async () => {
      await api.applyNode(token, Number($("node").value));
      $("url").value = "";
      $("file").value = "";
      reset();
    }, "订阅节点已保存。");
  });
})();
