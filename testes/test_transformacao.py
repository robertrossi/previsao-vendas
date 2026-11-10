from datetime import date
from pathlib import Path

import pytest

from previsao_vendas.banco_dados import conectar, criar_schemas
from previsao_vendas.processamento.transformacao import transformar_bases

_DADOS_TREINO_PADRAO = [
    ("1", "1", "2010-02-05", "24924.50", "FALSE"),
    ("1", "2", "2010-02-05", "-175.00", "FALSE"),
    ("2", "1", "2010-02-05", "0.00", "FALSE"),
]

_DADOS_TESTE_PADRAO = [
    ("1", "1", "2012-11-02", "FALSE"),
    ("2", "1", "2012-11-02", "FALSE"),
]

_DADOS_STORES_PADRAO = [
    ("1", "A", "151315"),
    ("2", "B", "202307"),
]

_DADOS_FEATURES_PADRAO = [
    (
        "1",
        "2010-02-05",
        "42.31",
        "2.572",
        "NA",
        "NA",
        "NA",
        "NA",
        "NA",
        "211.096358",
        "8.106",
        "FALSE",
    ),
    (
        "2",
        "2010-02-05",
        "38.51",
        "2.572",
        "100.5",
        "200.0",
        "300.0",
        "400.0",
        "500.0",
        "NA",
        "NA",
        "FALSE",
    ),
    (
        "1",
        "2012-11-02",
        "55.32",
        "3.386",
        "6766.44",
        "NA",
        "8.5",
        "NA",
        "1200.0",
        "223.46",
        "6.57",
        "FALSE",
    ),
    (
        "2",
        "2012-11-02",
        "58.34",
        "3.386",
        "NA",
        "NA",
        "NA",
        "NA",
        "NA",
        "NA",
        "NA",
        "FALSE",
    ),
]


def _criar_dados_brutos(
    caminho_banco: Path,
    treino: list[tuple[str, ...]] | None = None,
    teste: list[tuple[str, ...]] | None = None,
    stores: list[tuple[str, ...]] | None = None,
    features: list[tuple[str, ...]] | None = None,
) -> None:
    """Cria tabelas no schema bruto com todas as colunas como VARCHAR."""
    con = conectar(caminho_banco)
    try:
        criar_schemas(con)
        con.execute(
            """
            CREATE OR REPLACE TABLE bruto.train (
                Store VARCHAR,
                Dept VARCHAR,
                Date VARCHAR,
                Weekly_Sales VARCHAR,
                IsHoliday VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TABLE bruto.test (
                Store VARCHAR,
                Dept VARCHAR,
                Date VARCHAR,
                IsHoliday VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TABLE bruto.stores (
                Store VARCHAR,
                Type VARCHAR,
                Size VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TABLE bruto.features (
                Store VARCHAR,
                Date VARCHAR,
                Temperature VARCHAR,
                Fuel_Price VARCHAR,
                MarkDown1 VARCHAR,
                MarkDown2 VARCHAR,
                MarkDown3 VARCHAR,
                MarkDown4 VARCHAR,
                MarkDown5 VARCHAR,
                CPI VARCHAR,
                Unemployment VARCHAR,
                IsHoliday VARCHAR
            )
            """
        )

        con.executemany(
            "INSERT INTO bruto.train VALUES (?, ?, ?, ?, ?)",
            _DADOS_TREINO_PADRAO if treino is None else treino,
        )
        con.executemany(
            "INSERT INTO bruto.test VALUES (?, ?, ?, ?)",
            _DADOS_TESTE_PADRAO if teste is None else teste,
        )
        con.executemany(
            "INSERT INTO bruto.stores VALUES (?, ?, ?)",
            _DADOS_STORES_PADRAO if stores is None else stores,
        )
        con.executemany(
            "INSERT INTO bruto.features VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _DADOS_FEATURES_PADRAO if features is None else features,
        )
    finally:
        con.close()


