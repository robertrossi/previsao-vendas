"""Conexão DuckDB e estrutura inicial do banco do projeto."""

from pathlib import Path

import duckdb

from previsao_vendas.configuracao import obter_caminhos


def conectar(
    caminho: str | Path | None = None,
) -> duckdb.DuckDBPyConnection:
    """Abre uma conexão DuckDB no caminho do projeto ou em um caminho informado."""
    arquivo = Path(caminho) if caminho is not None else obter_caminhos().banco_duckdb
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(arquivo))


def criar_schemas(con: duckdb.DuckDBPyConnection) -> None:
    """Cria os schemas iniciais do projeto caso ainda não existam."""
    con.execute("CREATE SCHEMA IF NOT EXISTS bruto")
    con.execute("CREATE SCHEMA IF NOT EXISTS processado")


__all__ = ["conectar", "criar_schemas"]
