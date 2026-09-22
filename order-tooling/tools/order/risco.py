"""
Risk Engine (ORDER §14, §17) — determinístico, sem LLM.

    risk = max( by_resource(recurso), by_field(campo, de → para),
                action_modifier(ação), entity.risk_hint, decision_mapping )

Duas regras que o cálculo por caminho sozinho não daria, e que nasceram de
rodadas adversariais:

- **Rebaixar privacidade é A4, sempre.** A1 significa "reversível por Git", e
  Git reverte o ARQUIVO, não o EFEITO: uma vez enviado a um provedor, reverter o
  commit não traz o conteúdo de volta.
- **Promover não é privilégio.** `tool.chaos.promote` recebe exatamente a classe
  que a escrita equivalente receberia — senão a camada episódica, que ninguém
  classifica na entrada, viraria a antessala da escalação.
"""
from __future__ import annotations

import fnmatch

ORDEM = ["A0", "A1", "A2", "A3", "A4"]

BY_RESOURCE = [
    ("metadata/policies/**", "A4"), ("metadata/registries/**", "A4"),
    ("metadata/schemas/**", "A4"), ("metadata/tooling.yaml", "A4"),
    ("order/policies/**", "A4"), ("order/agents/**", "A4"),
    ("order/automations/**", "A4"), ("order/PAUSED", "A4"),
    ("AGENTS.md", "A4"), ("CLAUDE.md", "A4"),
    ("workflows/**", "A4"), (".claude/**", "A4"), ("tools/**", "A4"),
    (".github/**", "A4"), (".gitattributes", "A4"), (".gitignore", "A4"),
    ("audit/**", "A4"),
    ("indexes/**", "A1"), ("graph/**", "A1"),
]

FERRAMENTAS = {
    "tool.chaos.write": "A1",
    "tool.chaos.read": "A0",
    "tool.chaos.promote": "A1",      # escrita comum; herda by_resource/by_field
    "tool.episodic.read": "A0",      # ler nunca eleva nada
    "tool.notify.send": "A3",
    "tool.code.execute": "A3",
}

NOTIFY_RESOURCE = {"channel:self": "A2"}


def maior(*classes: str) -> str:
    validas = [c for c in classes if c in ORDEM]
    return max(validas, key=ORDEM.index) if validas else "A0"


def by_resource(recurso: str) -> str | None:
    if not recurso:
        return None
    rel = recurso.replace("\\", "/")
    for padrao, classe in BY_RESOURCE:
        if fnmatch.fnmatch(rel, padrao):
            return classe
        if padrao.endswith("/**") and rel.startswith(padrao[:-2]):
            return classe
    return None


def by_field(campo: str | None, de: str | None, para: str | None) -> str | None:
    """Rebaixar é A4; restringir é A1. A direção é o que decide."""
    if not campo:
        return None
    if "→" in campo or ":" in campo and de is None and para is None:
        # forma compacta "privacy:local_only→cloud_allowed"
        nome, _, resto = campo.partition(":")
        de, _, para = resto.partition("→")
        campo = nome
    if campo == "privacy":
        if de == "local_only" and para == "cloud_allowed":
            return "A4"
        if de == "cloud_allowed" and para == "local_only":
            return "A1"
    if campo == "execution":
        if de == "local" and para in ("cloud", "any"):
            return "A4"
        return "A1"
    if campo == "privacy_class":
        return "A4" if de != para else "A1"
    return None


def avaliar(*, tool: str = "tool.chaos.write", resource: str = "",
            action: str = "", field: str | None = None,
            de: str | None = None, para: str | None = None,
            risk_hint: str = "") -> dict:
    base = FERRAMENTAS.get(tool, "A1")
    if tool == "tool.notify.send" and resource in NOTIFY_RESOURCE:
        base = NOTIFY_RESOURCE[resource]

    componentes = {
        "tool_default": base,
        "by_resource": by_resource(resource),
        "by_field": by_field(field, de, para),
        "action_modifier": "A2" if action in ("delete", "send", "publish") else None,
        "risk_hint": risk_hint if risk_hint in ORDEM else None,
    }
    # `risk_hint` SÓ ELEVA: um agente pode propor elevação, nunca redução.
    classe = maior(*[c for c in componentes.values() if c])
    return {"risk_class": classe, "components": componentes,
            "tool": tool, "resource": resource, "field": field}