def test_transformar_bases_converte_tipos_de_dados(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "teste_tipos.duckdb"
    _criar_dados_brutos(caminho_banco)

    transformar_bases(caminho_banco)

    tipos_esperados_treino = {
        "Store": "INTEGER",
        "Dept": "INTEGER",
        "Date": "DATE",
        "Weekly_Sales": "DOUBLE",
        "IsHoliday": "BOOLEAN",
        "Store_Type": "VARCHAR",
        "Store_Size": "DOUBLE",
        "Temperature": "DOUBLE",
        "Fuel_Price": "DOUBLE",
        "MarkDown1": "DOUBLE",
        "MarkDown2": "DOUBLE",
        "MarkDown3": "DOUBLE",
        "MarkDown4": "DOUBLE",
        "MarkDown5": "DOUBLE",
        "CPI": "DOUBLE",
        "Unemployment": "DOUBLE",
        "MarkDown1_missing": "BOOLEAN",
        "MarkDown2_missing": "BOOLEAN",
        "MarkDown3_missing": "BOOLEAN",
        "MarkDown4_missing": "BOOLEAN",
        "MarkDown5_missing": "BOOLEAN",
        "CPI_missing": "BOOLEAN",
        "Unemployment_missing": "BOOLEAN",
    }
    tipos_esperados_teste = {
        coluna: tipo
        for coluna, tipo in tipos_esperados_treino.items()
        if coluna != "Weekly_Sales"
    }

    con = conectar(caminho_banco)
    try:
        colunas_treino = {
            linha[0]: linha[1]
            for linha in con.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'processado' AND table_name = 'treino_base'
                """
            ).fetchall()
        }
        colunas_teste = {
            linha[0]: linha[1]
            for linha in con.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'processado' AND table_name = 'teste_base'
                """
            ).fetchall()
        }

        assert colunas_treino == tipos_esperados_treino
        assert colunas_teste == tipos_esperados_teste

        registro = con.execute(
            """
            SELECT
                Store, Dept, Date, Weekly_Sales, IsHoliday, Store_Type, Store_Size,
                Temperature, Fuel_Price, MarkDown1_missing, CPI, Unemployment
            FROM processado.treino_base
            WHERE Store = 1 AND Dept = 1
            """
        ).fetchone()
        assert isinstance(registro[0], int)
        assert isinstance(registro[1], int)
        assert isinstance(registro[2], date)
        assert isinstance(registro[3], float)
        assert isinstance(registro[4], bool)
        assert isinstance(registro[5], str)
        assert isinstance(registro[6], float)
        assert isinstance(registro[7], float)
        assert isinstance(registro[8], float)
        assert isinstance(registro[9], bool)
        assert isinstance(registro[10], float)
        assert isinstance(registro[11], float)
    finally:
        con.close()


def test_transformar_bases_preserva_quantidade_registros_e_realiza_joins(
    tmp_path: Path,
) -> None:
    caminho_banco = tmp_path / "teste_joins.duckdb"
    treino_com_ausente = list(_DADOS_TREINO_PADRAO) + [
        ("99", "1", "2010-02-05", "100.00", "FALSE"),
    ]
    features_com_ausente = list(_DADOS_FEATURES_PADRAO) + [
        (
            "99",
            "2010-02-05",
            "45.0",
            "3.0",
            "NA",
            "NA",
            "NA",
            "NA",
            "NA",
            "200.0",
            "7.0",
            "FALSE",
        )
    ]
    _criar_dados_brutos(
        caminho_banco,
        treino=treino_com_ausente,
        features=features_com_ausente,
    )

    resultado = transformar_bases(caminho_banco)

    assert resultado["processado.treino_base"] == len(treino_com_ausente)
    assert resultado["processado.teste_base"] == len(_DADOS_TESTE_PADRAO)
    assert resultado["treino_sem_loja"] == 1
    assert resultado["treino_sem_features"] == 0
    assert resultado["teste_sem_loja"] == 0
    assert resultado["teste_sem_features"] == 0

    con = conectar(caminho_banco)
    try:
        contagem_treino = con.execute(
            "SELECT COUNT(*) FROM processado.treino_base"
        ).fetchone()[0]
        contagem_teste = con.execute(
            "SELECT COUNT(*) FROM processado.teste_base"
        ).fetchone()[0]
        assert contagem_treino == 4
        assert contagem_teste == 2

        linha_integrada = con.execute(
            """
            SELECT Store_Type, Store_Size, Temperature, Fuel_Price
            FROM processado.treino_base
            WHERE Store = 1 AND Dept = 1
            """
        ).fetchone()
        assert linha_integrada == ("A", 151315.0, 42.31, 2.572)

        linha_sem_loja = con.execute(
            """
            SELECT Store_Type, Store_Size, Temperature
            FROM processado.treino_base
            WHERE Store = 99
            """
        ).fetchone()
        assert linha_sem_loja == (None, None, 45.0)
    finally:
        con.close()


