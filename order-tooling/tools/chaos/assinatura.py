"""
Assinatura — a raiz de confiança do sistema (CHAOS §17.6).

Este módulo existe por causa de um resultado experimental, não de uma análise.
O spike de identidade de 21/09/2026 mediu o runtime real e encontrou duas
coisas em direções opostas:

  - a sessão na nuvem escolhe livremente autor e committer do commit;
  - a sessão na nuvem NÃO consegue assinar.

A primeira matou a regra "commit humano = identidade humana e ausência de
trailer": as duas metades são texto que o executor escreve. A segunda deu o
substituto. Daí a inversão de polaridade que governa este arquivo inteiro:

    autoria humana é provada pela PRESENÇA de uma marca que o executor não
    produz, nunca pela AUSÊNCIA de uma marca que qualquer um omite.

Consequência prática para quem for mexer aqui: toda função deste módulo falha
FECHANDO. Erro de leitura, arquivo ausente, git antigo, assinatura ilegível —
tudo resulta em "não é humano". Um `except` que devolva `True` neste arquivo
reabre, sozinho, o buraco que o spike encontrou.
"""
from __future__ import annotations

import datetime as _dt
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import yamlio
from .repo import ErroChaos

REL_ALLOWED_SIGNERS = "metadata/registries/allowed_signers"

# Nomes que denunciam chave privada em caminho versionado (§15 da Implementação).
PADROES_CHAVE_PRIVADA = ("*.pem", "*.key", "id_rsa", "id_ecdsa", "id_ed25519",
                         "*.ppk", "*_rsa", "*_ed25519")
_CABECALHOS_PRIVADOS = (
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN PGP PRIVATE KEY BLOCK-----",
)


# --------------------------------------------------------------------------
# allowed_signers
# --------------------------------------------------------------------------

@dataclass
class LinhaSigner:
    """Uma linha do allowed_signers, já interpretada."""
    principal: str
    tipo: str
    chave: str
    opcoes: dict = field(default_factory=dict)
    comentario: str = ""
    bruto: str = ""

    def vigente_em(self, quando: _dt.date) -> bool:
        """§17.6: revogar é expirar com `valid-before`, nunca apagar."""
        depois = self.opcoes.get("valid-after")
        antes = self.opcoes.get("valid-before")
        if depois and quando < _data(depois):
            return False
        if antes and quando >= _data(antes):
            return False
        return True


def _data(txt: str) -> _dt.date:
    txt = txt.strip().strip('"')[:8]
    try:
        return _dt.date(int(txt[0:4]), int(txt[4:6]), int(txt[6:8]))
    except (ValueError, IndexError):
        # Falha fechando: data ilegível vira "muito no futuro", nunca "vigente".
        return _dt.date.max


_RE_OPCAO = re.compile(r'([a-z-]+)(?:="([^"]*)")?')


def _data_iso(txt: str) -> _dt.date:
    """`--date=short` devolve YYYY-MM-DD; ausência vira hoje."""
    txt = (txt or "").strip()
    try:
        return _dt.date.fromisoformat(txt)
    except ValueError:
        return _dt.date.today()


def ler_allowed_signers(repo: Path) -> list[LinhaSigner]:
    caminho = repo / REL_ALLOWED_SIGNERS
    if not caminho.exists():
        return []
    linhas: list[LinhaSigner] = []
    for bruto in caminho.read_text(encoding="utf-8").splitlines():
        linha = bruto.strip()
        if not linha or linha.startswith("#"):
            continue
        partes = linha.split()
        if len(partes) < 3:
            continue
        principal = partes[0]
        resto = partes[1:]
        opcoes: dict = {}
        # As opções, quando existem, vêm antes do tipo da chave.
        while resto and not resto[0].startswith(("ssh-", "sk-", "ecdsa-")):
            for chave, valor in _RE_OPCAO.findall(resto[0]):
                opcoes[chave] = valor
            resto = resto[1:]
        if len(resto) < 2:
            continue
        linhas.append(LinhaSigner(principal=principal, tipo=resto[0], chave=resto[1],
                                  opcoes=opcoes, comentario=" ".join(resto[2:]),
                                  bruto=linha))
    return linhas


