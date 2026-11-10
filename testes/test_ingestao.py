import csv
from pathlib import Path

import pytest

import previsao_vendas.ingestao as ingestao
from previsao_vendas.banco_dados import conectar, criar_schemas
from previsao_vendas.ingestao import ingerir_csvs

_DADOS_SINTETICOS = {
    "train.csv": (
        ("Store", "Dept", "Date", "Weekly_Sales", "IsHoliday"),
        (
            ("001", "07", "2012-11-02", "NA", "FALSE"),
            ("2", "1", "2012-11-09", "0", "TRUE"),
        ),
    ),
    "test.csv": (
        ("Store", "Dept", "Date", "IsHoliday"),
        (("001", "07", "2012-11-16", "FALSE"),),
    ),
    "stores.csv": (
        ("Store", "Type", "Size"),
        (("001", "A", "00100"),),
    ),
    "features.csv": (
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
        (
            (
                "001",
                "2012-11-02",
                "NA",
                "2.5",
                "",
                "NA",
                "0",
                "",
                "",
                "NA",
                "NA",
                "FALSE",
            ),
        ),
    ),
    "sampleSubmission.csv": (
        ("Id", "Weekly_Sales"),
        (("001_07_2012-11-16", "0"),),
    ),
}


def _criar_csvs(diretorio: Path) -> None:
    diretorio.mkdir(parents=True)
    for nome, (cabecalho, linhas) in _DADOS_SINTETICOS.items():
        with (diretorio / nome).open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(cabecalho)
            escritor.writerows(linhas)


def _ler_tabela(caminho_banco: Path, tabela: str) -> list[tuple[str, ...]]:
    con = conectar(caminho_banco)
    try:
        return con.execute(f'SELECT * FROM bruto."{tabela}"').fetchall()
    finally:
        con.close()


