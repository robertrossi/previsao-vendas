"""Leitura estrutural e carga dos CSVs na camada bruta."""

import csv
from pathlib import Path

import duckdb

from previsao_vendas.banco_dados import conectar, criar_schemas
from previsao_vendas.configuracao import obter_caminhos

_ARQUIVOS = (
    (
        "train.csv",
        "train",
        ("Store", "Dept", "Date", "Weekly_Sales", "IsHoliday"),
    ),
    ("test.csv", "test", ("Store", "Dept", "Date", "IsHoliday")),
    ("stores.csv", "stores", ("Store", "Type", "Size")),
    (
        "features.csv",
        "features",
        (
            "Store",
            "Date",
            "Temperature",
            "Fuel_Price",
            "MarkDown1",
            "MarkDown2",
            "MarkDown3",
            "MarkDown4",
            "MarkDown5",
            "CPI",
            "Unemployment",
            "IsHoliday",
        ),
    ),
    ("sampleSubmission.csv", "sample_submission", ("Id", "Weekly_Sales")),
)


def _identificador_sql(identificador: str) -> str:
    return '"' + identificador.replace('"', '""') + '"'


def _literal_sql(valor: str | Path) -> str:
    return "'" + str(valor).replace("'", "''") + "'"


def _validar_arquivo(caminho: Path, colunas_esperadas: tuple[str, ...]) -> int:
    """Valida cabeçalho e largura das linhas; retorna a contagem de registros."""
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {caminho}")

    try:
        with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
            leitor = csv.reader(arquivo, strict=True)
            cabecalho = next(leitor, None)
            if cabecalho is None:
                raise ValueError(f"Arquivo CSV vazio ou sem cabeçalho: {caminho}")
            if tuple(cabecalho) != colunas_esperadas:
                raise ValueError(
                    f"Cabeçalho inesperado em {caminho.name}: {cabecalho!r}; "
                    f"esperado: {list(colunas_esperadas)!r}"
                )

            quantidade = 0
            for numero_registro, linha in enumerate(leitor, start=2):
                if len(linha) != len(colunas_esperadas):
                    raise ValueError(
                        f"Estrutura inválida em {caminho.name}, registro "
                        f"{numero_registro}: esperadas {len(colunas_esperadas)} "
                        f"colunas, encontradas {len(linha)}"
                    )
                quantidade += 1
            return quantidade
    except csv.Error as erro:
        raise ValueError(f"CSV malformado em {caminho}: {erro}") from erro


def _criar_tabela_temporaria(
    con: duckdb.DuckDBPyConnection,
    caminho: Path,
    tabela_temporaria: str,
    colunas_esperadas: tuple[str, ...],
    quantidade_lida: int,
) -> None:
    nome_sql = _identificador_sql(tabela_temporaria)
    caminho_sql = _literal_sql(caminho.resolve())
    colunas_nao_nulas_sql = (
        "[" + ", ".join(_literal_sql(coluna) for coluna in colunas_esperadas) + "]"
    )
    con.execute(
        f"CREATE TEMP TABLE {nome_sql} AS "
        "SELECT * FROM read_csv("
        f"{caminho_sql}, header=true, all_varchar=true, "
        f"force_not_null={colunas_nao_nulas_sql}, "
        "strict_mode=true, ignore_errors=false)"
    )

    descricao = con.execute(f"DESCRIBE SELECT * FROM {nome_sql}").fetchall()
    colunas_lidas = tuple(linha[0] for linha in descricao)
    tipos_lidos = tuple(linha[1] for linha in descricao)
    if colunas_lidas != colunas_esperadas:
        raise ValueError(
            f"Colunas lidas de {caminho.name} diferem do cabeçalho validado: "
            f"{colunas_lidas!r}"
        )
    if any(tipo != "VARCHAR" for tipo in tipos_lidos):
        raise TypeError(
            f"Todas as colunas de {caminho.name} devem ser VARCHAR; "
            f"tipos encontrados: {tipos_lidos!r}"
        )

    quantidade_lida_duckdb = con.execute(f"SELECT COUNT(*) FROM {nome_sql}").fetchone()[
        0
    ]
    if quantidade_lida_duckdb != quantidade_lida:
        raise ValueError(
            f"Quantidade de registros divergente na leitura de {caminho.name}: "
            f"CSV={quantidade_lida}, DuckDB={quantidade_lida_duckdb}"
        )


def _substituir_tabela(
    con: duckdb.DuckDBPyConnection,
    tabela_temporaria: str,
    tabela_destino: str,
    quantidade_esperada: int,
) -> int:
    tabela_temporaria_sql = _identificador_sql(tabela_temporaria)
    tabela_destino_sql = (
        f"{_identificador_sql('bruto')}.{_identificador_sql(tabela_destino)}"
    )
    con.execute(
        f"CREATE OR REPLACE TABLE {tabela_destino_sql} AS "
        f"SELECT * FROM {tabela_temporaria_sql}"
    )
    quantidade_gravada = con.execute(
        f"SELECT COUNT(*) FROM {tabela_destino_sql}"
    ).fetchone()[0]
    if quantidade_gravada != quantidade_esperada:
        raise ValueError(
            f"Quantidade de registros divergente em bruto.{tabela_destino}: "
            f"esperada={quantidade_esperada}, gravada={quantidade_gravada}"
        )
    return quantidade_gravada


def ingerir_csvs(
    diretorio_origem: Path | None = None,
    caminho_banco: str | Path | None = None,
) -> dict[str, int]:
    """Carrega os cinco CSVs nas tabelas brutas e retorna as contagens gravadas.

    Os argumentos opcionais permitem apontar para fixtures e bancos temporários
    nos testes. Sem argumentos, são usados os caminhos centrais do projeto.
    """
    caminhos = obter_caminhos()
    origem = (
        Path(diretorio_origem)
        if diretorio_origem is not None
        else caminhos.dados_brutos
    )
    contagens = {
        nome_tabela: _validar_arquivo(origem / nome_arquivo, colunas)
        for nome_arquivo, nome_tabela, colunas in _ARQUIVOS
    }

    con = conectar() if caminho_banco is None else conectar(caminho_banco)
    try:
        for nome_arquivo, nome_tabela, colunas in _ARQUIVOS:
            _criar_tabela_temporaria(
                con,
                origem / nome_arquivo,
                f"_staging_{nome_tabela}",
                colunas,
                contagens[nome_tabela],
            )

        criar_schemas(con)
        con.execute("BEGIN TRANSACTION")
        try:
            contagens_gravadas = {
                nome_tabela: _substituir_tabela(
                    con,
                    f"_staging_{nome_tabela}",
                    nome_tabela,
                    contagens[nome_tabela],
                )
                for _, nome_tabela, _ in _ARQUIVOS
            }
            con.execute("COMMIT")
            return {
                f"bruto.{nome_tabela}": quantidade
                for nome_tabela, quantidade in contagens_gravadas.items()
            }
        except Exception:
            try:
                con.execute("ROLLBACK")
            except Exception as erro_rollback:
                raise RuntimeError(
                    "Falha ao reverter a transação de ingestão"
                ) from erro_rollback
            raise
    finally:
        con.close()


__all__ = ["ingerir_csvs"]
