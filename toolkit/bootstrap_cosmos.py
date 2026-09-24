#!/usr/bin/env python3
"""
bootstrap_cosmos.py — instalador retomável de um novo repositório CHAOS/ORDER pessoal.

Cobre as Partes 1 a 6 do runbook (TUTORIAL_Instalacao_e_Configuracao.md /
EXECUTAR_COSMOS.md), na ordem que a primeira instalação real (23/09/2026)
provou que funciona — inclusive os desvios que o runbook escrito não previa
(order-tooling/ACHADOS.md, achados 26 a 29: invólucro .cmd no Windows, o
bootstrap circular do Onboarding, o default de lista virando string, e o
`-m order.worker` que nunca existiu).

O que este script NUNCA faz, de propósito:
  - não lê, não gera, não guarda frase-secreta de chave humana — ela é
    sempre digitada direto no prompt do `ssh-keygen`/`git commit`, com
    stdio herdado do terminal; este processo nunca a vê;
  - não inventa resposta de Onboarding — cada pergunta sem valor já
    registrado é perguntada a você, exatamente como `chaos onboarding run`
    interativo faria (Implementação §3: "nada é assumido do histórico");
  - não commita nada em seu nome sem te mostrar o que vai commitar.

Retomada: se a execução parar (erro, Ctrl+C, falta de energia), rodar de
novo pergunta se quer continuar de onde parou ou recomeçar. Recomeçar não
apaga as respostas já dadas — elas voltam como SUGESTÃO em cada pergunta,
nunca aceitas em silêncio. O estado fica em ~/.cosmos/bootstrap/, fora de
qualquer repositório Git — nunca é commitado, nunca é enviado a lugar
nenhum, e não guarda nada da lista de "dados sensíveis" abaixo.

Dados nunca gravados no arquivo de estado (nem em qualquer outro lugar por
este script): frase-secreta, conteúdo de chave privada, token/PAT.
E-mails, nomes de área, identificador do dono etc. SÃO gravados — não são
segredo, são a personalização de cada instalação, e é exatamente isso que
permite sugerir em vez de perguntar nesta máquina de novo.

Uso:
    python3 bootstrap_cosmos.py --repo-dir D:\\personal-assistant --cosmos-dir D:\\cosmos

Em qualquer pergunta, Ctrl+C interrompe com segurança — o que já foi
gravado em disco continua lá, e a próxima execução retoma dali.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml  # PyYAML — usado só para escrever o arquivo de respostas do onboarding
except ImportError:
    yaml = None


# --------------------------------------------------------------------------- #
# estado retomável                                                            #
# --------------------------------------------------------------------------- #

def _state_path(repo_dir: Path) -> Path:
    base = Path.home() / ".cosmos" / "bootstrap"
    base.mkdir(parents=True, exist_ok=True)
    # a chave inclui um hash do caminho absoluto — dois repositórios com o
    # mesmo nome final em pastas diferentes não colidem no mesmo estado
    chave = hashlib.sha1(str(repo_dir.resolve()).encode("utf-8")).hexdigest()[:10]
    return base / f"{repo_dir.name}-{chave}.json"


class Estado:
    """
    completed:  passos já concluídos — permite pular na retomada.
    answers:    respostas não sensíveis já dadas. Sobrevive a "recomeçar":
                só vira sugestão, nunca é aceito sem confirmação.
    """

    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.data = {"completed": [], "answers": {}}
        else:
            self.data = {"completed": [], "answers": {}}
        self.data.setdefault("completed", [])
        self.data.setdefault("answers", {})

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    def done(self, passo: str) -> bool:
        return passo in self.data["completed"]

    def marcar(self, passo: str) -> None:
        if passo not in self.data["completed"]:
            self.data["completed"].append(passo)
        self.save()

    def reiniciar_progresso(self) -> None:
        """'Recomeçar do zero': limpa o que foi concluído, mas MANTÉM as
        respostas já dadas como sugestão — é o comportamento pedido."""
        self.data["completed"] = []
        self.save()

    def resposta(self, chave: str, default=None):
        return self.data["answers"].get(chave, default)

    def gravar(self, chave: str, valor) -> None:
        self.data["answers"][chave] = valor
        self.save()


# --------------------------------------------------------------------------- #
# prompts                                                                     #
# --------------------------------------------------------------------------- #

def perguntar(texto: str, default: str | None = None, obrigatoria: bool = False) -> str:
    sufixo = f" [{default}]" if default not in (None, "") else ""
    while True:
        try:
            resp = input(f"  {texto}{sufixo}\n  > ").strip()
        except EOFError:
            resp = ""
        if resp:
            return resp
        if default is not None:
            return default
        if not obrigatoria:
            return ""
        print("  (obrigatório — digite algo, sem default pra aceitar)")


def confirmar(texto: str, default: bool = True) -> bool:
    sufixo = " [S/n]" if default else " [s/N]"
    try:
        resp = input(f"{texto}{sufixo} ").strip().lower()
    except EOFError:
        resp = ""
    if not resp:
        return default
    return resp in ("s", "sim", "y", "yes")


def secao(titulo: str) -> None:
    print(f"\n== {titulo} ==")


# --------------------------------------------------------------------------- #
# processos                                                                   #
# --------------------------------------------------------------------------- #

class ErroPasso(RuntimeError):
    pass


def rodar(cmd: list[str], cwd: Path | None = None, check: bool = True,
          herdar_stdio: bool = False) -> subprocess.CompletedProcess:
    """
    herdar_stdio=True é para comandos que precisam de prompt interativo real
    no terminal (ssh-keygen pedindo frase-secreta, git commit que vai
    assinar): a frase-secreta nunca passa por este script porque o processo
    filho fala direto com o terminal, sem stdio capturado.
    """
    try:
        if herdar_stdio:
            p = subprocess.run(cmd, cwd=cwd)
            saida = ""
        else:
            p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
            saida = (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        # subprocess.run levanta FileNotFoundError quando o EXECUTÁVEL em si
        # não existe -- diferente de rodar e devolver código != 0. Quem chama
        # rodar(..., check=False) pra só perguntar "essa ferramenta existe?"
        # (ex.: `gh --version`, já que gh não vem no pacote) espera testar
        # p.returncode, não levar uma exceção não tratada (achado 40).
        saida = f"`{cmd[0]}` não encontrado no PATH"
        p = subprocess.CompletedProcess(cmd, returncode=127, stdout="", stderr=saida)
    if check and p.returncode != 0:
        raise ErroPasso(f"`{' '.join(cmd)}` falhou (código {p.returncode}):\n{saida.strip()}")
    return p


def chaos_json(bin_chaos: Path, repo_dir: Path, *args: str, check: bool = True) -> dict:
    p = rodar([sys.executable, str(bin_chaos), *args], cwd=repo_dir, check=check)
    texto = (p.stdout or "").strip()
    try:
        return json.loads(texto) if texto else {}
    except json.JSONDecodeError:
        raise ErroPasso(f"`chaos {' '.join(args)}` não devolveu JSON:\n{texto}\n{p.stderr}")


def git_config_get(repo_dir: Path | None, chave: str, global_: bool = False) -> str:
    cmd = ["git", "config"] + (["--global"] if global_ else []) + ["--get", chave]
    p = rodar(cmd, cwd=repo_dir, check=False)
    return (p.stdout or "").strip()


def git_config_set(repo_dir: Path | None, chave: str, valor: str, global_: bool = False) -> None:
    cmd = ["git", "config"] + (["--global"] if global_ else []) + [chave, valor]
    rodar(cmd, cwd=repo_dir)


# --------------------------------------------------------------------------- #
# Parte 1 — software                                                          #
# --------------------------------------------------------------------------- #

def passo_software(estado: Estado, repo_dir: Path) -> None:
    secao("Parte 1 — Software")
    v = sys.version_info
    print(f"  Python {v.major}.{v.minor}.{v.micro}"
          + (" — ok" if v >= (3, 11) else " — ATENÇÃO: recomenda-se 3.11+"))

    p = rodar(["git", "--version"], check=False)
    if p.returncode != 0:
        raise ErroPasso("Git não encontrado — instale antes de continuar (§1.1).")
    print(f"  {p.stdout.strip()}")

    if platform.system() == "Windows":
        atual = git_config_get(None, "credential.helper", global_=True)
        if not atual:
            print("  credential.helper não configurado — clone/push vão falhar com "
                  "'could not read Username' na primeira tentativa (§1.2.1).")
            if confirmar("  Configurar 'git config --global credential.helper manager' agora?"):
                git_config_set(None, "credential.helper", "manager", global_=True)
                print("  ok.")
        else:
            print(f"  credential.helper: {atual}")

    estado.marcar("software")


# --------------------------------------------------------------------------- #
# Parte 2 — chaves SSH                                                        #
# --------------------------------------------------------------------------- #

def _ssh_dir() -> Path:
    return Path.home() / ".ssh"


def passo_chaves_ssh(estado: Estado) -> tuple[Path, Path]:
    """Devolve (caminho_pub_humana, caminho_pub_worker). Gera o que faltar."""
    secao("Parte 2 — Chaves de assinatura")
    ssh_dir = _ssh_dir()
    ssh_dir.mkdir(parents=True, exist_ok=True)

    humana = ssh_dir / "chaos-humano"
    worker = ssh_dir / "chaos-worker"

    if not (ssh_dir / "chaos-humano.pub").exists():
        print("  Chave HUMANA não encontrada — vou gerar. Ela PRECISA de frase-secreta:")
        print("  sem isso, qualquer processo nesta máquina assina como você (§17.6).")
        principal_sugerido = estado.resposta("human_signing_principal", "")
        principal = perguntar("  E-mail/principal pra chave humana (vai no -C)",
                               default=principal_sugerido or None, obrigatoria=True)
        estado.gravar("human_signing_principal", principal)
        rodar(["ssh-keygen", "-t", "ed25519", "-f", str(humana), "-C", principal],
              herdar_stdio=True)
        if not (ssh_dir / "chaos-humano.pub").exists():
            raise ErroPasso("ssh-keygen não gerou a chave humana — confira a saída acima.")
    else:
        print(f"  Chave humana já existe: {humana}.pub")

    if not (ssh_dir / "chaos-worker.pub").exists():
        print("  Chave do WORKER não encontrada — gerando SEM frase-secreta (§1.2.2: "
              "ela prova procedência, nunca consentimento — não pode travar um processo "
              "sem ninguém por perto pra digitar senha).")
        principal_sugerido = estado.resposta("worker_signing_principal", "worker@chaos.local")
        principal = perguntar("  E-mail/principal pra chave do worker",
                               default=principal_sugerido)
        estado.gravar("worker_signing_principal", principal)
        rodar(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(worker), "-C", principal],
              herdar_stdio=True)
        if not (ssh_dir / "chaos-worker.pub").exists():
            raise ErroPasso("ssh-keygen não gerou a chave do worker — confira a saída acima.")
    else:
        print(f"  Chave do worker já existe: {worker}.pub")

    segunda = estado.resposta("segunda_chave_humana_pub", "")
    if not segunda:
        print("\n  Segunda chave humana (redundância, §2.3): sem ela, perder esta máquina "
              "é perder a capacidade de aprovar qualquer coisa A4 — registrar chave nova "
              "exigiria assinatura da que se perdeu.")
        if confirmar("  Já tem uma segunda chave humana gerada em outra mídia?", default=False):
            segunda = perguntar("  Caminho completo do .pub dela", obrigatoria=True)
            estado.gravar("segunda_chave_humana_pub", segunda)
        else:
            print("  Ok — pode gerar depois com o mesmo comando, em outra mídia, e "
                  "registrar com `chaos key register` (não bloqueia o resto agora).")

    estado.gravar("human_pub", str(ssh_dir / "chaos-humano.pub"))
    estado.gravar("worker_pub", str(ssh_dir / "chaos-worker.pub"))
    estado.marcar("chaves_ssh")
    return ssh_dir / "chaos-humano.pub", ssh_dir / "chaos-worker.pub"


# --------------------------------------------------------------------------- #
# Parte 2 — repositório remoto                                                #
# --------------------------------------------------------------------------- #

def passo_repo_remoto(estado: Estado, repo_dir: Path) -> str:
    secao("Parte 2 — Repositório remoto")
    sugestao = estado.resposta("remote_url", "")
    if sugestao:
        print(f"  Já tinha um remoto anotado desta tentativa: {sugestao}")
        if confirmar("  Usar este?"):
            estado.marcar("repo_remoto")
            return sugestao

    p = rodar(["gh", "--version"], check=False)
    tem_gh = p.returncode == 0
    if not tem_gh:
        print("  GitHub CLI (`gh`) não encontrado — crie o repositório manualmente no "
              "GitHub: PRIVADO e VAZIO (sem README/.gitignore/licença — qualquer arquivo "
              "inicial cria um commit que não é seu e atrapalha o passo de assinatura).")
        url = perguntar("  URL do repositório remoto (https://github.com/usuario/nome.git)",
                         obrigatoria=True)
        estado.gravar("remote_url", url)
        estado.marcar("repo_remoto")
        return url

    nome_sugerido = estado.resposta("remote_name", repo_dir.name)
    nome = perguntar("  Nome do repositório no GitHub", default=nome_sugerido)
    estado.gravar("remote_name", nome)

    v = rodar(["gh", "repo", "view", nome], check=False)
    if v.returncode == 0:
        print(f"  Repositório '{nome}' já existe no GitHub — usando ele.")
    else:
        if confirmar(f"  Repositório '{nome}' não existe ainda — criar como privado e vazio?"):
            rodar(["gh", "repo", "create", nome, "--private"])
        else:
            raise ErroPasso("sem repositório remoto não dá pra prosseguir com o push depois "
                             "— rode de novo quando tiver criado.")

    url_p = rodar(["gh", "repo", "view", nome, "--json", "url", "-q", ".url"], check=False)
    url = (url_p.stdout or "").strip()
    if not url:
        url = perguntar("  URL do repositório (não consegui detectar via gh)", obrigatoria=True)
    else:
        url = url + ".git" if not url.endswith(".git") else url
    estado.gravar("remote_url", url)
    estado.marcar("repo_remoto")
    return url


# --------------------------------------------------------------------------- #
# Parte 4.2 — chaos init                                                      #
# --------------------------------------------------------------------------- #

def passo_chaos_init(estado: Estado, repo_dir: Path, cosmos_dir: Path) -> Path:
    """Devolve o caminho do `bin/chaos` A USAR DAQUI EM DIANTE — o vendorizado
    dentro do próprio repositório, não mais o do clone de `cosmos`."""
    secao("Parte 4.2 — Inicializando o repositório")
    repo_dir.mkdir(parents=True, exist_ok=True)

    if not (repo_dir / ".git").exists():
        rodar(["git", "init", "-b", "main"], cwd=repo_dir)
        print("  git init ok.")

    bin_chaos_vendorizado = repo_dir / "bin" / "chaos"
    if (repo_dir / "metadata" / "repo.yaml").exists():
        print("  Já inicializado (metadata/repo.yaml existe) — pulando `chaos init`.")
        estado.marcar("chaos_init")
        return bin_chaos_vendorizado

    bin_chaos_cosmos = cosmos_dir / "order-tooling" / "bin" / "chaos"
    if not bin_chaos_cosmos.exists():
        raise ErroPasso(f"não achei {bin_chaos_cosmos} — confirme --cosmos-dir")

    classe = perguntar("  Classe de privacidade (privacy_class)",
                        default=estado.resposta("privacy_class", "pessoal"))
    estado.gravar("privacy_class", classe)
    owner_sugerido = estado.resposta("owner_id", "")
    if not owner_sugerido:
        nome = perguntar("  Seu identificador (só o nome/apelido, sem 'human:' — "
                          "eu completo)", obrigatoria=True)
        owner_sugerido = f"human:{nome.strip().lower()}"
    owner = perguntar("  Identificador do proprietário (formato human:<algo>)",
                       default=owner_sugerido)
    if not owner.startswith("human:"):
        print(f"  Precisa começar com 'human:' — usando 'human:{owner}'.")
        owner = f"human:{owner}"
    estado.gravar("owner_id", owner)

    chaos_json(bin_chaos_cosmos, repo_dir, "init", "--privacy-class", classe, "--owner", owner)
    print(f"  chaos init ok — classe={classe} owner={owner}")
    estado.marcar("chaos_init")
    return bin_chaos_vendorizado


def passo_config_assinatura_local(estado: Estado, repo_dir: Path, human_pub: Path) -> None:
    secao("Configurando assinatura local (só este repositório, não sua config global)")
    # gpg.format e allowedSignersFile já vêm do `chaos init`; falta a chave e
    # o gatilho automático — sem isso, TODO commit humano feito pelo
    # chaos/order sai sem assinar (achado descoberto na primeira instalação
    # real: a ferramenta nunca assina em nome do humano por design — §17.6 —
    # e depende inteiramente desta configuração).
    git_config_set(repo_dir, "user.signingkey", str(human_pub))
    git_config_set(repo_dir, "commit.gpgsign", "true")
    print(f"  user.signingkey={human_pub}")
    print("  commit.gpgsign=true")
    estado.marcar("config_assinatura")


# --------------------------------------------------------------------------- #
# Parte 4.3 — onboarding                                                      #
# --------------------------------------------------------------------------- #

def passo_onboarding(estado: Estado, repo_dir: Path, bin_chaos: Path) -> None:
    secao("Parte 4.3 — Onboarding")
    marcador = repo_dir / "reports" / ".onboarding-confirmado"
    if marcador.exists():
        print("  Já confirmado (reports/.onboarding-confirmado existe) — pulando.")
        estado.marcar("onboarding")
        return

    if yaml is None:
        raise ErroPasso("PyYAML não instalado (`pip install pyyaml`) — necessário pra "
                         "escrever o arquivo de respostas do onboarding sem depender do "
                         "modo interativo nativo do `chaos`.")

    perguntas = chaos_json(bin_chaos, repo_dir, "onboarding", "questions")

    respostas_prontas: dict = estado.resposta("onboarding_respostas", {}) or {}
    bloco_atual = ""
    for q in perguntas:
        chave = q["chave"]
        if chave in respostas_prontas:
            continue  # já coletada numa tentativa anterior desta mesma rodada
        if q["bloco"] != bloco_atual:
            bloco_atual = q["bloco"]
            print(f"\n  — {bloco_atual} —")

        sugestao = estado.resposta(f"onboarding.{chave}", None)
        default_mostrado = sugestao if sugestao is not None else q.get("default")
        origem = " (sua resposta anterior)" if sugestao is not None else ""

        texto = q["pergunta"]
        if q.get("opcoes"):
            texto += f" [{' | '.join(q['opcoes'])}]"
        bruto = perguntar(f"{texto}{origem}", default=default_mostrado,
                           obrigatoria=q.get("obrigatoria", False) and default_mostrado is None)

        # `chaos onboarding questions` não devolve se a pergunta é de lista
        # (o JSON não tem esse campo — só `chave, pergunta, destino, default,
        # opcoes, bloco, obrigatoria`). Não precisamos adivinhar aqui: o
        # arquivo --answers é lido por `coletar()`, cujo ramo `prefixadas`
        # já faz `valor.split(",")` pra qualquer pergunta de lista quando o
        # valor chega como string (achado 28 cobriu só o caminho interativo
        # de aceitar o default com Enter — este caminho, --answers, sempre
        # funcionou certo). Basta gravar a string tal como digitada.
        valor = bruto

        respostas_prontas[chave] = valor
        estado.gravar(f"onboarding.{chave}", valor)
        estado.gravar("onboarding_respostas", respostas_prontas)

    # grava o arquivo de respostas fora do repositório (não é conteúdo do
    # CHAOS, é insumo pro onboarding rodar não-interativo)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                      encoding="utf-8") as f:
        yaml.safe_dump(respostas_prontas, f, allow_unicode=True)
        respostas_path = Path(f.name)

    try:
        print("\n  Rodando `chaos onboarding run --answers ...`")
        resultado = chaos_json(bin_chaos, repo_dir, "onboarding", "run",
                                "--answers", str(respostas_path))
        print(f"  Relatório: {resultado.get('report')}")
        print(f"  Arquivos: {len(resultado.get('files', []))}")
    finally:
        respostas_path.unlink(missing_ok=True)

    print(f"\n  Revise o relatório em {repo_dir / resultado.get('report', '')}")
    if not confirmar("  Relatório conferido — confirmar e liberar a Fase 0?"):
        raise ErroPasso("onboarding materializado mas NÃO confirmado — revise o relatório "
                         "e rode este script de novo (ele retoma daqui, não refaz as "
                         "perguntas) pra confirmar quando estiver pronto.")

    chaos_json(bin_chaos, repo_dir, "onboarding", "run", "--confirm")
    print("  Onboarding confirmado — Fase 0 liberada.")
    estado.marcar("onboarding")


# --------------------------------------------------------------------------- #
# Parte 4.4 — registro de chaves                                              #
# --------------------------------------------------------------------------- #

def passo_registrar_chaves(estado: Estado, repo_dir: Path, bin_chaos: Path,
                            human_pub: Path, worker_pub: Path) -> None:
    secao("Parte 4.4 — Registrando as chaves (o commit que funda a confiança)")
    allowed_signers = repo_dir / "metadata" / "registries" / "allowed_signers"
    conteudo_atual = allowed_signers.read_text(encoding="utf-8") if allowed_signers.exists() else ""

    owner = estado.resposta("owner_id", "human:owner")
    human_principal = estado.resposta("onboarding.human_signing_principal") \
        or estado.resposta("human_signing_principal", "")
    worker_principal = estado.resposta("onboarding.worker_signing_principal") \
        or estado.resposta("worker_signing_principal", "worker@chaos.local")

    def registrar(papel: str, pub: Path, principal: str) -> None:
        if principal and principal in conteudo_atual:
            print(f"  {papel}: já parece estar em allowed_signers — pulando.")
            return
        r = chaos_json(bin_chaos, repo_dir, "key", "register", papel, str(pub),
                        "--principal", principal)
        with allowed_signers.open("a", encoding="utf-8") as f:
            f.write(r["linha"] + "\n")
        print(f"  {papel}: linha acrescentada.")

    registrar(owner, human_pub, human_principal)
    registrar("executor:local_worker", worker_pub, worker_principal)

    segunda = estado.resposta("segunda_chave_humana_pub", "")
    if segunda and Path(segunda).exists():
        registrar(owner, Path(segunda), human_principal)

    print("\n  Commitando allowed_signers — vai pedir sua frase-secreta agora.")
    rodar(["git", "add", str(allowed_signers)], cwd=repo_dir)
    rodar(["git", "commit", "-m", "registra as chaves de assinatura"],
          cwd=repo_dir, herdar_stdio=True)

    v = chaos_json(bin_chaos, repo_dir, "key", "verify", check=False)
    if not v.get("humano"):
        raise ErroPasso(f"`chaos key verify` não confirmou humano após o commit: {v}\n"
                         "Confira se `user.signingkey`/`commit.gpgsign` estão certos e "
                         "rode este script de novo — ele retoma deste passo.")
    print(f"  key verify: humano={v['humano']} estado={v['estado']}")
    estado.marcar("chaves_registradas")


# --------------------------------------------------------------------------- #
# Parte 4.5 — conectar e empurrar                                             #
# --------------------------------------------------------------------------- #

def passo_push(estado: Estado, repo_dir: Path, remote_url: str) -> None:
    secao("Parte 4.5 — Conectando e empurrando")
    atual = rodar(["git", "remote", "get-url", "origin"], cwd=repo_dir, check=False)
    if atual.returncode != 0:
        rodar(["git", "remote", "add", "origin", remote_url], cwd=repo_dir)
    elif atual.stdout.strip() != remote_url:
        print(f"  origin já aponta pra {atual.stdout.strip()} — mantendo (diferente do "
              f"que foi anotado, {remote_url}; ajuste manualmente se estiver errado).")

    p = rodar(["git", "push", "-u", "origin", "main"], cwd=repo_dir, check=False)
    saida = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        if "workflow" in saida and "scope" in saida:
            print("  Push recusado por falta do escopo 'workflow' (o repositório tem "
                  ".github/workflows/lease-audit.yml, e o token não tem esse escopo).")
            if confirmar("  Rodar `gh auth refresh -h github.com -s workflow` agora?"):
                rodar(["gh", "auth", "refresh", "-h", "github.com", "-s", "workflow"],
                      herdar_stdio=True)
                p2 = rodar(["git", "push", "-u", "origin", "main"], cwd=repo_dir, check=False)
                if p2.returncode != 0:
                    raise ErroPasso(f"push falhou de novo:\n{p2.stdout}{p2.stderr}")
            else:
                raise ErroPasso("push pendente — rode `gh auth refresh -h github.com -s "
                                 "workflow` e `git push -u origin main` manualmente, depois "
                                 "rode este script de novo.")
        else:
            raise ErroPasso(f"push falhou:\n{saida}")
    print("  push ok.")
    estado.marcar("push")


# --------------------------------------------------------------------------- #
# Parte 5 — verificação                                                       #
# --------------------------------------------------------------------------- #

def passo_verificacao(estado: Estado, repo_dir: Path, bin_chaos: Path) -> None:
    secao("Parte 5 — Verificação")
    bin_order = bin_chaos.parent / "order"

    viol = chaos_json(bin_chaos, repo_dir, "validate", check=False)
    print(f"  validate: {'sem erros' if not viol else viol}")

    saude = chaos_json(bin_chaos, repo_dir, "health", check=False)
    print(f"  health: {saude.get('status')}")

    v = chaos_json(bin_chaos, repo_dir, "key", "verify", check=False)
    print(f"  key verify: humano={v.get('humano')}")

    if bin_order.exists():
        status = chaos_json(bin_order, repo_dir, "status", check=False)
        print(f"  order status: {status}")
        agentes = chaos_json(bin_order, repo_dir, "agent", "list", check=False)
        nomes = [a.get("name") for a in agentes] if isinstance(agentes, list) else agentes
        print(f"  equipe: {nomes}")

    if confirmar("\n  Rodar o teste ponta a ponta (cria uma tarefa de exemplo)?", default=True):
        tarefa = chaos_json(bin_chaos, repo_dir, "task", "create",
                             "--title", "Primeira tarefa do COSMOS")
        print(f"  criada: {tarefa.get('id')}")
        busca = chaos_json(bin_chaos, repo_dir, "search", "primeira", check=False)
        achou = any(r.get("id") == tarefa.get("id") for r in busca) if isinstance(busca, list) else False
        print(f"  busca encontrou: {achou}")

    estado.marcar("verificacao")


# --------------------------------------------------------------------------- #
# Parte 6 — worker no logon                                                   #
# --------------------------------------------------------------------------- #

def passo_worker_logon(estado: Estado, repo_dir: Path, toolkit_dir: Path) -> None:
    secao("Parte 6 — Worker no logon")
    if not confirmar("  Registrar o worker pra iniciar no logon desta máquina agora?",
                      default=True):
        print("  Pulado — pode rodar depois: "
              f"{toolkit_dir / ('register-worker.ps1' if platform.system() == 'Windows' else 'register-worker.sh')}")
        return

    sistema = platform.system()
    if sistema == "Windows":
        script = toolkit_dir / "register-worker.ps1"
        rodar(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
               "-File", str(script), "-RepoDir", str(repo_dir)], herdar_stdio=True)
    elif sistema == "Linux":
        script = toolkit_dir / "register-worker.sh"
        rodar(["bash", str(script), str(repo_dir)], herdar_stdio=True)
    else:
        print(f"  {sistema}: sem script automático ainda (macOS é LaunchAgent manual — "
              "ver Parte 6 do tutorial longo).")
        return

    estado.marcar("worker_logon")


# --------------------------------------------------------------------------- #
# orquestração                                                                #
# --------------------------------------------------------------------------- #

PASSOS = [
    "software", "chaves_ssh", "repo_remoto", "chaos_init", "config_assinatura",
    "onboarding", "chaves_registradas", "push", "verificacao", "worker_logon",
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-dir", required=True, help="pasta do novo repositório pessoal")
    ap.add_argument("--cosmos-dir", required=True,
                     help="pasta do clone de github.com/luannesi/cosmos (só usado pro "
                          "`chaos init` inicial — depois disso as ferramentas moram "
                          "vendorizadas dentro do próprio repositório)")
    args = ap.parse_args()

    repo_dir = Path(args.repo_dir).expanduser().resolve()
    cosmos_dir = Path(args.cosmos_dir).expanduser().resolve()
    toolkit_dir = Path(__file__).resolve().parent

    estado = Estado(_state_path(repo_dir))
    if estado.data["completed"]:
        print(f"Encontrei uma tentativa anterior pra {repo_dir} "
              f"({len(estado.data['completed'])}/{len(PASSOS)} passos concluídos).")
        if confirmar("Continuar de onde parou?", default=True):
            pass
        else:
            if confirmar("Recomeçar do zero? (as respostas já dadas continuam disponíveis "
                          "como sugestão em cada pergunta, não são apagadas)", default=False):
                estado.reiniciar_progresso()
            else:
                print("Cancelado — nada foi alterado.")
                return 0

    try:
        if not estado.done("software"):
            passo_software(estado, repo_dir)

        human_pub = worker_pub = None
        if not estado.done("chaves_ssh"):
            human_pub, worker_pub = passo_chaves_ssh(estado)
        else:
            human_pub = Path(estado.resposta("human_pub"))
            worker_pub = Path(estado.resposta("worker_pub"))

        remote_url = estado.resposta("remote_url")
        if not estado.done("repo_remoto"):
            remote_url = passo_repo_remoto(estado, repo_dir)

        bin_chaos = repo_dir / "bin" / "chaos"
        if not estado.done("chaos_init"):
            bin_chaos = passo_chaos_init(estado, repo_dir, cosmos_dir)

        if not estado.done("config_assinatura"):
            passo_config_assinatura_local(estado, repo_dir, human_pub)

        if not estado.done("onboarding"):
            passo_onboarding(estado, repo_dir, bin_chaos)

        if not estado.done("chaves_registradas"):
            passo_registrar_chaves(estado, repo_dir, bin_chaos, human_pub, worker_pub)

        if not estado.done("push"):
            passo_push(estado, repo_dir, remote_url)

        if not estado.done("verificacao"):
            passo_verificacao(estado, repo_dir, bin_chaos)

        if not estado.done("worker_logon"):
            passo_worker_logon(estado, repo_dir, toolkit_dir)

    except ErroPasso as exc:
        print(f"\nPAROU: {exc}")
        print("Rode este script de novo pra retomar exatamente daqui.")
        return 1
    except KeyboardInterrupt:
        print("\nInterrompido — o que já foi feito está salvo. Rode de novo pra retomar.")
        return 130

    print(f"\nPronto. Repositório em {repo_dir}, no ar em {remote_url or '(local)'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
