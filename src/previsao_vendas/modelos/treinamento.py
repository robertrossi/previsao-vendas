"""Comparação walk-forward e geração do arquivo de submissão."""

import csv
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from previsao_vendas.avaliacao.metricas import mae, rmse, wmae
from previsao_vendas.avaliacao.validacao_temporal import validar_temporal
from previsao_vendas.banco_dados import conectar
from previsao_vendas.configuracao import obter_caminhos
from previsao_vendas.modelos.previsao_recursiva import Preditor, prever_recursivamente

Linha = Mapping[str, Any]
COLUNAS_MODELO = (
    "Store",
    "Dept",
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
    "lag_1",
    "lag_2",
    "lag_4",
    "lag_52",
    "lag_1_disponivel",
    "lag_2_disponivel",
    "lag_4_disponivel",
    "lag_52_disponivel",
    "rolling_mean_4",
    "rolling_mean_8",
    "rolling_std_4",
    "rolling_count_4",
    "rolling_count_8",
)
TIPOS_LOJA = ("A", "B", "C")


def _vetor(linha: Linha) -> list[float]:
    valores: list[float] = []
    for coluna in COLUNAS_MODELO:
        if coluna == "Store_Type":
            valores.extend(float(linha.get(coluna) == tipo) for tipo in TIPOS_LOJA)
            continue
        valor = linha.get(coluna)
        valores.append(float(valor) if valor is not None else math.nan)
    return valores


def criar_baseline_sazonal(_: Sequence[Linha]) -> Preditor:
    """Retorna o lag de 52 semanas; usa zero quando não há observação exata."""
    return lambda linhas: [float(linha.get("lag_52") or 0.0) for linha in linhas]


def criar_preditor_xgboost(
    treino: Sequence[Linha], *, num_boost_round: int = 120
) -> Preditor:
    """Treina XGBoost com os atributos existentes e codificação one-hot de loja."""
    try:
        import xgboost as xgb
    except ImportError as erro:
        raise RuntimeError(
            "XGBoost não está instalado. Instale as dependências do projeto."
        ) from erro
    if not treino:
        raise ValueError("O conjunto de treino não pode estar vazio.")
    matriz = xgb.DMatrix(
        [_vetor(linha) for linha in treino],
        label=[float(linha["Weekly_Sales"]) for linha in treino],
        feature_names=[
            f"{c}_{t}" if c == "Store_Type" else c
            for c in COLUNAS_MODELO
            for t in (TIPOS_LOJA if c == "Store_Type" else ("",))
        ],
        missing=math.nan,
    )
    modelo = xgb.train(
        {
            "objective": "reg:squarederror",
            "max_depth": 6,
            "eta": 0.08,
            "subsample": 0.85,
            "colsample_bytree": 0.9,
            "nthread": 4,
            "seed": 42,
            "verbosity": 0,
        },
        matriz,
        num_boost_round=num_boost_round,
    )
    nomes = matriz.feature_names

    def prever(linhas: Sequence[dict[str, Any]]) -> Sequence[float]:
        entrada = xgb.DMatrix(
            [_vetor(linha) for linha in linhas], feature_names=nomes, missing=math.nan
        )
        return modelo.predict(entrada).tolist()

    return prever


def _ler_tabela(con: Any, schema: str, tabela: str) -> list[dict[str, Any]]:
    cursor = con.execute(f"SELECT * FROM {schema}.{tabela}")
    nomes = [coluna[0] for coluna in cursor.description]
    return [dict(zip(nomes, linha, strict=True)) for linha in cursor.fetchall()]


def treinar_comparar_e_prever(
    caminho_banco: str | Path | None = None,
    arquivo_submissao: str | Path | None = None,
    *,
    tamanho_treino_minimo: int = 100,
    horizonte_validacao: int = 39,
    max_janelas: int = 2,
    num_boost_round: int = 120,
) -> dict[str, Any]:
    """Compara baseline e XGBoost, retreina o vencedor e grava a submissão.

    Pressupõe que ingestão, transformação e engenharia de atributos já foram
    executadas, preservando seus dados e convenções.
    """
    caminhos = obter_caminhos()
    destino = (
        Path(arquivo_submissao)
        if arquivo_submissao
        else (caminhos.raiz / "dados" / "processados" / "submission.csv")
    )
    con = conectar(caminho_banco)
    try:
        treino = _ler_tabela(con, "features", "treino_modelagem")
        teste = _ler_tabela(con, "features", "teste_modelagem")
        amostra = _ler_tabela(con, "bruto", "sample_submission")
    finally:
        con.close()

    criadores = {
        "baseline_sazonal_52": criar_baseline_sazonal,
        "xgboost": lambda linhas: criar_preditor_xgboost(
            linhas, num_boost_round=num_boost_round
        ),
    }
    relatorio: dict[str, dict[str, float]] = {}
    folds_por_modelo: dict[str, list[dict[str, Any]]] = {}
    for nome, criar in criadores.items():
        folds = validar_temporal(
            treino,
            criar,
            tamanho_treino_minimo=tamanho_treino_minimo,
            horizonte=horizonte_validacao,
            max_janelas=max_janelas,
        )
        if not folds:
            raise ValueError("A validação temporal não produziu janelas.")
        linhas_reais = [
            linha
            for fold in folds
            for linha in fold["previsoes"]
        ]
        reais = [float(linha["Weekly_Sales"]) for linha in linhas_reais]
        previstos = [float(linha["Weekly_Sales_previsto"]) for linha in linhas_reais]
        feriados = [bool(linha.get("IsHoliday", False)) for linha in linhas_reais]
        relatorio[nome] = {
            "mae": mae(reais, previstos),
            "rmse": rmse(reais, previstos),
            "wmae": wmae(reais, previstos, feriados),
        }
        folds_por_modelo[nome] = folds
    vencedor = min(relatorio, key=lambda nome: relatorio[nome]["wmae"])
    preditor_final = criadores[vencedor](treino)
    previsoes = prever_recursivamente(treino, teste, preditor_final)
    por_id = {
        f"{r['Store']}_{r['Dept']}_{r['Date']}": r["Weekly_Sales_previsto"]
        for r in previsoes
    }
    if len(por_id) != len(teste):
        raise ValueError(
            "A previsão não preservou a granularidade Store + Dept + Date."
        )
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(("Id", "Weekly_Sales"))
        for linha in amostra:
            identificador = str(linha["Id"])
            if identificador not in por_id:
                raise ValueError(
                    f"ID do sampleSubmission ausente nas previsões: {identificador}"
                )
            escritor.writerow((identificador, por_id[identificador]))
    if len(amostra) != len(teste):
        raise ValueError("A quantidade de IDs da amostra difere do conjunto de teste.")
    return {
        "metricas": relatorio,
        "melhor_modelo": vencedor,
        "janelas_validacao": {
            nome: [(f["data_corte"], f["data_fim"]) for f in folds]
            for nome, folds in folds_por_modelo.items()
        },
        "quantidade_previsoes": len(previsoes),
        "arquivo_submissao": destino,
    }


__all__ = [
    "criar_baseline_sazonal",
    "criar_preditor_xgboost",
    "treinar_comparar_e_prever",
]


if __name__ == "__main__":
    print(treinar_comparar_e_prever())
