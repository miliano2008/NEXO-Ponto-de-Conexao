"""NEXO — leitura das configurações (banco, e-mail e aplicação).

Ordem de prioridade (a primeira que tiver o valor vence):
  1. variáveis de ambiente do sistema;
  2. arquivo .env na raiz do projeto (padrão do projeto; modelo em .env.example);
  3. config.ini antigo (raiz ou banco/), aceito para quem já configurou a versão 0.3.

Nenhuma senha fica no código nem vai para o navegador: só o servidor lê estes valores.
"""

import configparser
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_ENV = RAIZ / ".env"
CONFIG_INI = [RAIZ / "config.ini", RAIZ / "banco" / "config.ini"]
PASTA_DADOS = RAIZ / "banco" / "dados"

# chave do .env → (seção, chave) do config.ini antigo
_EQUIVALENTES_INI = {
    "APP_URL_BASE": ("app", "url_base"),
    "DB_HOST": ("mysql", "host"), "DB_PORT": ("mysql", "porta"), "DB_USER": ("mysql", "usuario"),
    "DB_PASSWORD": ("mysql", "senha"), "DB_NAME": ("mysql", "banco"), "DB_SSL_CA": ("mysql", "ssl_ca"),
    "SMTP_HOST": ("smtp", "host"), "SMTP_PORT": ("smtp", "porta"), "SMTP_SECURITY": ("smtp", "seguranca"),
    "SMTP_USER": ("smtp", "usuario"), "SMTP_PASSWORD": ("smtp", "senha"), "SMTP_FROM": ("smtp", "remetente"),
}


def _ler_env(arquivo):
    """Leitor simples de .env (CHAVE=valor), sem depender de biblioteca."""
    valores = {}
    if not arquivo.exists():
        return valores
    for linha in arquivo.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        valores[chave.strip()] = valor
    return valores


def _ler_ini():
    cfg = configparser.ConfigParser(interpolation=None)  # senhas podem ter '%'
    for arquivo in CONFIG_INI:
        if arquivo.exists():
            cfg.read(arquivo, encoding="utf-8-sig")  # aceita arquivo salvo pelo Bloco de Notas (BOM)
            return cfg, arquivo
    return cfg, None


_cache = {"chave": None, "valores": None}


def _assinatura_arquivos():
    return tuple((str(a), a.stat().st_mtime_ns) for a in [ARQUIVO_ENV, *CONFIG_INI] if a.exists())


def valores():
    """Todas as configurações já combinadas, no formato do .env.

    Os arquivos só são relidos quando mudam (data de modificação), então a
    leitura não pesa em cada pedido do servidor.
    """
    chave = (_assinatura_arquivos(), tuple(os.environ.get(k, "") for k in _EQUIVALENTES_INI))
    if _cache["chave"] != chave:
        _cache.update(chave=chave, valores=_combinar())
    return dict(_cache["valores"])


def _combinar():
    cfg, _ = _ler_ini()
    combinado = {}
    for chave, (secao, nome) in _EQUIVALENTES_INI.items():
        if cfg.has_option(secao, nome):
            combinado[chave] = cfg.get(secao, nome).strip()
    combinado.update({k: v for k, v in _ler_env(ARQUIVO_ENV).items() if v != ""})
    combinado.update({k: os.environ[k] for k in _EQUIVALENTES_INI if os.environ.get(k)})
    return combinado


def obter(chave, padrao=""):
    return valores().get(chave, padrao)


def origem():
    """De onde as configurações estão vindo (mostrado no diagnóstico)."""
    if ARQUIVO_ENV.exists():
        return str(ARQUIVO_ENV)
    _, arquivo = _ler_ini()
    return str(arquivo) if arquivo else None


def caminho(valor, padrao=None):
    """Resolve caminhos relativos à raiz do projeto (ex.: banco/dados/ca.pem).

    Aceita o caminho antigo 'dados/ca.pem' da versão 0.3, que agora fica em banco/dados/.
    """
    if not valor:
        return padrao
    arquivo = Path(valor)
    if not arquivo.is_absolute():
        arquivo = RAIZ / arquivo
        if not arquivo.exists() and Path(valor).parts[:1] == ("dados",):
            arquivo = RAIZ / "banco" / Path(valor)
    return arquivo


def salvar_env(novos):
    """Grava o .env preservando chaves que não foram alteradas."""
    atuais = _ler_env(ARQUIVO_ENV)
    atuais.update({k: v for k, v in novos.items() if v is not None})
    blocos = [
        ("# Aplicação", ["APP_URL_BASE"]),
        ("# Banco MySQL (Aiven). Deixe DB_HOST vazio para o modo local (CSV + SQLite).",
         ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME", "DB_SSL_CA"]),
        ("# E-mail (confirmação de cadastro e recuperação de senha)",
         ["SMTP_HOST", "SMTP_PORT", "SMTP_SECURITY", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"]),
    ]
    linhas = ["# Gerado por app/configurar.py. NÃO envie este arquivo para o GitHub (contém senhas).", ""]
    conhecidas = set()
    for titulo, chaves in blocos:
        linhas.append(titulo)
        for chave in chaves:
            linhas.append(f"{chave}={atuais.get(chave, '')}")
            conhecidas.add(chave)
        linhas.append("")
    linhas += [f"{k}={v}" for k, v in atuais.items() if k not in conhecidas]
    ARQUIVO_ENV.write_text("\n".join(linhas).rstrip() + "\n", encoding="utf-8")
    return ARQUIVO_ENV
