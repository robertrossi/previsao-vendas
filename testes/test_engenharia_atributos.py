from datetime import date
from pathlib import Path

import pytest

from previsao_vendas.banco_dados import conectar, criar_schemas
from previsao_vendas.caracteristicas.engenharia_atributos import (
    gerar_atributos,
    gerar_caracteristicas,
)
from previsao_vendas.processamento.transformacao import transformar_bases


def _criar_dados_base(
    caminho_banco: Path,
    treino_extra: list[tuple[str, ...]] | None = None,
    teste_extra: list[tuple[str, ...]] | None = None,
    features_extra: list[tuple[str, ...]] | None = None,
) -> None:
    """Configura o banco com tabelas processadas a partir de dados sintéticos."""
    con = conectar(caminho_banco)
    try:
        criar_schemas(con)
        con.execute(
            """
            CREATE OR REPLACE TABLE bruto.train (
                Store VARCHAR, Dept VARCHAR, Date VARCHAR,
                Weekly_Sales VARCHAR, IsHoliday VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TABLE bruto.test (
                Store VARCHAR, Dept VARCHAR, Date VARCHAR, IsHoliday VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TABLE bruto.stores (
                Store VARCHAR, Type VARCHAR, Size VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TABLE bruto.features (
                Store VARCHAR, Date VARCHAR, Temperature VARCHAR,
                Fuel_Price VARCHAR, MarkDown1 VARCHAR, MarkDown2 VARCHAR,
                MarkDown3 VARCHAR, MarkDown4 VARCHAR, MarkDown5 VARCHAR,
                CPI VARCHAR, Unemployment VARCHAR, IsHoliday VARCHAR
            )
            """
        )

        # 5 semanas consecutivas para Store 1, Dept 1 (2010-02-05 a 2010-03-05)
        # e uma semana exatamente 52 semanas depois (2011-02-04)
        treino_padrao = [
            ("1", "1", "2010-02-05", "100.00", "FALSE"),
            ("1", "1", "2010-02-12", "200.00", "FALSE"),
            ("1", "1", "2010-02-19", "300.00", "FALSE"),
            ("1", "1", "2010-02-26", "400.00", "FALSE"),
            ("1", "1", "2010-03-05", "500.00", "FALSE"),
            ("1", "1", "2011-02-04", "1000.00", "FALSE"),
        ]
        teste_padrao = [
            ("1", "1", "2012-11-02", "FALSE"),
            ("1", "1", "2012-11-09", "FALSE"),
        ]
        stores_padrao = [("1", "A", "151315")]
        features_padrao = [
            (
                "1",
                d,
                "45.0",
                "2.5",
                "NA",
                "NA",
                "NA",
                "NA",
                "NA",
                "210.0",
                "8.0",
                "FALSE",
            )
            for d in (
                "2010-02-05",
                "2010-02-12",
                "2010-02-19",
                "2010-02-26",
                "2010-03-05",
                "2011-02-04",
                "2012-11-02",
                "2012-11-09",
            )
        ]

        con.executemany(
            "INSERT INTO bruto.train VALUES (?, ?, ?, ?, ?)",
            treino_padrao if treino_extra is None else treino_extra,
        )
        con.executemany(
            "INSERT INTO bruto.test VALUES (?, ?, ?, ?)",
            teste_padrao if teste_extra is None else teste_extra,
        )
        con.executemany("INSERT INTO bruto.stores VALUES (?, ?, ?)", stores_padrao)
        con.executemany(
            "INSERT INTO bruto.features VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            features_padrao if features_extra is None else features_extra,
        )
    finally:
        con.close()

    transformar_bases(caminho_banco)


