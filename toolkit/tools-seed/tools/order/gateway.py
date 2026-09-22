"""
Model Gateway (ORDER §21.5).

Normaliza autenticação, chamada, erros, retries e **estimativa de custo** (que
alimenta o Quota Engine). O que este módulo NÃO faz é decidir qual modelo usar —
isso é o Router (§21.3), e a separação importa: trocar de provedor não pode
exigir tocar em política de roteamento.

**Nenhuma credencial vive aqui.** Cada modelo remoto declara em
`model-registry.yaml` o nome da variável de ambiente que carrega sua chave
(`api_key_env`); o gateway lê do ambiente no momento da chamada e nunca grava.
Sem a variável, a chamada falha com mensagem explícita em vez de silenciosamente
cair para outro modelo — fallback silencioso é como um sistema passa meses
usando o modelo errado.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass


class ErroGateway(RuntimeError):
    pass


@dataclass
class Resposta:
    texto: str
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_estimado: float = 0.0
    adapter: str = ""

    def dict(self) -> dict:
        return {"text": self.texto, "model": self.modelo,
                "input_tokens": self.tokens_entrada,
                "output_tokens": self.tokens_saida,
                "estimated_cost": round(self.custo_estimado, 6),
                "adapter": self.adapter}


def _estimar_tokens(texto: str) -> int:
    # Estimativa grosseira e declarada como tal: serve para cota, não para conta.
    return max(1, len(texto) // 4)


def chamar(modelo: dict, prompt: str, *, timeout: int = 60,
           dry_run: bool = False) -> Resposta:
    adapter = modelo.get("adapter") or (
        "local" if modelo.get("locality") == "local" else "http")

    if dry_run:
        return Resposta(texto="", modelo=modelo["id"], adapter="dry-run",
                        tokens_entrada=_estimar_tokens(prompt))

    if adapter == "local":
        return _local(modelo, prompt, timeout)
    if adapter == "http":
        return _http(modelo, prompt, timeout)
    raise ErroGateway(f"adapter `{adapter}` desconhecido para `{modelo['id']}`")


def _local(modelo: dict, prompt: str, timeout: int) -> Resposta:
    """
    Modelos locais pelo binário declarado (`runner`, default `ollama`).

    É o único caminho para `privacy: local_only` — e é por isso que ele não pode
    ter fallback remoto: o conteúdo não sai da máquina, ponto.
    """
    runner = modelo.get("runner", "ollama")
    nome = modelo.get("model_name", modelo["id"])
    try:
        p = subprocess.run([runner, "run", nome], input=prompt,
                           capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise ErroGateway(
            f"`{runner}` não está instalado — a tarefa é `local_only` e NÃO há "
            "fallback remoto por desenho (§21.3). Instale o runner ou aceite a "
            "tarefa bloqueada por `no_model_capacity`.")
    except subprocess.TimeoutExpired:
        raise ErroGateway(f"`{runner}` excedeu {timeout}s")
    if p.returncode != 0:
        raise ErroGateway(f"`{runner}` falhou: {p.stderr.strip()[:200]}")
    return Resposta(texto=p.stdout, modelo=modelo["id"], adapter="local",
                    tokens_entrada=_estimar_tokens(prompt),
                    tokens_saida=_estimar_tokens(p.stdout),
                    custo_estimado=0.0)


def _http(modelo: dict, prompt: str, timeout: int) -> Resposta:
    endpoint = modelo.get("endpoint")
    if not endpoint:
        raise ErroGateway(
            f"`{modelo['id']}` não declara `endpoint` em model-registry.yaml — "
            "o registry só contém o que o usuário declarou no Onboarding (§3.4)")

    var = modelo.get("api_key_env", "")
    chave = os.environ.get(var, "") if var else ""
    if var and not chave:
        raise ErroGateway(
            f"a variável `{var}` não está no ambiente. O gateway nunca guarda "
            "credencial: ela vive fora do repositório (Impl. §15). Sem ela a "
            "chamada falha aqui em vez de cair em outro modelo em silêncio.")

    corpo = json.dumps({
        "model": modelo.get("model_name", modelo["id"]),
        "max_tokens": int(modelo.get("max_tokens", 2048)),
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(endpoint, data=corpo, method="POST")
    req.add_header("content-type", "application/json")
    for k, v in (modelo.get("headers") or {}).items():
        req.add_header(k, v.replace("${KEY}", chave))
    if chave and not modelo.get("headers"):
        req.add_header("authorization", f"Bearer {chave}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dados = json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        raise ErroGateway(f"{endpoint} respondeu {exc.code}: "
                          f"{exc.read()[:200].decode('utf-8', 'replace')}")
    except Exception as exc:
        raise ErroGateway(f"falha ao chamar {endpoint}: {exc}")

    texto = _extrair(dados)
    uso = dados.get("usage") or {}
    entrada = int(uso.get("input_tokens") or uso.get("prompt_tokens")
                  or _estimar_tokens(prompt))
    saida = int(uso.get("output_tokens") or uso.get("completion_tokens")
                or _estimar_tokens(texto))
    preco_e = float(modelo.get("price_per_1k_input", 0.0))
    preco_s = float(modelo.get("price_per_1k_output", 0.0))
    return Resposta(texto=texto, modelo=modelo["id"], adapter="http",
                    tokens_entrada=entrada, tokens_saida=saida,
                    custo_estimado=(entrada / 1000) * preco_e + (saida / 1000) * preco_s)


def _extrair(dados: dict) -> str:
    if isinstance(dados.get("content"), list):
        return "".join(b.get("text", "") for b in dados["content"])
    if dados.get("choices"):
        return dados["choices"][0].get("message", {}).get("content", "")
    return dados.get("text", "") or json.dumps(dados, ensure_ascii=False)
