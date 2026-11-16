from datetime import date, timedelta

import pytest

from previsao_vendas.avaliacao.validacao_temporal import validar_temporal
from previsao_vendas.modelos.previsao_recursiva import prever_recursivamente


def _linha(dia: int, venda: float) -> dict[str, object]:
    return {
        "Store": 1,
        "Dept": 2,
        "Date": date(2020, 1, 3) + timedelta(weeks=dia),
        "Weekly_Sales": venda,
        "IsHoliday": False,
    }


def test_previsao_recursiva_alimenta_lags_com_previsoes() -> None:
    treino = [_linha(0, 10), _linha(1, 20)]
    futuro = [_linha(2, 999), _linha(3, 888)]
    lags: list[float | None] = []

    def preditor(linhas):
        lags.extend(linha["lag_1"] for linha in linhas)
        return [float(linha["lag_1"] or 0) + 1 for linha in linhas]

    resultado = prever_recursivamente(treino, futuro, preditor)
    assert lags == [20.0, 21.0]
    assert [r["Weekly_Sales_previsto"] for r in resultado] == [21.0, 22.0]


def test_previsoes_nao_dependem_das_vendas_reais_futuras() -> None:
    treino = [_linha(0, 10), _linha(1, 20)]
    futuro_a = [_linha(2, 100), _linha(3, 200)]
    futuro_b = [_linha(2, -5000), _linha(3, 99999)]

    def preditor(xs):
        return [float(x["lag_1"] or 0) + 3 for x in xs]

    a = prever_recursivamente(treino, futuro_a, preditor)
    b = prever_recursivamente(treino, futuro_b, preditor)
    assert [r["Weekly_Sales_previsto"] for r in a] == [
        r["Weekly_Sales_previsto"] for r in b
    ]


def test_previsao_processa_todas_as_lojas_da_semana_antes_de_avancar() -> None:
    treino = [_linha(0, 10), {**_linha(0, 30), "Store": 2}]
    futuro = [_linha(1, 0), {**_linha(1, 0), "Store": 2}]
    chamadas: list[list[tuple[int, object]]] = []

    def preditor(linhas):
        chamadas.append([(linha["Store"], linha["Date"]) for linha in linhas])
        return [float(linha["lag_1"] or 0) + 1 for linha in linhas]

    prever_recursivamente(treino, futuro, preditor)
    assert len(chamadas) == 1
    assert chamadas[0] == [(1, futuro[0]["Date"]), (2, futuro[1]["Date"])]


def test_validacao_temporal_expansiva_sem_embaralhar() -> None:
    dados = [_linha(i, 10.0 + i) for i in range(6)]
    treinos_recebidos: list[list[object]] = []

    def criar_preditor(treino):
        treinos_recebidos.append([r["Date"] for r in treino])
        return lambda xs: [float(x["lag_1"] or 0) for x in xs]

    folds = validar_temporal(
        dados, criar_preditor, tamanho_treino_minimo=3, horizonte=2
    )
    assert len(folds) == 2
    assert treinos_recebidos[0] == [r["Date"] for r in dados[:3]]
    assert treinos_recebidos[1] == [r["Date"] for r in dados[:5]]
    assert folds[0]["data_corte"] < folds[0]["data_fim"]
    assert len(folds[0]["previsoes"]) == 2


def test_rejeita_futuro_fora_de_ordem() -> None:
    futuro = [_linha(2, 0), _linha(1, 0)]
    with pytest.raises(ValueError, match="ordenadas cronologicamente"):
        prever_recursivamente([], futuro, lambda xs: [0.0 for _ in xs])