def test_ingerir_csvs_carrega_mapeamento_como_varchar_e_preserva_valores(
    tmp_path: Path,
) -> None:
    diretorio = tmp_path / "csvs"
    _criar_csvs(diretorio)
    caminho_banco = tmp_path / "temporario.duckdb"
    conteudo_original = {p.name: p.read_bytes() for p in diretorio.iterdir()}

    contagens = ingerir_csvs(diretorio, caminho_banco)

    assert contagens == {
        "bruto.train": 2,
        "bruto.test": 1,
        "bruto.stores": 1,
        "bruto.features": 1,
        "bruto.sample_submission": 1,
    }
    assert _ler_tabela(caminho_banco, "train")[0] == (
        "001",
        "07",
        "2012-11-02",
        "NA",
        "FALSE",
    )
    assert _ler_tabela(caminho_banco, "stores")[0] == ("001", "A", "00100")
    assert _ler_tabela(caminho_banco, "features")[0] == (
        "001",
        "2012-11-02",
        "NA",
        "2.5",
        "",
        "NA",
        "0",
        "",
        "",
        "NA",
        "NA",
        "FALSE",
    )

    con = conectar(caminho_banco)
    try:
        schemas = con.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'bruto'
            ORDER BY table_name, ordinal_position
            """
        ).fetchall()
        assert {linha[0] for linha in schemas} == {
            "train",
            "test",
            "stores",
            "features",
            "sample_submission",
        }
        assert all(tipo == "VARCHAR" for _, _, tipo in schemas)
        colunas_esperadas = {
            "train": _DADOS_SINTETICOS["train.csv"][0],
            "test": _DADOS_SINTETICOS["test.csv"][0],
            "stores": _DADOS_SINTETICOS["stores.csv"][0],
            "features": _DADOS_SINTETICOS["features.csv"][0],
            "sample_submission": _DADOS_SINTETICOS["sampleSubmission.csv"][0],
        }
        assert {
            tabela: tuple(
                coluna for nome_tabela, coluna, _ in schemas if nome_tabela == tabela
            )
            for tabela in colunas_esperadas
        } == colunas_esperadas
        counts = {
            table: con.execute(f'SELECT COUNT(*) FROM bruto."{table}"').fetchone()[0]
            for table in (
                "train",
                "test",
                "stores",
                "features",
                "sample_submission",
            )
        }
        assert counts == {
            "train": 2,
            "test": 1,
            "stores": 1,
            "features": 1,
            "sample_submission": 1,
        }
    finally:
        con.close()

    assert {p.name: p.read_bytes() for p in diretorio.iterdir()} == conteudo_original


def test_reexecucao_substitui_integralmente_as_tabelas(tmp_path: Path) -> None:
    diretorio = tmp_path / "csvs"
    _criar_csvs(diretorio)
    caminho_banco = tmp_path / "temporario.duckdb"
    ingerir_csvs(diretorio, caminho_banco)

    with (diretorio / "train.csv").open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(_DADOS_SINTETICOS["train.csv"][0])
        escritor.writerow(("3", "2", "2012-11-16", "12.5", "FALSE"))

    contagens = ingerir_csvs(diretorio, caminho_banco)

    assert contagens["bruto.train"] == 1
    assert _ler_tabela(caminho_banco, "train") == [
        ("3", "2", "2012-11-16", "12.5", "FALSE")
    ]


@pytest.mark.parametrize("tipo_erro", ["cabecalho", "largura"])
def test_rejeita_estrutura_invalida_antes_de_criar_o_banco(
    tmp_path: Path, tipo_erro: str
) -> None:
    diretorio = tmp_path / "csvs"
    _criar_csvs(diretorio)
    arquivo = diretorio / "train.csv"
    with arquivo.open("w", encoding="utf-8", newline="") as destino:
        escritor = csv.writer(destino)
        if tipo_erro == "cabecalho":
            escritor.writerow(("Dept", "Store", "Date", "Weekly_Sales", "IsHoliday"))
            escritor.writerow(("1", "1", "2012-11-02", "10", "FALSE"))
        else:
            escritor.writerow(_DADOS_SINTETICOS["train.csv"][0])
            escritor.writerow(("1", "1", "2012-11-02"))
    caminho_banco = tmp_path / "nao_criar.duckdb"

    with pytest.raises(ValueError):
        ingerir_csvs(diretorio, caminho_banco)

    assert not caminho_banco.exists()


def test_rejeita_arquivo_ausente_antes_de_criar_o_banco(tmp_path: Path) -> None:
    diretorio = tmp_path / "csvs"
    _criar_csvs(diretorio)
    (diretorio / "features.csv").unlink()
    caminho_banco = tmp_path / "nao_criar.duckdb"

    with pytest.raises(FileNotFoundError):
        ingerir_csvs(diretorio, caminho_banco)

    assert not caminho_banco.exists()


def test_falha_durante_substituicao_reverte_tabelas_anteriores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diretorio = tmp_path / "csvs"
    _criar_csvs(diretorio)
    caminho_banco = tmp_path / "temporario.duckdb"
    con = conectar(caminho_banco)
    try:
        criar_schemas(con)
        con.execute("CREATE TABLE bruto.train (valor VARCHAR)")
        con.execute("INSERT INTO bruto.train VALUES ('versao-anterior-train')")
        con.execute("CREATE TABLE bruto.test (valor VARCHAR)")
        con.execute("INSERT INTO bruto.test VALUES ('versao-anterior-test')")
    finally:
        con.close()

    substituir_original = ingestao._substituir_tabela

    def falhar_depois_de_substituir(
        con,
        tabela_temporaria: str,
        tabela_destino: str,
        quantidade_esperada: int,
    ) -> int:
        quantidade = substituir_original(
            con, tabela_temporaria, tabela_destino, quantidade_esperada
        )
        if tabela_destino == "test":
            raise RuntimeError("falha sintética durante a transação")
        return quantidade

    monkeypatch.setattr(ingestao, "_substituir_tabela", falhar_depois_de_substituir)

    with pytest.raises(RuntimeError, match="falha sintética"):
        ingerir_csvs(diretorio, caminho_banco)

    assert _ler_tabela(caminho_banco, "train") == [("versao-anterior-train",)]
    assert _ler_tabela(caminho_banco, "test") == [("versao-anterior-test",)]
