"""Métricas de avaliação de desempenho para previsão de vendas.

Implementa as métricas previstas na especificação do projeto:
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- WMAE (Weighted Mean Absolute Error): métrica oficial da competição Walmart,
  que atribui peso 5 para observações em semanas de feriado e peso 1 para
  semanas normais.
"""

import math
from collections.abc import Sequence


def mae(y_real: Sequence[float], y_previsto: Sequence[float]) -> float:
    """Calcula o Erro Médio Absoluto (Mean Absolute Error - MAE).

    Fórmula:
        MAE = (1 / n) * sum(|y_i - y_pred_i|)

    Args:
        y_real: Sequência de valores observados reais.
        y_previsto: Sequência de valores previstos.

    Returns:
        Valor do MAE como float.

    Raises:
        ValueError: Se as sequências estiverem vazias ou tiverem tamanhos
            diferentes.
    """
    _validar_sequencias(y_real, y_previsto)
    total_erro = sum(abs(r - p) for r, p in zip(y_real, y_previsto, strict=True))
    return total_erro / len(y_real)


def rmse(y_real: Sequence[float], y_previsto: Sequence[float]) -> float:
    """Calcula a Raiz do Erro Quadrático Médio (Root Mean Squared Error - RMSE).

    Fórmula:
        RMSE = sqrt((1 / n) * sum((y_i - y_pred_i)^2))

    Args:
        y_real: Sequência de valores observados reais.
        y_previsto: Sequência de valores previstos.

    Returns:
        Valor do RMSE como float.

    Raises:
        ValueError: Se as sequências estiverem vazias ou tiverem tamanhos
            diferentes.
    """
    _validar_sequencias(y_real, y_previsto)
    total_erro_quadratico = sum(
        (r - p) ** 2 for r, p in zip(y_real, y_previsto, strict=True)
    )
    return math.sqrt(total_erro_quadratico / len(y_real))


def wmae(
    y_real: Sequence[float],
    y_previsto: Sequence[float],
    e_feriado: Sequence[bool],
    peso_feriado: float = 5.0,
    peso_regular: float = 1.0,
) -> float:
    """Calcula o Erro Médio Absoluto Ponderado (Weighted Mean Absolute Error - WMAE).

    Fórmula:
        WMAE = sum(w_i * |y_i - y_pred_i|) / sum(w_i)

        onde:
            w_i = peso_feriado (padrão 5.0) se e_feriado[i] for True
            w_i = peso_regular (padrão 1.0) se e_feriado[i] for False

    Args:
        y_real: Sequência de valores observados reais.
        y_previsto: Sequência de valores previstos.
        e_feriado: Sequência booleana indicando se a observação ocorreu em feriado.
        peso_feriado: Peso atribuído às semanas de feriado (padrão 5.0).
        peso_regular: Peso atribuído às semanas normais (padrão 1.0).

    Returns:
        Valor do WMAE como float.

    Raises:
        ValueError: Se as sequências estiverem vazias ou tiverem comprimentos
            incompatíveis.
    """
    _validar_sequencias(y_real, y_previsto)
    if len(y_real) != len(e_feriado):
        raise ValueError(
            "A sequência do indicador de feriado deve ter o mesmo tamanho que "
            f"os valores reais: y_real={len(y_real)}, e_feriado={len(e_feriado)}"
        )

    soma_ponderada_erros = 0.0
    soma_pesos = 0.0

    for r, p, feriado in zip(y_real, y_previsto, e_feriado, strict=True):
        peso = peso_feriado if bool(feriado) else peso_regular
        soma_ponderada_erros += peso * abs(r - p)
        soma_pesos += peso

    if soma_pesos == 0.0:
        raise ValueError("A soma dos pesos não pode ser zero.")

    return soma_ponderada_erros / soma_pesos


def _validar_sequencias(
    y_real: Sequence[float],
    y_previsto: Sequence[float],
) -> None:
    """Valida se as sequências não estão vazias e possuem o mesmo comprimento."""
    if len(y_real) == 0:
        raise ValueError("As sequências de valores não podem estar vazias.")
    if len(y_real) != len(y_previsto):
        raise ValueError(
            "As sequências de valores reais e previstos devem ter o mesmo tamanho: "
            f"y_real={len(y_real)}, y_previsto={len(y_previsto)}"
        )


calcular_mae = mae
calcular_rmse = rmse
calcular_wmae = wmae

__all__ = [
    "calcular_mae",
    "calcular_rmse",
    "calcular_wmae",
    "mae",
    "rmse",
    "wmae",
]
