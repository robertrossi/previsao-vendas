from pathlib import Path

from previsao_vendas.banco_dados import conectar, criar_schemas


def test_conectar_abre_banco_temporario(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "temporario.duckdb"
    con = conectar(caminho_banco)

    try:
        assert caminho_banco.is_file()
        assert con.execute("SELECT 1").fetchone() == (1,)
    finally:
        con.close()


def test_criar_schemas_cria_bruto_e_processado(tmp_path: Path) -> None:
    con = conectar(tmp_path / "schemas.duckdb")

    try:
        criar_schemas(con)

        schemas = {
            linha[0]
            for linha in con.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name IN ('bruto', 'processado')
                """
            ).fetchall()
        }

        assert schemas == {"bruto", "processado"}
    finally:
        con.close()


def test_criar_schemas_pode_ser_executado_mais_de_uma_vez(
    tmp_path: Path,
) -> None:
    con = conectar(tmp_path / "schemas_idempotentes.duckdb")

    try:
        criar_schemas(con)
        criar_schemas(con)

        schemas = {
            linha[0]
            for linha in con.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name IN ('bruto', 'processado')
                """
            ).fetchall()
        }

        assert schemas == {"bruto", "processado"}
    finally:
        con.close()
