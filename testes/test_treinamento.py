import csv
from datetime import date, timedelta

from previsao_vendas.banco_dados import conectar
from previsao_vendas.modelos import treinamento


def _registro(data: date, venda: float) -> dict[str, object]:
    return {
        "Store": 1,
        "Dept": 1,
        "Date": data,
        "Weekly_Sales": venda,
        "IsHoliday": False,
        "Store_Type": "A",
        "Year": data.year,
        "Month": data.month,
        "Week": data.isocalendar().week,
        "Quarter": (data.month - 1) // 3 + 1,
        "DayOfYear": data.timetuple().tm_yday,
    }


def test_baseline_usa_lag_sazonal() -> None:
    preditor = treinamento.criar_baseline_sazonal([])
    assert preditor([{"lag_52": 123.5}, {"lag_52": None}]) == [123.5, 0.0]


def test_treina_compara_e_salva_no_formato_sample_submission(tmp_path, monkeypatch):
    banco = tmp_path / "modelo.duckdb"
    con = conectar(banco)
    con.execute("CREATE SCHEMA features")
    con.execute("CREATE SCHEMA bruto")
    datas = [date(2020, 1, 3) + timedelta(weeks=i) for i in range(5)]
    treino = [_registro(d, float(i + 1)) for i, d in enumerate(datas[:3])]
    teste = [{**_registro(d, 99999), "Weekly_Sales": None} for d in datas[3:]]
    for schema, table, rows in (
        ("features", "treino_modelagem", treino),
        ("features", "teste_modelagem", teste),
    ):
        cols = list(rows[0])
        tipos = []
        for coluna in cols:
            valor = next((r[coluna] for r in rows if r[coluna] is not None), None)
            tipo = (
                "BOOLEAN"
                if isinstance(valor, bool)
                else (
                    "INTEGER"
                    if isinstance(valor, int)
                    else "DOUBLE"
                    if isinstance(valor, float)
                    else "DATE"
                    if isinstance(valor, date)
                    else "VARCHAR"
                )
            )
            tipos.append(f'"{coluna}" {tipo}')
        con.execute(f"CREATE TABLE {schema}.{table} ({', '.join(tipos)})")
        con.executemany(
            f"INSERT INTO {schema}.{table} VALUES ({', '.join('?' for _ in cols)})",
            [tuple(row[c] for c in cols) for row in rows],
        )
    con.execute(
        "CREATE TABLE bruto.sample_submission (Id VARCHAR, Weekly_Sales DOUBLE)"
    )
    ids = [f"1_1_{d.isoformat()}" for d in datas[3:]]
    con.executemany(
        "INSERT INTO bruto.sample_submission VALUES (?, 0)", [(i,) for i in ids]
    )
    con.close()

    def fake_xgb(rows, *, num_boost_round):
        return lambda features: [float(row.get("lag_1") or 0) for row in features]

    monkeypatch.setattr(treinamento, "criar_preditor_xgboost", fake_xgb)
    arquivo = tmp_path / "submission.csv"
    resultado = treinamento.treinar_comparar_e_prever(
        banco,
        arquivo,
        tamanho_treino_minimo=2,
        horizonte_validacao=1,
        max_janelas=1,
    )
    assert set(resultado["metricas"]) == {"baseline_sazonal_52", "xgboost"}
    assert resultado["melhor_modelo"] in resultado["metricas"]
    with arquivo.open(encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    assert [linha["Id"] for linha in linhas] == ids
    assert all(set(linha) == {"Id", "Weekly_Sales"} for linha in linhas)
    assert len(linhas) == 2
