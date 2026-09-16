"""适配器注册表。内置: dsh/codebuddy(=workbuddy 别名)/zcode(占位);agents.<name>.type=custom 优先。"""
from __future__ import annotations

from .base import Adapter
from .codebuddy import CodebuddyAdapter
from .custom import CustomAdapter
from .dsh import DshAdapter
from .zcode import ZcodeAdapter

BUILTIN = {
    "dsh": DshAdapter,
    "codebuddy": CodebuddyAdapter,
    "workbuddy": CodebuddyAdapter,  # 同一 CLI 的产品别名;command 默认 codebuddy,可 agents 配置覆盖
    "zcode": ZcodeAdapter,
}


def resolve(name: str, agents_cfg: dict) -> Adapter:
    """按名字取适配器实例;type=custom 或未注册但给了 command 时走 CustomAdapter。"""
    acfg = (agents_cfg or {}).get(name) or {}
    if acfg.get("type") == "custom" or (name not in BUILTIN and acfg.get("command")):
        return CustomAdapter(name, acfg)
    cls = BUILTIN.get(name)
    if cls is None:
        return type("MissingAdapter", (Adapter,), {"name": name, "capable": False})()
    return cls()
