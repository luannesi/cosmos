"""
Testes de consistência dos próprios contratos — não precisam de implementação.

Os AT verificam o sistema; estes verificam as **especificações**, e rodam hoje.
Cada um deles nasceu de um defeito real encontrado por análise adversarial e
existe para que a mesma classe não volte: nas rodadas 9 e 10, três das quatro
falhas abaixo estavam presentes ao mesmo tempo.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness import GUARD_CASES

SPECS = Path(__file__).resolve().parents[2]


def _latest(prefixo: str) -> Path:
    """
    A spec mais recente por número de versão, não por nome de arquivo fixo.

    Fixar `..._v2.3.md` no código foi o que fez a suíte apontar para a versão
    anterior quando as specs subiram para v2.4 — a mesma classe de defeito que
    nos custou 43 correções aplicadas ao arquivo errado.
    """
    def chave(p: Path):
        m = re.search(r"_v(\d+)\.(\d+)\.md$", p.name)
        return (int(m.group(1)), int(m.group(2))) if m else (-1, -1)

    cands = sorted(SPECS.glob(f"{prefixo}_v*.md"), key=chave)
    return cands[-1] if cands else SPECS / f"{prefixo}_AUSENTE.md"


CHAOS = _latest("CHAOS_Especificacao")
ORDER = _latest("ORDER_Especificacao")
IMPL = _latest("Implementacao_Claude_Nativa")

TIPOS = {"project", "task", "decision", "source", "approval", "automation",
         "handoff", "document", "meeting", "risk", "milestone", "deliverable", "inbox"}


def _skip_if_absent(*paths):
    for p in paths:
        if not p.exists():
            pytest.skip(f"spec não encontrada em {p} — rode a suíte ao lado dos documentos")


def _cli_block(path: Path, sec: int) -> str:
    return re.search(rf"## {sec}\..*?```text\n(.*?)```", path.read_text(encoding="utf-8"),
                     re.S).group(1)


def _declared(blk: str, tool: str) -> set[str]:
    out: set[str] = set()
    for line in blk.splitlines():
        line = line.split("#")[0].strip()
        if not line.startswith(tool):
            continue
        rest = line[len(tool):].strip()
        chunks = rest.split("|") if " | " in rest else [rest]
        for chunk in chunks:
            toks = [t for t in chunk.split() if not t.startswith(("<", "[", "--", '"'))]
            if not toks:
                continue
            out.add(toks[0])
            if len(toks) > 1:
                for sub in toks[1].split("|"):
                    out.add(f"{toks[0]} {sub}")
        toks = [t for t in rest.split() if not t.startswith(("<", "[", "--", '"'))]
        if len(toks) >= 2 and "|" in toks[1]:
            for sub in toks[1].split("|"):
                out.add(f"{toks[0]} {sub}")
        if toks and "|" in toks[0]:
            out.update(toks[0].split("|"))
    return out


def _used(tool: str) -> set[str]:
    u: set[str] = set()
    for f in Path(__file__).parent.glob("test_*_at.py"):
        s = f.read_text(encoding="utf-8")
        u |= {f"{a} {b}" for a, b in re.findall(rf'{tool}\("([a-z]+)",\s*"([a-z-]+)"', s)}
    return u


@pytest.mark.parametrize("tool,spec,sec", [("chaos", CHAOS, 21), ("order", ORDER, 38)])
def test_nenhum_comando_fantasma(tool, spec, sec):
    """
    Todo comando que os AT invocam existe na CLI declarada.

    Rodada 9: oito operações exigidas pelos AT — incluindo `run checkpoint`, de que
    todo o contrato de retomada depende — não existiam em nenhuma lista.
    """
    _skip_if_absent(spec)
    blk = _cli_block(spec, sec)
    decl = _declared(blk, tool)
    generic = {"create", "update", "show", "list"} if "<tipo>" in blk else set()
    ghost = sorted(x for x in _used(tool)
                   if x not in decl and x.split()[0] not in decl
                   and not (x.split()[0] in TIPOS and x.split()[1] in generic))
    assert not ghost, f"comandos `{tool}` usados pelos AT e não declarados em §{sec}: {ghost}"


def test_binding_nao_declara_cli_paralela():
    """
    A Implementação referencia as CLIs; não mantém listas próprias.

    Rodadas 9 e 10: as duas listas paralelas divergiram — `order` com 22 comandos
    de cada lado e só 10 em comum; `chaos` sem declarar `commit` nem `sync`, que
    são o único caminho de commit de agente.
    """
    _skip_if_absent(IMPL)
    txt = IMPL.read_text(encoding="utf-8")
    sec = txt[txt.index("## 11. CLIs"):txt.index("## 12.")]
    for tool, alvo in (("chaos", "CHAOS §21"), ("order", "ORDER §38")):
        linha = re.search(rf"^`{tool}`: (.+)$", sec, re.M)
        assert linha, f"§11 deve dizer de onde vem a CLI do `{tool}`"
        assert alvo in linha.group(1), \
            f"§11 deve referenciar {alvo} em vez de listar comandos de `{tool}`"


def test_guard_cases_cobrem_o_minimo_da_spec():
    """
    `GUARD_CASES` cobre todas as classes enumeradas em ORDER §16.

    Rodada 10: a spec exigia seis classes mínimas e a tabela cobria cinco — a
    suíte não verificava o mínimo que a própria spec declara obrigatório.
    """
    _skip_if_absent(ORDER)
    txt = ORDER.read_text(encoding="utf-8")
    tabela = txt[txt.index("Casos mínimos de negação"):]
    tabela = tabela[:tabela.index("- protected paths incluem")]
    classes = {re.sub(r"[`*]", "", c).strip()
               for c in re.findall(r"^\s*\|\s*([^|]+?)\s*\|", tabela, re.M)}
    classes -= {"Caso", "---"}

    esperado = {"Família": None, "interpretador": "interpretador",
                "redirecionamento": "redirecionamento", "editor em lugar": "editor",
                "git de escrita": "git", "protected path": "protected",
                "audit/ direto": "audit", "shell aninhado": "shell-aninhado"}
    for classe in classes:
        if classe not in esperado:
            raise AssertionError(f"classe `{classe}` de §16 não mapeada na suíte — atualize GUARD_CASES")
        chave = esperado[classe]
        if chave is None:
            continue                      # cabeçalho da tabela
        assert any(c[0].startswith(chave) for c in GUARD_CASES), \
            f"§16 exige a classe `{classe}` e GUARD_CASES não a cobre"

    # A tabela é por família, não por plataforma: as duas colunas têm de estar cobertas.
    ids = {c[0] for c in GUARD_CASES}
    assert any("powershell" in i for i in ids) and any("cmd" in i for i in ids), \
        "GUARD_CASES cobre só POSIX — no Windows o guard seria contornado com powershell/cmd"


@pytest.mark.parametrize("spec,sec_at,sec_dod", [(CHAOS, 30, 32), (ORDER, 44, 45)])
def test_dod_nao_fixa_faixa_de_at(spec, sec_at, sec_dod):
    """
    A Definition of Done exige a suíte inteira, sem faixa numérica.

    Rodada 7 criou a regra; a rodada 8 descobriu que a própria correção ainda
    enunciava "AT-01 a AT-24" ao lado da frase que proibia faixas.
    """
    _skip_if_absent(spec)
    txt = spec.read_text(encoding="utf-8")
    dod = txt[txt.index(f"## {sec_dod}. Definition of Done"):]
    dod = dod.split("\n## ")[0]
    assert not re.search(r"AT-\d+\s+a\s+AT-\d+\s+passam", dod), \
        "a DoD fixa faixa numérica: acrescentar um AT a quebra em silêncio"
    assert re.search(rf"Acceptance Tests de §{sec_at}", dod), \
        f"a DoD deve exigir toda a suíte de §{sec_at}"


@pytest.mark.parametrize("spec,sec,total", [(CHAOS, 30, 38), (ORDER, 44, 32)])
def test_at_numerados_sem_lacuna(spec, sec, total):
    """AT sequenciais e sem duplicata — e a suíte cobre todos."""
    _skip_if_absent(spec)
    txt = spec.read_text(encoding="utf-8")
    nums = [int(n) for n in re.findall(r"^- \*\*AT-(\d+)", txt, re.M)]
    assert nums == list(range(1, total + 1)), f"§{sec}: numeração dos AT quebrada: {nums}"

    nome = "CHAOS" if spec is CHAOS else "ORDER"
    arquivo = Path(__file__).parent / f"test_{nome.lower()}_at.py"
    cobertos = {int(n) for n in re.findall(rf'@pytest\.mark\.at\("{nome}", (\d+)\)',
                                           arquivo.read_text(encoding="utf-8"))}
    assert cobertos == set(nums), f"AT sem teste em {arquivo.name}: {sorted(set(nums) - cobertos)}"


def test_camada_episodica_nunca_e_fonte():
    """
    A não-canonicidade da camada episódica é afirmada nas três specs.

    Nasceu da adoção do componente de terceiro: a garantia de que toda escrita
    canônica é classificada e auditada só sobrevive se o store não governado
    ficar declaradamente fora do canônico — em CHAOS §4.2, em ORDER §24 e no
    binding. Uma das três esquecendo disso é como a garantia se perde em silêncio.
    """
    _skip_if_absent(CHAOS, ORDER, IMPL)
    c = CHAOS.read_text(encoding="utf-8")
    o = ORDER.read_text(encoding="utf-8")
    i = IMPL.read_text(encoding="utf-8")

    assert "### 4.2 Camada episódica" in c, "CHAOS deve definir a camada episódica em §4.2"
    assert "chaos promote" in c, "CHAOS §21 deve declarar o único caminho de promoção"
    assert re.search(r"MUST NOT.{0,400}canônic", c, re.S | re.I),         "CHAOS §4.2 deve proibir conteúdo canônico na camada episódica"
    assert "episodic" in o and "nenhuma" in o,         "ORDER §24 deve declarar a camada episódica sem autoridade"
    assert "ai-memory" in i and "não é fonte" in i.replace("nao é fonte", "não é fonte"),         "o binding deve nomear o componente e declarar que ele não é fonte"


def test_degradacao_da_camada_episodica_declarada():
    """Componente novo sem linha de degradação vira dependência estrutural por omissão."""
    _skip_if_absent(CHAOS, ORDER)
    o = ORDER.read_text(encoding="utf-8")
    deg = o[o.index("## 40. Graceful Degradation"):].split("\n## ")[0]
    assert "camada episódica" in deg, "ORDER §40 deve declarar a degradação sem a camada episódica"
    c = CHAOS.read_text(encoding="utf-8")
    assert "AT-34" in c, "CHAOS deve ter o AT que prova que a camada é dispensável"
