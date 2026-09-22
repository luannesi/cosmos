"""
Testes de unidade dos motores.

A suíte de aceitação verifica o sistema de fora, pela CLI, e é lenta. Estes
verificam as funções puras — risco, guard, workflows, bitemporalidade — em
milissegundos, e cobrem os casos de borda que nenhum AT exercita porque um AT
descreve um critério de aceitação, não uma tabela-verdade.

    python -m pytest tests/ -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.chaos import ids, indice
from tools.chaos.repo import eh_protegido
from tools.order import guarda, risco


# --------------------------------------------------------------------------- #
# Risk Engine                                                                   #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("recurso,esperado", [
    ("order/policies/quotas.yaml", "A4"),
    ("order/agents/registry.yaml", "A4"),
    ("order/automations/AUT-x.md", "A4"),
    ("metadata/tooling.yaml", "A4"),
    ("AGENTS.md", "A4"),
    ("workflows/briefing.yaml", "A4"),
    ("audit/events.jsonl", "A4"),
    ("indexes/bm25.json", "A1"),
    ("tasks/TSK-1.md", "A1"),
])
def test_risco_por_recurso(recurso, esperado):
    assert risco.avaliar(resource=recurso)["risk_class"] == esperado


@pytest.mark.parametrize("campo,de,para,esperado", [
    ("privacy", "local_only", "cloud_allowed", "A4"),   # divulgar é irreversível
    ("privacy", "cloud_allowed", "local_only", "A1"),   # restringir não divulga
    ("execution", "local", "any", "A4"),
    ("execution", "local", "cloud", "A4"),
    ("privacy_class", "trabalho", "pessoal", "A4"),
    ("privacy_class", "trabalho", "trabalho", "A1"),
])
def test_risco_por_campo(campo, de, para, esperado):
    assert risco.avaliar(field=campo, de=de, para=para)["risk_class"] == esperado


def test_forma_compacta_do_campo():
    """`privacy:local_only→cloud_allowed` é a forma que o ORDER AT-28 usa."""
    r = risco.avaliar(tool="tool.chaos.promote", resource="sources/",
                      field="privacy:local_only→cloud_allowed")
    assert r["risk_class"] == "A4"


def test_hint_so_eleva():
    base = risco.avaliar(resource="tasks/")["risk_class"]
    assert risco.avaliar(resource="tasks/", risk_hint="A0")["risk_class"] == base
    assert risco.avaliar(resource="tasks/", risk_hint="A3")["risk_class"] == "A3"


def test_promover_nao_e_privilegio():
    """A promoção recebe a classe da escrita equivalente — nunca uma mais branda."""
    for recurso in ("order/policies/quotas.yaml", "AGENTS.md", "tools/x.py"):
        assert (risco.avaliar(tool="tool.chaos.promote", resource=recurso)["risk_class"]
                == risco.avaliar(tool="tool.chaos.write", resource=recurso)["risk_class"])


def test_ler_episodico_nunca_eleva():
    assert risco.avaliar(tool="tool.episodic.read", resource="qualquer")["risk_class"] == "A0"


def test_notificar_a_si_e_a2_e_terceiro_e_a3():
    assert risco.avaliar(tool="tool.notify.send",
                         resource="channel:self")["risk_class"] == "A2"
    assert risco.avaliar(tool="tool.notify.send",
                         resource="channel:cliente")["risk_class"] == "A3"


# --------------------------------------------------------------------------- #
# Guard — por família, nunca por plataforma                                    #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("comando", [
    "python3 -c print(1)", "node -e x", "powershell -Command Set-Content a b",
    "powershell -EncodedCommand UwBlAHQA", "cmd /c echo x > a.md",
    "bash -c 'echo x >> tasks/a.md'", "sed -i s/a/b/ tasks/a.md",
    "tee tasks/a.md", "powershell -Command Add-Content a b",
    "sh -c 'echo x > y.md'", "cmd /c powershell -Command exit",
    "git commit -am x", "git push",
])
def test_guard_nega(comando):
    permitido, motivo = guarda.avaliar_comando(comando.split())
    assert not permitido and motivo


@pytest.mark.parametrize("comando", [
    "chaos task create --title x", "order status", "git status",
    "git log --oneline", "cat AGENTS.md", "grep -r termo .",
])
def test_guard_permite(comando):
    permitido, _ = guarda.avaliar_comando(comando.split())
    assert permitido


def test_guard_nao_depende_do_host():
    """
    Um Windows com Git Bash executa `sed -i`; um Linux com PowerShell executa
    `Set-Content`. Negar só a metade correspondente ao host abriria a outra.
    """
    for c in ("sed -i s/a/b/ x.md", "powershell -Command Set-Content x.md y"):
        assert not guarda.avaliar_comando(c.split())[0]


def test_guard_escrita_em_recurso():
    assert not guarda.avaliar_comando(["write", "order/policies/quotas.yaml"])[0]
    assert guarda.avaliar_comando(["write", "tasks/TSK-1.md"])[0]


# --------------------------------------------------------------------------- #
# Protected paths — derivados de critério                                      #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("caminho", [
    "metadata/policies/x.yaml", "metadata/tooling.yaml", "order/agents/registry.yaml",
    "order/automations/AUT-1.md", "AGENTS.md", "CLAUDE.md", "workflows/w.yaml",
    ".claude/settings.json", "tools/chaos/cli.py", ".gitattributes",
    ".ai-memory.toml", "order/PAUSED",
])
def test_protegido(caminho):
    assert eh_protegido(caminho)


@pytest.mark.parametrize("caminho", [
    "areas/pesquisa/state.md",      # conteúdo: o agente dono é quem mantém
    "tasks/TSK-1.md", "projects/PRJ-1/state.md", "wiki/nota.md",
    "reports/onboarding-2026-09-20.md", "indexes/bm25.json",
])
def test_nao_protegido(caminho):
    """O critério separa governança de conteúdo — sem essa linha, protege-se o
    Área State e engessa-se o sistema em nome da segurança."""
    assert not eh_protegido(caminho)


# --------------------------------------------------------------------------- #
# IDs e bitemporalidade                                                        #
# --------------------------------------------------------------------------- #

def test_id_formato_e_alfabeto():
    for tipo in ("task", "project", "decision", "run"):
        novo = ids.novo_id(tipo)
        assert ids.id_valido(novo)
        assert ids.tipo_de(novo) == tipo
        sufixo = novo.split("-")[2]
        assert not (set(sufixo) & set("01OI")), "alfabeto sem 0/O/1/I (§7.2)"
        assert sufixo.upper() == sufixo, "só maiúsculo: seguro em FS insensível a caso"


def test_ids_nao_colidem_em_lote():
    gerados = {ids.novo_id("task") for _ in range(5000)}
    assert len(gerados) == 5000


@pytest.mark.parametrize("vf,vt,corte,esperado", [
    ("", "", "2026-09-20", True),
    ("2026-01-01", "", "2026-09-20", True),
    ("2027-01-01", "", "2026-09-20", False),      # vigência futura
    ("2026-01-01", "2026-06-01", "2026-09-20", False),   # já superada
    ("2026-01-01", "2026-06-01", "2026-03-01", True),    # vigente na data
])
def test_vigencia(vf, vt, corte, esperado):
    doc = {"valid_from": vf, "valid_to": vt}
    assert indice.vigente(doc, corte) is esperado


def test_bm25_ranqueia_o_mais_relevante_primeiro(tmp_path):
    docs = {
        "A": {"tokens": indice.normalizar("calibração do espectrômetro de massa"),
              "path": "a", "title": "A", "type": "task",
              "privacy": "cloud_allowed", "authority": "active",
              "valid_from": "", "valid_to": ""},
        "B": {"tokens": indice.normalizar("compra de café"), "path": "b", "title": "B",
              "type": "task", "privacy": "cloud_allowed", "authority": "active",
              "valid_from": "", "valid_to": ""},
    }
    indice.gravar(tmp_path, docs)
    r = indice.buscar(tmp_path, "espectrômetro")
    assert r and r[0]["id"] == "A"
    assert indice.buscar(tmp_path, "inexistente") == []


def test_normalizar_ignora_acento_e_caixa():
    assert indice.normalizar("Calibração") == indice.normalizar("calibracao")


# --------------------------------------------------------------------------- #
# Workflow Engine                                                              #
# --------------------------------------------------------------------------- #

def _wf(tmp_path, steps):
    import yaml
    (tmp_path / "workflows").mkdir(parents=True, exist_ok=True)
    (tmp_path / "workflows" / "w.yaml").write_text(
        yaml.safe_dump({"name": "w", "steps": steps}), encoding="utf-8")
    return tmp_path


def test_workflow_exige_id_e_ferramenta(tmp_path):
    from tools.chaos.repo import ErroChaos
    from tools.order import workflows
    _wf(tmp_path, [{"id": "a"}])
    with pytest.raises(ErroChaos):
        workflows.carregar(tmp_path, "w")
    _wf(tmp_path, [{"tool": "tool.chaos.write"}])
    with pytest.raises(ErroChaos):
        workflows.carregar(tmp_path, "w")


def test_workflow_recusa_id_duplicado(tmp_path):
    from tools.chaos.repo import ErroChaos
    from tools.order import workflows
    _wf(tmp_path, [{"id": "a", "tool": "tool.chaos.read"},
                   {"id": "a", "tool": "tool.chaos.read"}])
    with pytest.raises(ErroChaos):
        workflows.carregar(tmp_path, "w")


def test_workflow_risco_e_o_maior_passo(tmp_path):
    from tools.order import workflows
    _wf(tmp_path, [{"id": "a", "tool": "tool.chaos.read"},
                   {"id": "b", "tool": "tool.notify.send", "resource": "channel:x"}])
    assert workflows.avaliar(tmp_path, "w")["risk_class"] == "A3"


def test_workflow_e_idempotente_por_passo(tmp_path):
    from tools.order import workflows
    _wf(tmp_path, [{"id": "a", "tool": "tool.chaos.read"},
                   {"id": "b", "tool": "tool.chaos.write", "resource": "tasks/"}])
    chamados = []

    def executor(passo, r):
        chamados.append(passo["id"])
        return {"status": "ok"}

    out = workflows.executar(tmp_path, "w", executor=executor, concluidos=["a"])
    assert chamados == ["b"], "passo concluído não é reexecutado"
    assert out["skipped"] == ["a"]


def test_workflow_para_no_passo_que_espera_aprovacao(tmp_path):
    from tools.order import workflows
    _wf(tmp_path, [{"id": "a", "tool": "tool.chaos.read"},
                   {"id": "b", "tool": "tool.notify.send", "resource": "channel:x"},
                   {"id": "c", "tool": "tool.chaos.read"}])

    def executor(passo, r):
        return {"status": "awaiting_approval" if passo["id"] == "b" else "ok"}

    out = workflows.executar(tmp_path, "w", executor=executor)
    assert [r["step"] for r in out["results"]] == ["a", "b"], \
        "para no passo, preservando o que já foi feito"


# --------------------------------------------------------------------------- #
# Assinatura (CHAOS §17.6) — unidades rápidas do módulo que virou a raiz       #
# de confiança depois do spike de 21/09/2026.                                  #
# --------------------------------------------------------------------------- #

import datetime as _dt

from tools.chaos import assinatura


def _escrever_signers(tmp_path, *linhas):
    d = tmp_path / "metadata" / "registries"
    d.mkdir(parents=True, exist_ok=True)
    (d / "allowed_signers").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return tmp_path


def test_opcoes_separadas_por_virgula(tmp_path):
    """
    Espaço entre opções quebra o OpenSSH — foi o primeiro defeito que a
    implementação encontrou na redação de §17.6. O parser aceita as duas
    formas de propósito: se um humano escreveu com espaço, é melhor que o
    validador consiga dizer o que está errado do que engasgar.
    """
    repo = _escrever_signers(
        tmp_path,
        'a@ex.com namespaces="git",valid-after="20200101" ssh-ed25519 AAAA humano')
    linha, = assinatura.ler_allowed_signers(repo)
    assert linha.principal == "a@ex.com"
    assert linha.opcoes == {"namespaces": "git", "valid-after": "20200101"}
    assert linha.tipo == "ssh-ed25519" and linha.chave == "AAAA"
    assert linha.comentario == "humano"


def test_comentario_e_linha_sem_opcoes(tmp_path):
    repo = _escrever_signers(tmp_path,
                             "# comentário no topo",
                             "b@ex.com ssh-ed25519 BBBB")
    linha, = assinatura.ler_allowed_signers(repo)
    assert linha.principal == "b@ex.com" and linha.opcoes == {}


def test_vigencia_por_data():
    l = assinatura.LinhaSigner("a@ex.com", "ssh-ed25519", "AAAA",
                               {"valid-after": "20260101", "valid-before": "20270101"})
    assert not l.vigente_em(_dt.date(2025, 12, 31))
    assert l.vigente_em(_dt.date(2026, 6, 1))
    assert not l.vigente_em(_dt.date(2027, 1, 1)), "valid-before é exclusivo"


def test_data_ilegivel_falha_fechando():
    """
    Uma data que não interpreta vira `date.max`, e portanto "ainda não
    vigente". É a direção certa: erro de parsing nega, nunca concede. A
    tentação é tratar lixo como ausência de restrição — seria a v2.5 de novo,
    onde a ausência de marca era a condição de aprovação.
    """
    l = assinatura.LinhaSigner("a@ex.com", "ssh-ed25519", "AAAA",
                               {"valid-after": "não-é-data"})
    assert not l.vigente_em(_dt.date.today())


def test_veredito_sem_arquivo_nega(tmp_path):
    v = assinatura.verificar_commit(tmp_path)
    assert not v.verificada and not v.eh_humano
    assert "ausente" in v.motivo


def test_estados_de_assinatura_que_nao_bastam():
    """Só `G` conta. `U` e `E` são o que um histórico adulterado produziria."""
    for estado in ("N", "B", "U", "X", "Y", "R", "E"):
        assert assinatura._explicar(estado), f"estado {estado} precisa de explicação"
    assert "sem assinatura" in assinatura._explicar("N")
    assert "INVÁLIDA" in assinatura._explicar("B")
