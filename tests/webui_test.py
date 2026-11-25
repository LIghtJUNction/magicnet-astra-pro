"""Exercise the shipped static files in Chromium using a simulated KernelSU callback."""
import argparse
import base64
import functools
import http.server
import os
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright

WEB = Path(__file__).resolve().parents[1] / "src/magicnet-astra-pro/webroot"


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


BRIDGE = """
window.calls = [];
let upstream = "", state = "stopped", scope = [];
window.ksu = {exec(command, opts, callback) {
  const payload = JSON.parse(opts).env?.MAGICNET_INPUT_B64 || "";
  window.calls.push({command, payload});
  const action = command.split("/cli ").pop();
  let output = "", code = 0, error = "";
  if (action === "status") {
    output = "state=" + state + "\\nautostart=no\\nlisten=127.0.0.1:1080\\nupstream=" + upstream;
  } else if (action === "web-configure") {
    if (atob(payload).includes("invalid")) { code = 1; error = "magicnet: invalid_config"; }
    else upstream = "socks5://192.0.2.1:8000";
  } else if (action === "start") { state = "running"; }
  else if (action === "stop") { state = "stopped"; }
  else if (action === "traffic apps") { output = "10042 org.reader\\n10042 org.reader.sync\\n10123 org.player"; }
  else if (action === "traffic status") {
    output = "redirect=" + (scope.length && state === "running" ? "running" : "stopped") + "\\n" + scope.map(line => line.replace(":", " ")).join("\\n");
  } else if (action === "web-traffic") { scope = atob(payload).trim().split("\\n"); }
  else if (action === "traffic clear") { scope = []; }
  else if (action.startsWith("web-preview-")) {
    output = "preview=0123456789abcdef01234567\\n1\\tvless\\tunavailable\\tParis\\n2\\tsocks5\\tready\\tTaipei <b>Office</b>";
  } else if (action !== "web-apply 0123456789abcdef01234567 2") { code = 127; }
  queueMicrotask(() => window[callback](code, output, error));
}};
"""


def exercise(url, chrome, screenshot):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chrome, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 390, "height": 844}, color_scheme="dark", locale="zh-CN")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        page.get_by_text("未连接", exact=True).wait_for()
        assert page.locator("#save").is_disabled()
        page.add_init_script(BRIDGE)
        page.reload()
        page.get_by_text("待配置", exact=True).wait_for()
        assert page.locator("#toggle").is_disabled()

        secret = "socks5://example:password@192.0.2.1:8000"
        page.locator("#endpoint").fill(secret)
        page.locator("#save").click()
        page.get_by_text("运行中", exact=True).wait_for()
        assert not page.locator("#endpoint").input_value()
        assert "password" not in page.locator("body").inner_text()
        assert page.locator("#upstream").text_content() == "socks5://192.0.2.1:8000", page.locator("#upstream").text_content()
        if screenshot:
            page.screenshot(path=screenshot, full_page=True)
        page.locator("#routing summary").click()
        page.get_by_text("分流已关闭", exact=True).wait_for()
        assert page.locator("#route-apps option").count() == 2
        assert "org.reader.sync" in page.locator('#route-apps option[value="10042"]').inner_text()
        page.locator("#route-apps").select_option("10042")
        page.locator("#route-tethers").fill("wlan1;test")
        page.locator("#route-apply").click()
        page.get_by_text("请填写热点的实际接口名称。").wait_for()
        page.locator("#route-tethers").fill("wlan1")
        page.locator("#route-apply").click()
        page.get_by_text("分流已启用", exact=True).wait_for()
        scope_calls = page.evaluate("window.calls.filter(entry => entry.command.endsWith(' web-traffic'))")
        assert len(scope_calls) == 1
        assert base64.b64decode(scope_calls[0]["payload"]) == b"uid:10042\ntether:wlan1\n"
        page.locator("#route-clear").click()
        page.get_by_text("分流已关闭", exact=True).wait_for()
        assert page.locator("#route-clear").is_disabled()
        page.locator("#routing summary").click()
        page.locator("#endpoint").fill("invalid'$()")
        page.locator("#save").click()
        page.locator("#message").get_by_text("节点地址无效", exact=False).wait_for()
        page.locator("#toggle").click()
        page.get_by_text("已停止", exact=True).wait_for()

        page.locator("#subscriptions summary").click()
        raw = b"socks5://198.51.100.1:8001\nsocks5://192.0.2.1:8000\n"
        page.locator("#file").set_input_files({"name":"nodes.txt", "mimeType":"text/plain", "buffer":raw})
        page.locator("#preview").click()
        page.locator("#node").wait_for()
        assert page.locator("#node option").count() == 2
        assert page.locator('#node option[value="1"]').is_disabled()
        page.locator("#filter").fill("taipei")
        assert page.locator("#node option").count() == 1
        assert "<b>Office</b>" in page.locator("#node option").text_content()
        page.locator("#node").select_option("2")
        page.locator("#import").click()
        page.get_by_text("订阅节点已保存。").wait_for()
        page.locator("#source").select_option("remote")
        url_with_token = "https://example.org/feed?key=test&mode=short"
        ua = "test $(untrusted); '"
        page.locator("#url").fill(url_with_token)
        page.locator("#ua").fill(ua)
        page.locator("#preview").click()
        page.locator("#node").select_option("2")
        page.locator("#import").click()
        page.wait_for_function("document.querySelector('#url').value === ''")
        calls = page.evaluate("window.calls")
        for entry in calls:
            assert all(value not in entry["command"] for value in (secret, ua, "invalid'", "example.org"))
        used = [(entry["command"], base64.b64decode(entry["payload"])) for entry in calls]
        assert any(cmd.endswith(" web-preview-file") and data == raw for cmd, data in used)
        assert any(cmd.endswith(" web-preview-url") and data == f"{url_with_token}\n{ua}\n".encode()
                   for cmd, data in used)
        for width in [320, 390, 768, 1280]:
            page.set_viewport_size({"width": width, "height": 640})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator("#language").select_option("en")
        page.get_by_text("Stopped", exact=True).wait_for()
        page.locator("#language").select_option("ru")
        page.get_by_text("Остановлен", exact=True).wait_for()
        page.reload()
        page.get_by_text("Нужна настройка", exact=True).wait_for()
        assert page.locator("html").get_attribute("lang") == "ru"
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chrome", default=os.environ.get("CHROME_BIN"))
    parser.add_argument("--screenshot")
    args = parser.parse_args()
    serve = functools.partial(Handler, directory=WEB)
    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), serve) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            exercise(f"http://127.0.0.1:{server.server_port}", args.chrome, args.screenshot)
        finally:
            server.shutdown()
    print("WebUI checks passed (Chromium, simulated KernelSU bridge)")