def test_transformar_bases_converte_na_para_null_e_gera_indicadores_missing(
    tmp_path: Path,
) -> None:
    caminho_banco = tmp_path / "teste_missing.duckdb"
    _criar_dados_brutos(caminho_banco)

    transformar_bases(caminho_banco)

    con = conectar(caminho_banco)
    try:
        linha_store1 = con.execute(
            """
            SELECT
                MarkDown1, MarkDown2, MarkDown3, MarkDown4, MarkDown5,
                MarkDown1_missing, MarkDown2_missing, MarkDown3_missing,
                MarkDown4_missing, MarkDown5_missing,
                CPI, CPI_missing,
                Unemployment, Unemployment_missing
            FROM processado.treino_base
            WHERE Store = 1 AND Dept = 1
            """
        ).fetchone()

        assert linha_store1[0:5] == (None, None, None, None, None)
        assert linha_store1[5:10] == (True, True, True, True, True)
        assert linha_store1[10] == pytest.approx(211.096358)
        assert linha_store1[11] is False
        assert linha_store1[12] == pytest.approx(8.106)
        assert linha_store1[13] is False

        linha_store2 = con.execute(
            """
            SELECT
                MarkDown1, MarkDown2, MarkDown3, MarkDown4, MarkDown5,
                MarkDown1_missing, MarkDown2_missing, MarkDown3_missing,
                MarkDown4_missing, MarkDown5_missing,
                CPI, CPI_missing,
                Unemployment, Unemployment_missing
            FROM processado.treino_base
            WHERE Store = 2 AND Dept = 1
            """
        ).fetchone()

        assert linha_store2[0:5] == (100.5, 200.0, 300.0, 400.0, 500.0)
        assert linha_store2[5:10] == (False, False, False, False, False)
        assert linha_store2[10] is None
        assert linha_store2[11] is True
        assert linha_store2[12] is None
        assert linha_store2[13] is True

        linha_teste = con.execute(
            """
            SELECT
                MarkDown1, MarkDown1_missing,
                MarkDown2, MarkDown2_missing,
                CPI, CPI_missing
            FROM processado.teste_base
            WHERE Store = 1 AND Dept = 1
            """
        ).fetchone()
        assert linha_teste[0] == pytest.approx(6766.44)
        assert linha_teste[1] is False
        assert linha_teste[2] is None
        assert linha_teste[3] is True
        assert linha_teste[4] == pytest.approx(223.46)
        assert linha_teste[5] is False
    finally:
        con.close()


def test_transformar_bases_preserva_vendas_negativas_e_zero(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "teste_vendas.duckdb"
    _criar_dados_brutos(caminho_banco)

    transformar_bases(caminho_banco)

    con = conectar(caminho_banco)
    try:
        vendas = con.execute(
            """
            SELECT Store, Dept, Weekly_Sales
            FROM processado.treino_base
            ORDER BY Store, Dept
            """
        ).fetchall()

        assert len(vendas) == 3
        assert vendas[0] == (1, 1, 24924.50)
        assert vendas[1] == (1, 2, -175.00)
        assert vendas[2] == (2, 1, 0.00)

        assert any(v[2] < 0 for v in vendas)
        assert any(v[2] == 0 for v in vendas)
    finally:
        con.close()


def test_processado_teste_base_nao_possui_coluna_weekly_sales(
    tmp_path: Path,
) -> None:
    caminho_banco = tmp_path / "teste_sem_alvo.duckdb"
    _criar_dados_brutos(caminho_banco)

    transformar_bases(caminho_banco)

    con = conectar(caminho_banco)
    try:
        colunas_teste = [
            linha[0]
            for linha in con.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'processado' AND table_name = 'teste_base'
                """
            ).fetchall()
        ]
        colunas_treino = [
            linha[0]
            for linha in con.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'processado' AND table_name = 'treino_base'
                """
            ).fetchall()
        ]

        assert "Weekly_Sales" not in colunas_teste
        assert "Weekly_Sales" in colunas_treino
        assert set(colunas_treino) - {"Weekly_Sales"} == set(colunas_teste)
    finally:
        con.close()


