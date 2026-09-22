"""Fixtures da suíte de AT (Acceptance Test)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness import CLI, CLIUnavailable, HUMAN, WORKER, Identity


def pytest_addoption(parser):
    parser.addoption("--chaos-bin", action="store", default=None,
                     help="caminho do executável `chaos` a testar")
    parser.addoption("--order-bin", action="store", default=None,
                     help="caminho do executável `order` a testar")
    parser.addoption("--profile", action="store", default="A",
                     help="perfil de implantação: A (Claude-nativo) ou B (auto-hospedado)")
    parser.addoption("--episodic-bin", action="store", default=None,
                     help="caminho do executável da camada episódica (CHAOS §4.2; "
                          "no binding de referência, `ai-memory`)")


def pytest_configure(config):
    config.addinivalue_line("markers", "at(spec, num): amarra o teste ao AT da spec")
    config.addinivalue_line("markers", "needs_remote: exige um remoto Git (hosting)")
    config.addinivalue_line("markers", "needs_two_executors: exige duas identidades de executor")


@pytest.fixture(scope="session")
def chaos_bin(request):
    return request.config.getoption("--chaos-bin")


@pytest.fixture(scope="session")
def order_bin(request):
    return request.config.getoption("--order-bin")


@pytest.fixture
def repo(tmp_path: Path, chaos_bin) -> Path:
    """
    Repositório CHAOS recém-inicializado.

    Usa `chaos init` — e não um layout fabricado pela suíte — de propósito: se a
    implementação não cria o layout de Implementação §4.3, os testes seguintes
    falham por essa razão, que é a razão certa.
    """
    if not chaos_bin:
        pytest.skip("`chaos` não apontado — rode com --chaos-bin=/caminho/para/chaos")
    root = tmp_path / "chaos-demo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    CLI(chaos_bin, root, "chaos")(
        "init", "--privacy-class", "demo", "--owner", "human:owner",
        identity=HUMAN, expect_ok=True,
    )
    return root


@pytest.fixture
def chaos(repo: Path, chaos_bin) -> CLI:
    return CLI(chaos_bin, repo, "chaos")


@pytest.fixture
def order(repo: Path, order_bin) -> CLI:
    if not order_bin:
        pytest.skip("`order` não apontado — rode com --order-bin=/caminho/para/order")
    return CLI(order_bin, repo, "order")


@pytest.fixture
def repo_pair(tmp_path: Path, chaos_bin):
    """
    Dois repositórios de classes de privacidade distintas.

    Necessário para §28.2 (reclassificação): o contrato diz que histórico e EVT
    não atravessam a fronteira de classe, e isso só é observável com duas.
    """
    if not chaos_bin:
        pytest.skip("`chaos` não apontado — rode com --chaos-bin=/caminho/para/chaos")

    def _make(name: str) -> Path:
        root = tmp_path / f"chaos-{name}"
        root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        CLI(chaos_bin, root, "chaos")(
            "init", "--privacy-class", name, "--owner", "human:owner",
            identity=HUMAN, expect_ok=True,
        )
        return root

    return _make("trabalho"), _make("cliente")


@pytest.fixture
def episodic(repo: Path, tmp_path: Path, request):
    """
    Camada episódica (CHAOS §4.2) — store fora do repositório CHAOS.

    A fixture é deliberadamente magra: os AT verificam o **contrato** — que o
    registro episódico não é fonte, que só `chaos promote` o traz para dentro —
    e não a API do componente que a implementa. Trocar `ai-memory` por outro
    componente não deve exigir reescrever nenhum AT; se exigir, o acoplamento
    entrou pela suíte, que é o lugar mais difícil de perceber.

    Sem `--episodic-bin`, os AT que dependem dela são pulados com motivo — nunca
    passam em verde, pela mesma razão dos demais.
    """
    binario = request.config.getoption("--episodic-bin")
    if not binario:
        pytest.skip("camada episódica não apontada — rode com --episodic-bin=/caminho/para/ai-memory")

    store = tmp_path / "episodic-demo"
    store.mkdir()
    import os
    os.environ["EPISODIC_STORE"] = str(store)
    os.environ["CHAOS_EPISODIC_BIN"] = binario
    cli = CLI(binario, repo, "episodic")
    cli("init", "--store", str(store), identity=HUMAN, expect_ok=True)

    class _Episodic:
        """Fachada mínima: observar, ler cru, e a referência que `chaos promote` aceita."""

        path = store

        def observe(self, texto: str) -> str:
            """Grava uma observação e devolve a referência estável para promoção."""
            r = cli("observe", "--text", texto, "--format", "json",
                    identity=HUMAN, expect_ok=True)
            return r.json()["ref"]

        def raw(self, ref: str) -> str:
            return cli("show", ref, identity=HUMAN, expect_ok=True).stdout

    return _Episodic()


@pytest.fixture
def chaves(repo: Path, tmp_path: Path):
    """
    Chaves de assinatura — a raiz de confiança de CHAOS §17.6.

    Esta fixture existe por causa de um resultado de campo, não de uma
    hipótese. O spike de 21/09/2026 mediu que a sessão na nuvem escolhe autor e
    committer à vontade e NÃO consegue assinar. Os AT que dependem dela testam
    a consequência: autoria humana é a presença de uma marca que o executor não
    produz.

    Deliberadamente sem frase-secreta, apesar de §17.6 exigi-la em produção: um
    teste automatizado não digita frase, e exigi-la aqui só transformaria o AT
    em teste de `expect`. O que o AT verifica é o PORTÃO — quem a assinatura
    diz ser —, não a fricção que protege a chave.
    """
    if not (tmp_path / "keys").exists():
        (tmp_path / "keys").mkdir()
    base = tmp_path / "keys"

    def _gerar(nome: str, principal: str) -> Path:
        priv = base / nome
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(priv),
                        "-C", principal], check=True)
        return priv

    humano = _gerar("humano", HUMAN.email)
    worker = _gerar("worker", WORKER.email)
    intruso = _gerar("intruso", "intruso@example.invalid")

    def _linha(principal: str, pub: Path, comentario: str, opcoes: str = '') -> str:
        tipo, chave = pub.read_text(encoding="utf-8").split()[:2]
        op = opcoes or 'namespaces="git"'
        return f"{principal} {op} {tipo} {chave} {comentario}"

    class _Chaves:
        arquivo = repo / "metadata" / "registries" / "allowed_signers"
        privada_humana, privada_worker, privada_intrusa = humano, worker, intruso

        def registrar(self, humano_ok: bool = True, worker_ok: bool = True) -> None:
            linhas = []
            if humano_ok:
                linhas.append(_linha(HUMAN.email, Path(str(humano) + ".pub"), "humano"))
            if worker_ok:
                linhas.append(_linha(WORKER.email, Path(str(worker) + ".pub"), "worker"))
            with self.arquivo.open("a", encoding="utf-8", newline="\n") as f:
                for l in linhas:
                    f.write(l + "\n")

        def expirar(self, principal: str, data: str) -> None:
            """§17.6: revogar é expirar, nunca apagar."""
            texto = self.arquivo.read_text(encoding="utf-8").splitlines()
            saida = []
            for l in texto:
                if l.startswith(principal + " "):
                    partes = l.split()
                    partes[1] = partes[1] + f',valid-before="{data}"'
                    l = " ".join(partes)
                saida.append(l)
            self.arquivo.write_text("\n".join(saida) + "\n", encoding="utf-8",
                                    newline="\n")

        def commit(self, mensagem: str, quem: str | None = "humano",
                   identity: Identity = HUMAN, cwd: Path | None = None):
            """
            Commit assinado (ou não) — `quem` decide a CHAVE, `identity` decide
            autor e committer. Separar os dois é o ponto: o spike mostrou que
            são dimensões independentes, e os AT precisam combiná-las livremente
            para reproduzir o caso que a v2.5 aceitava por engano.
            """
            onde = cwd or repo
            chave = {"humano": humano, "worker": worker, "intruso": intruso,
                     None: None}[quem]
            from harness import git as _git
            _git(onde, "add", "-A", identity=identity)
            args = ["commit", "-q", "-m", mensagem]
            if chave is not None:
                args = ["-c", "gpg.format=ssh",
                        "-c", f"user.signingkey={chave}.pub"] + args + ["-S"]
            return _git(onde, *args, identity=identity)

    return _Chaves()


@pytest.fixture
def clone(repo: Path, tmp_path: Path):
    """
    Segundo clone do mesmo repositório: representa o outro executor.

    A fila do ORDER (§11) e o merge do CHAOS (§17.3) só têm sentido com dois
    executores sobre o mesmo remoto; testar concorrência num diretório só
    verificaria outra coisa.
    """
    def _clone(name: str = "clone") -> Path:
        dst = tmp_path / name
        subprocess.run(["git", "clone", "-q", str(repo), str(dst)], check=True)
        return dst
    return _clone


def pytest_report_header(config):
    chaos = config.getoption("--chaos-bin") or "AUSENTE"
    order = config.getoption("--order-bin") or "AUSENTE"
    return [
        f"suíte de conformidade CHAOS v2.6 / ORDER v2.6 — perfil {config.getoption('--profile')}",
        f"chaos={chaos}  order={order}",
        "sem implementação apontada os AT são PULADOS, nunca verdes",
    ]