def test_gerar_atributos_cria_schemas_e_tabelas(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "teste_schemas.duckdb"
    _criar_dados_base(caminho_banco)

    resultado = gerar_atributos(caminho_banco)

    assert resultado["features.treino_modelagem"] == 6
    assert resultado["features.teste_modelagem"] == 2
    assert resultado["treino_lag_1_disponivel"] == 4
    assert resultado["treino_lag_2_disponivel"] == 3
    assert resultado["treino_lag_4_disponivel"] == 1
    assert resultado["treino_lag_52_disponivel"] == 1

    con = conectar(caminho_banco)
    try:
        tabelas = {
            linha[0]
            for linha in con.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'features'
                """
            ).fetchall()
        }
        assert tabelas == {"treino_modelagem", "teste_modelagem"}
    finally:
        con.close()


def test_atributos_de_calendario(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "teste_calendario.duckdb"
    _criar_dados_base(caminho_banco)

    gerar_atributos(caminho_banco)

    con = conectar(caminho_banco)
    try:
        linha_treino = con.execute(
            """
            SELECT Date, Year, Month, Week, Quarter, DayOfYear
            FROM features.treino_modelagem
            WHERE Date = DATE '2010-02-05'
            """
        ).fetchone()

        assert linha_treino[0] == date(2010, 2, 5)
        assert linha_treino[1] == 2010
        assert linha_treino[2] == 2
        assert linha_treino[3] == 5
        assert linha_treino[4] == 1
        assert linha_treino[5] == 36

        linha_teste = con.execute(
            """
            SELECT Date, Year, Month, Week, Quarter, DayOfYear
            FROM features.teste_modelagem
            WHERE Date = DATE '2012-11-02'
            """
        ).fetchone()

        assert linha_teste[0] == date(2012, 11, 2)
        assert linha_teste[1] == 2012
        assert linha_teste[2] == 11
        assert linha_teste[3] == 44
        assert linha_teste[4] == 4
        assert linha_teste[5] == 307
    finally:
        con.close()


def test_lags_respeitam_diferenca_exata_de_calendario(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "teste_lags.duckdb"
    # Semanas: 1, 2, 3, 4, 5 e 52 semanas depois (52 * 7 = 364 dias)
    # 2010-02-05 + 364 dias = 2011-02-04
    _criar_dados_base(caminho_banco)

    gerar_atributos(caminho_banco)

    con = conectar(caminho_banco)
    try:
        lags_w1 = con.execute(
            """
            SELECT lag_1, lag_2, lag_4, lag_52,
                   lag_1_disponivel, lag_2_disponivel,
                   lag_4_disponivel, lag_52_disponivel
            FROM features.treino_modelagem
            WHERE Date = DATE '2010-02-05'
            """
        ).fetchone()
        assert lags_w1 == (None, None, None, None, False, False, False, False)

        lags_w2 = con.execute(
            """
            SELECT lag_1, lag_2, lag_4, lag_52, lag_1_disponivel
            FROM features.treino_modelagem
            WHERE Date = DATE '2010-02-12'
            """
        ).fetchone()
        assert lags_w2 == (100.00, None, None, None, True)

        lags_w3 = con.execute(
            """
            SELECT lag_1, lag_2, lag_4, lag_52, lag_2_disponivel
            FROM features.treino_modelagem
            WHERE Date = DATE '2010-02-19'
            """
        ).fetchone()
        assert lags_w3 == (200.00, 100.00, None, None, True)

        lags_w5 = con.execute(
            """
            SELECT lag_1, lag_2, lag_4, lag_52, lag_4_disponivel
            FROM features.treino_modelagem
            WHERE Date = DATE '2010-03-05'
            """
        ).fetchone()
        assert lags_w5 == (400.00, 300.00, 100.00, None, True)

        lags_52w = con.execute(
            """
            SELECT lag_1, lag_2, lag_4, lag_52, lag_52_disponivel
            FROM features.treino_modelagem
            WHERE Date = DATE '2011-02-04'
            """
        ).fetchone()
        # 52 semanas antes (2010-02-05) tinha venda 100.00
        assert lags_52w[3] == 100.00
        assert lags_52w[4] is True
    finally:
        con.close()


def test_lags_retornam_null_em_semanas_com_lacunas(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "teste_lags_lacunas.duckdb"
    # Lacuna entre 2010-02-05 e 2010-03-05 (sem semanas 2010-02-12, 19, 26)
    treino = [
        ("1", "1", "2010-02-05", "100.00", "FALSE"),
        ("1", "1", "2010-03-05", "500.00", "FALSE"),
    ]
    features = [
        (
            "1",
            d,
            "45.0",
            "2.5",
            "NA",
            "NA",
            "NA",
            "NA",
            "NA",
            "210.0",
            "8.0",
            "FALSE",
        )
        for d in ("2010-02-05", "2010-03-05", "2012-11-02", "2012-11-09")
    ]
    _criar_dados_base(caminho_banco, treino_extra=treino, features_extra=features)

    gerar_atributos(caminho_banco)

    con = conectar(caminho_banco)
    try:
        # Em 2010-03-05, lag_1 e lag_2 NÃO existem no calendário!
        # NÃO deve pegar 2010-02-05 como substituto posicional!
        linha = con.execute(
            """
            SELECT lag_1, lag_2, lag_4, lag_1_disponivel, lag_4_disponivel
            FROM features.treino_modelagem
            WHERE Date = DATE '2010-03-05'
            """
        ).fetchone()

        assert linha[0] is None
        assert linha[1] is None
        assert (
            linha[2] == 100.00
        )  # lag_4 (4 semanas = 28 dias antes = 2010-02-05) existe!
        assert linha[3] is False
        assert linha[4] is True
    finally:
        con.close()


def test_estatisticas_moveis_respeitam_regras_temporais(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "teste_moveis.duckdb"
    _criar_dados_base(caminho_banco)

    gerar_atributos(caminho_banco)

    con = conectar(caminho_banco)
    try:
        # Semana 1 (2010-02-05): nenhuma semana anterior
        w1 = con.execute(
            """
            SELECT rolling_mean_4, rolling_count_4, rolling_std_4
            FROM features.treino_modelagem
            WHERE Date = DATE '2010-02-05'
            """
        ).fetchone()
        assert w1 == (None, 0, None)

        # Semana 2 (2010-02-12): 1 observação anterior (100.00)
        # rolling_std_4 deve ser NULL pois N < 2
        w2 = con.execute(
            """
            SELECT rolling_mean_4, rolling_count_4, rolling_std_4
            FROM features.treino_modelagem
            WHERE Date = DATE '2010-02-12'
            """
        ).fetchone()
        assert w2[0] == 100.00
        assert w2[1] == 1
        assert w2[2] is None

        # Semana 3 (2010-02-19): 2 observações anteriores (100.00, 200.00)
        # média = 150.00, std = 70.710678...
        w3 = con.execute(
            """
            SELECT rolling_mean_4, rolling_count_4, rolling_std_4
            FROM features.treino_modelagem
            WHERE Date = DATE '2010-02-19'
            """
        ).fetchone()
        assert w3[0] == 150.00
        assert w3[1] == 2
        assert w3[2] == pytest.approx(70.710678, rel=1e-4)

        # Semana 5 (2010-03-05): 4 observações anteriores (100, 200, 300, 400)
        # média = 250.00, count = 4, std = 129.09944...
        w5 = con.execute(
            """
            SELECT rolling_mean_4, rolling_count_4, rolling_std_4,
                   rolling_mean_8, rolling_count_8
            FROM features.treino_modelagem
            WHERE Date = DATE '2010-03-05'
            """
        ).fetchone()
        assert w5[0] == 250.00
        assert w5[1] == 4
        assert w5[2] == pytest.approx(129.09944, rel=1e-4)
        assert w5[3] == 250.00
        assert w5[4] == 4
    finally:
        con.close()


def test_teste_modelagem_recebe_somente_atributos_antecipados(
    tmp_path: Path,
) -> None:
    caminho_banco = tmp_path / "teste_antecipados.duckdb"
    _criar_dados_base(caminho_banco)

    gerar_atributos(caminho_banco)

    con = conectar(caminho_banco)
    try:
        colunas_teste = [
            linha[0]
            for linha in con.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'features' AND table_name = 'teste_modelagem'
                """
            ).fetchall()
        ]

        # Não deve conter a variável-alvo
        assert "Weekly_Sales" not in colunas_teste

        # Não deve conter atributos históricos calculados antecipadamente no teste
        assert "lag_1" not in colunas_teste
        assert "lag_2" not in colunas_teste
        assert "lag_4" not in colunas_teste
        assert "lag_52" not in colunas_teste
        assert "rolling_mean_4" not in colunas_teste
        assert "rolling_mean_8" not in colunas_teste
        assert "rolling_std_4" not in colunas_teste
        assert "rolling_count_4" not in colunas_teste
        assert "rolling_count_8" not in colunas_teste

        # Deve conter todos os atributos conhecidos antecipadamente
        atributos_esperados = {
            "Store",
            "Dept",
            "Date",
            "IsHoliday",
            "Store_Type",
            "Store_Size",
            "Temperature",
            "Fuel_Price",
            "MarkDown1",
            "MarkDown2",
            "MarkDown3",
            "MarkDown4",
            "MarkDown5",
            "CPI",
            "Unemployment",
            "MarkDown1_missing",
            "MarkDown2_missing",
            "MarkDown3_missing",
            "MarkDown4_missing",
            "MarkDown5_missing",
            "CPI_missing",
            "Unemployment_missing",
            "Year",
            "Month",
            "Week",
            "Quarter",
            "DayOfYear",
        }
        assert set(colunas_teste) == atributos_esperados
    finally:
        con.close()