def papel_do_principal(repo: Path, principal: str) -> str | None:
    """
    principal (e-mail do signatário) -> ator (`human:owner`, `executor:...`).

    A fonte é `executors.yaml`, que é registro de ATRIBUIÇÃO. Aqui ele responde
    uma pergunta diferente da de §17.1: não "quem diz ter feito", mas "a que
    papel esta chave pertence". Continua sendo o registro certo porque é
    protected path — quem o edita já podia tudo.
    """
    if not principal:
        return None
    alvo = principal.strip().lower()
    dados = yamlio.ler_yaml(repo / "metadata" / "registries" / "executors.yaml")
    for e in (dados or {}).get("executors", []) if isinstance(dados, dict) else []:
        cands = [str(e.get("signing_principal") or "").strip().lower(),
                 str(e.get("git_identity") or "").strip().lower()]
        if alvo in [c for c in cands if c]:
            return str(e.get("id") or "") or None
    return None


def ha_chave_humana(repo: Path, quando: _dt.date | None = None) -> bool:
    """Existe ao menos uma chave `human:*` vigente? Decide a degradação (AT-37)."""
    quando = quando or _dt.date.today()
    for linha in ler_allowed_signers(repo):
        if not linha.vigente_em(quando):
            continue
        papel = papel_do_principal(repo, linha.principal)
        if papel and papel.startswith("human:"):
            return True
    return False


# --------------------------------------------------------------------------
# Verificação de commit
# --------------------------------------------------------------------------

@dataclass
class Veredito:
    verificada: bool
    principal: str = ""
    ator: str = ""
    estado: str = "N"      # %G? do git: G bom, B ruim, U/X/Y/R parciais, E erro, N ausente
    motivo: str = ""

    @property
    def eh_humano(self) -> bool:
        return self.verificada and self.ator.startswith("human:")

    @property
    def eh_worker(self) -> bool:
        return self.verificada and self.ator.startswith("executor:")


