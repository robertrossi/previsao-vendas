"""Validação walk-forward expansiva com horizonte recursivo semanal."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from previsao_vendas.avaliacao.metricas import mae, rmse, wmae
from previsao_vendas.modelos.previsao_recursiva import Preditor, prever_recursivamente

Linha = Mapping[str, Any]
CriarPreditor = Callable[[Sequence[Linha]], Preditor]


def validar_temporal(
    dados: Sequence[Linha],
    criar_preditor: CriarPreditor,
    *,
    tamanho_treino_minimo: int,
    horizonte: int,
    passo: int | None = None,
    max_janelas: int | None = None,
) -> list[dict[str, Any]]:
    """Executa janelas cronológicas expansivas, sem expor alvos futuros ao modelo.

    ``criar_preditor`` recebe exclusivamente as linhas de treino da janela e
    devolve uma função que prevê uma lista de atributos por chamada.
    """
    if tamanho_treino_minimo < 1 or horizonte < 1 or (passo is not None and passo < 1):
        raise ValueError("Treino, horizonte e passo devem ser positivos.")
    datas = sorted({r["Date"] for r in dados})
    if tamanho_treino_minimo >= len(datas):
        raise ValueError("Não há datas suficientes após o período mínimo de treino.")
    passo = horizonte if passo is None else passo
    resultados: list[dict[str, Any]] = []
    inicio = tamanho_treino_minimo
    while inicio < len(datas) and (
        max_janelas is None or len(resultados) < max_janelas
    ):
        datas_validacao = set(datas[inicio : inicio + horizonte])
        if not datas_validacao:
            break
        corte = datas[inicio]
        treino = [r for r in dados if r["Date"] < corte]
        validacao = [r for r in dados if r["Date"] in datas_validacao]
        preditor = criar_preditor(treino)
        previstos = prever_recursivamente(treino, validacao, preditor)
        reais = [float(r["Weekly_Sales"]) for r in validacao]
        estimados = [r["Weekly_Sales_previsto"] for r in previstos]
        feriados = [bool(r.get("IsHoliday", False)) for r in validacao]
        resultados.append(
            {
                "data_corte": corte,
                "data_fim": max(datas_validacao),
                "treino": treino,
                "previsoes": previstos,
                "mae": mae(reais, estimados),
                "rmse": rmse(reais, estimados),
                "wmae": wmae(reais, estimados, feriados),
            }
        )
        inicio += passo
    return resultados


__all__ = ["validar_temporal"]