def test_rejeita_chaves_duplicadas_em_stores(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "duplicidade_stores.duckdb"
    stores_duplicadas = [
        ("1", "A", "151315"),
        ("1", "B", "202307"),
    ]
    _criar_dados_brutos(caminho_banco, stores=stores_duplicadas)

    with pytest.raises(
        ValueError,
        match=r"Chaves duplicadas nas tabelas complementares:.*bruto\.stores=1",
    ):
        transformar_bases(caminho_banco)


def test_rejeita_chaves_duplicadas_em_features(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "duplicidade_features.duckdb"
    features_duplicadas = list(_DADOS_FEATURES_PADRAO) + [_DADOS_FEATURES_PADRAO[0]]
    _criar_dados_brutos(caminho_banco, features=features_duplicadas)

    with pytest.raises(
        ValueError,
        match=r"Chaves duplicadas nas tabelas complementares:.*bruto\.features=1",
    ):
        transformar_bases(caminho_banco)


@pytest.mark.parametrize(
    ("tabela", "campo", "valor_invalido"),
    [
        ("train", "Store", "invalido"),
        ("train", "Dept", "abc"),
        ("train", "Date", "2010-02-31"),
        ("train", "Weekly_Sales", "texto"),
        ("train", "IsHoliday", "talvez"),
        ("test", "Store", "invalido"),
        ("test", "Dept", "abc"),
        ("test", "Date", "data_invalida"),
        ("test", "IsHoliday", "indefinido"),
    ],
)
def test_rejeita_conversoes_invalidas_em_campos_obrigatorios(
    tmp_path: Path, tabela: str, campo: str, valor_invalido: str
) -> None:
    caminho_banco = tmp_path / f"invalido_{tabela}_{campo}.duckdb"
    data_alvo = "2010-02-05" if tabela == "train" else "2012-11-02"
    features = [
        (
            linha[0],
            linha[1],
            linha[2],
            linha[3],
            linha[4],
            linha[5],
            linha[6],
            linha[7],
            linha[8],
            linha[9],
            linha[10],
            (
                valor_invalido
                if campo == "IsHoliday" and linha[1] == data_alvo
                else linha[11]
            ),
        )
        for linha in _DADOS_FEATURES_PADRAO
    ]
    if tabela == "train":
        treino = [
            (
                valor_invalido if campo == "Store" else "1",
                valor_invalido if campo == "Dept" else "1",
                valor_invalido if campo == "Date" else "2010-02-05",
                valor_invalido if campo == "Weekly_Sales" else "24924.50",
                valor_invalido if campo == "IsHoliday" else "FALSE",
            )
        ]
        _criar_dados_brutos(caminho_banco, treino=treino, features=features)
    else:
        teste = [
            (
                valor_invalido if campo == "Store" else "1",
                valor_invalido if campo == "Dept" else "1",
                valor_invalido if campo == "Date" else "2012-11-02",
                valor_invalido if campo == "IsHoliday" else "FALSE",
            )
        ]
        _criar_dados_brutos(caminho_banco, teste=teste, features=features)

    with pytest.raises(
        ValueError,
        match=r"Conversões inválidas ou valores ausentes em campos obrigatórios",
    ):
        transformar_bases(caminho_banco)


def test_falha_na_transformacao_executa_rollback(tmp_path: Path) -> None:
    caminho_banco = tmp_path / "teste_rollback.duckdb"
    con = conectar(caminho_banco)
    try:
        criar_schemas(con)
        con.execute("CREATE TABLE processado.treino_base (conteudo VARCHAR)")
        con.execute("INSERT INTO processado.treino_base VALUES ('versao_original')")
    finally:
        con.close()

    # Inserir duplicidade em Store + Dept + Date em treino, que é validada
    # após a criação das tabelas processadas na transação.
    treino_com_duplicidade = [
        ("1", "1", "2010-02-05", "100.00", "FALSE"),
        ("1", "1", "2010-02-05", "200.00", "FALSE"),
    ]
    _criar_dados_brutos(caminho_banco, treino=treino_com_duplicidade)

    with pytest.raises(
        ValueError,
        match=r"Chave Store \+ Dept \+ Date duplicada após transformação",
    ):
        transformar_bases(caminho_banco)

    con = conectar(caminho_banco)
    try:
        linhas = con.execute("SELECT * FROM processado.treino_base").fetchall()
        assert linhas == [("versao_original",)]
    finally:
        con.close()


def test_rejeita_divergencia_is_holiday_entre_vendas_e_features(
    tmp_path: Path,
) -> None:
    caminho_banco = tmp_path / "divergencia_feriado.duckdb"
    treino = [("1", "1", "2010-02-05", "100.00", "FALSE")]
    features = [
        (
            "1",
            "2010-02-05",
            "42.31",
            "2.572",
            "NA",
            "NA",
            "NA",
            "NA",
            "NA",
            "211.0",
            "8.1",
            "TRUE",  # Divergente de treino (FALSE)
        )
    ]
    _criar_dados_brutos(caminho_banco, treino=treino, features=features)

    with pytest.raises(
        ValueError,
        match=r"Valores de IsHoliday divergentes entre vendas e features",
    ):
        transformar_bases(caminho_banco)


def test_reexecucao_substitui_tabelas_processadas_com_sucesso(
    tmp_path: Path,
) -> None:
    caminho_banco = tmp_path / "teste_idempotencia.duckdb"
    _criar_dados_brutos(caminho_banco)

    resultado1 = transformar_bases(caminho_banco)
    assert resultado1["processado.treino_base"] == 3

    treino_novo = [
        ("1", "1", "2010-02-05", "50000.00", "FALSE"),
    ]
    _criar_dados_brutos(caminho_banco, treino=treino_novo)

    resultado2 = transformar_bases(caminho_banco)
    assert resultado2["processado.treino_base"] == 1

    con = conectar(caminho_banco)
    try:
        valor = con.execute(
            "SELECT Weekly_Sales FROM processado.treino_base"
        ).fetchone()[0]
        assert valor == 50000.00
    finally:
        con.close()