def verificar_commit(repo: Path, ref: str = "HEAD") -> Veredito:
    """
    Veredito de um commit. Falha fechando em todos os caminhos de erro.

    `%G?` = estado da assinatura; `%GS` = principal do signatário. Só `G`
    conta: `U` (boa, validade desconhecida) e `E` (não verificável) são
    exatamente o que um histórico adulterado produziria, e tratá-los como
    sucesso anularia o propósito.
    """
    caminho = repo / REL_ALLOWED_SIGNERS
    if not caminho.exists():
        return Veredito(False, motivo=f"{REL_ALLOWED_SIGNERS} ausente — "
                                      "nenhuma chave registrada (§17.6)")
    p = subprocess.run(
        ["git", "-c", "gpg.format=ssh",
         "-c", f"gpg.ssh.allowedSignersFile={caminho}",
         "log", "-1", "--date=short", "--format=%G?%x1f%GS%x1f%ad", ref],
        cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        return Veredito(False, motivo=f"git não leu `{ref}`: {p.stderr.strip()}")
    bruto = p.stdout.strip("\n")
    partes = bruto.split("\x1f")
    estado = (partes[0] if partes else "N").strip() or "N"
    principal = (partes[1] if len(partes) > 1 else "").strip()
    quando = _data_iso(partes[2] if len(partes) > 2 else "")
    if estado != "G":
        return Veredito(False, estado=estado, principal=principal,
                        motivo=_explicar(estado))
    papel = papel_do_principal(repo, principal)
    if not papel:
        return Veredito(False, estado=estado, principal=principal,
                        motivo=f"assinatura verifica, mas o principal "
                               f"`{principal}` não tem papel em executors.yaml")
    # A vigência é avaliada na DATA DO COMMIT, não em hoje. É o que torna
    # `valid-before` uma revogação e não uma reescrita do passado: expirar uma
    # chave impede novos commits, e deixa os antigos verificando — que é
    # exatamente a diferença entre revogar e adulterar (§17.6, AT-38).
    vigentes = [l for l in ler_allowed_signers(repo)
                if l.principal.strip().lower() == principal.strip().lower()
                and l.vigente_em(quando)]
    if not vigentes:
        return Veredito(False, estado=estado, principal=principal, ator=papel,
                        motivo=f"chave de `{principal}` não estava vigente em "
                               f"{quando.isoformat()} (valid-after/valid-before)")
    return Veredito(True, principal=principal, ator=papel, estado=estado,
                    motivo="assinatura verificada")


def _explicar(estado: str) -> str:
    return {
        "N": "commit sem assinatura — conta como executor (§17.6)",
        "B": "assinatura INVÁLIDA — histórico adulterado ou chave trocada",
        "U": "assinatura boa mas de validade desconhecida — não basta",
        "X": "assinatura de chave expirada",
        "Y": "assinatura feita por chave que expirou depois",
        "R": "assinatura de chave revogada",
        "E": "assinatura não verificável — chave ausente do allowed_signers",
    }.get(estado, f"estado de assinatura `{estado}` não reconhecido")


def exigir_humana(repo: Path, ref: str = "HEAD", acao: str = "esta ação") -> Veredito:
    """
    Portão de A4 e de protected path. Erra para o lado de negar.

    A mensagem nomeia o caso que o spike produziu, porque é o erro que um
    implementador comete naturalmente: achar que autor humano basta.
    """
    v = verificar_commit(repo, ref)
    if v.eh_humano:
        return v
    if v.eh_worker:
        raise ErroChaos(
            f"{acao} exige assinatura HUMANA; o commit `{ref}` está assinado "
            f"pelo worker (`{v.ator}`). Worker prova procedência, não "
            "consentimento (ORDER §18) — um worker que assina sem presença é "
            "um oráculo de assinatura.", "integrity")
    raise ErroChaos(
        f"{acao} exige commit assinado por chave `human:*` (CHAOS §17.6). "
        f"Commit `{ref}`: {v.motivo}. Autor e committer humanos NÃO bastam — "
        "o spike de 21/09/2026 mostrou que o executor na nuvem produz os dois "
        "com dois comandos.", "integrity")


# --------------------------------------------------------------------------
# Higiene: chave privada não entra em caminho versionado
# --------------------------------------------------------------------------

def achar_chaves_privadas(repo: Path) -> list[str]:
    """Um repositório que contenha a chave que o autoriza não autoriza nada."""
    p = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        return []
    achados = []
    for rel in p.stdout.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        caminho = repo / rel
        try:
            if caminho.stat().st_size > 64 * 1024:
                continue
            inicio = caminho.read_text(encoding="utf-8", errors="ignore")[:200]
        except OSError:
            continue
        if any(h in inicio for h in _CABECALHOS_PRIVADOS):
            achados.append(rel)
    return achados


# --------------------------------------------------------------------------
# Vigência: a partir de quando exigir assinatura
# --------------------------------------------------------------------------

def commit_da_primeira_chave_humana(repo: Path) -> str:
    """
    O commit em que a raiz de confiança passou a existir.

    Antes dele, nenhum commit PODIA ser assinado — inclusive o `chaos init`,
    que cria o próprio `allowed_signers`. Exigir assinatura desses commits
    seria exigir que o sistema existisse antes de ser criado, e o efeito
    prático seria que nenhum repositório novo passaria no validador.

    O commit que registra a primeira chave é ele próprio isento, e é o único.
    Isso é uma concessão consciente e de janela única: quem escreve a primeira
    linha define quem é humano. §17.6 a fecha do lado certo — ela acontece no
    Onboarding, antes de existir agente algum. A partir do segundo commit no
    arquivo, a regra passa a valer sobre ele mesmo.
    """
    p = subprocess.run(["git", "log", "--reverse", "--format=%H", "--",
                        REL_ALLOWED_SIGNERS],
                       cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        return ""
    for rev in p.stdout.split():
        conteudo = subprocess.run(["git", "show", f"{rev}:{REL_ALLOWED_SIGNERS}"],
                                  cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if conteudo.returncode != 0:
            continue
        for linha in conteudo.stdout.splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            principal = linha.split()[0]
            papel = papel_do_principal(repo, principal)
            if papel and papel.startswith("human:"):
                return rev
    return ""


def commits_apos(repo: Path, rev: str) -> set[str]:
    """Commits alcançáveis de HEAD e não de `rev` — o período sob a regra."""
    p = subprocess.run(["git", "rev-list", f"{rev}..HEAD"],
                       cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return set(p.stdout.split()) if p.returncode == 0 else set()
