"""通知: 日志 / Windows toast(WinRT 零依赖,plans/001 §4 实测) / webhook(urllib)。
通知失败只告警,绝不影响任务状态。"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request

SUMMARY_MAX = 120

_TOAST_PS = (
    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
    "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null;"
    "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
    "$n = $x.GetElementsByTagName('text');"
    "$n.Item(0).AppendChild($x.CreateTextNode('{title}')) | Out-Null;"
    "$n.Item(1).AppendChild($x.CreateTextNode('{msg}')) | Out-Null;"
    "$t = [Windows.UI.Notifications.ToastNotification]::new($x);"
    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('onduty').Show($t)"
)


def _summary(output: str) -> str:
    return " ".join((output or "(无输出)").split())[:SUMMARY_MAX]


def _ps_quote(s: str) -> str:
    return s.replace("'", "''")


def _safe_print(s: str) -> None:
    """控制台可能是 GBK: 打印失败降级为 ascii-repr,绝不抛异常影响任务。"""
    try:
        print(s, flush=True)
    except UnicodeEncodeError:
        print(s.encode("utf-8", errors="backslashreplace").decode("ascii"), flush=True)


def notify(cfg: dict, job: dict, status: str, output: str) -> None:
    label = {"success": "OK", "failed": "FAIL", "timeout": "TIMEOUT", "error": "ERROR"}.get(status, status)
    title = f"onduty · {job['name']} [{label}]"
    summary = _summary(output)
    for ch in job["notify"]:
        if ch == "log":
            _safe_print(f"[notify:log] {title} | {summary}")
        elif ch == "toast":
            _toast(title, summary)
        elif ch == "webhook":
            _webhook(cfg, job["name"], status, summary)


def _toast(title: str, msg: str) -> None:
    try:
        cmd = _TOAST_PS.format(title=_ps_quote(title), msg=_ps_quote(msg))
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                       capture_output=True, timeout=25, creationflags=0x08000000)
    except Exception as e:
        _safe_print(f"[notify:toast] 发送失败(忽略): {e!r}")


def _webhook(cfg: dict, job_name: str, status: str, summary: str) -> None:
    n = cfg.get("notify") or {}
    url = n.get("webhook_url")
    if not url:
        _safe_print("[notify:webhook] 未配置 webhook_url, 跳过")
        return
    tmpl = n.get("webhook_body_template") or json.dumps(
        {"job": "{{job}}", "status": "{{status}}", "summary": "{{summary}}"}, ensure_ascii=False)
    body = (tmpl.replace("{{job}}", job_name)
                .replace("{{status}}", status)
                .replace("{{summary}}", summary.replace("\n", " ")))
    try:
        req = urllib.request.Request(url, data=body.encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read(200)
    except Exception as e:
        _safe_print(f"[notify:webhook] 发送失败(忽略): {e!r}")