def test_idempotencia_da_engenharia_de_atributos(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "teste_idempotencia.duckdb"
    _criar_dados_base(caminho_banco)

    res1 = gerar_atributos(caminho_banco)
    res2 = gerar_caracteristicas(caminho_banco)

    assert res1 == res2

    con = conectar(caminho_banco)
    try:
        count = con.execute(
            "SELECT COUNT(*) FROM features.treino_modelagem"
        ).fetchone()[0]
        assert count == 6
    finally:
        con.close()


def test_falha_reverte_transacao(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "teste_rollback.duckdb"
    con = conectar(caminho_banco)
    try:
        criar_schemas(con)
        con.execute("CREATE SCHEMA IF NOT EXISTS features")
        con.execute("CREATE TABLE features.treino_modelagem (col VARCHAR)")
        con.execute("INSERT INTO features.treino_modelagem VALUES ('estado_anterior')")
    finally:
        con.close()

    # Sem criar processado.treino_base, deve falhar
    with pytest.raises(
        ValueError,
        match=r"Tabelas processado\.treino_base e processado\.teste_base",
    ):
        gerar_atributos(caminho_banco)

    con = conectar(caminho_banco)
    try:
        linhas = con.execute("SELECT * FROM features.treino_modelagem").fetchall()
        assert linhas == [("estado_anterior",)]
    finally:
        con.close()
