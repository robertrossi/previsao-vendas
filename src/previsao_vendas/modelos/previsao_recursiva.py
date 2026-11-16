"""Previsões em horizonte semanal usando apenas observações passadas."""

from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta
from typing import Any

Linha = Mapping[str, Any]
Preditor = Callable[[Sequence[dict[str, Any]]], Sequence[float]]


def _atributos_dinamicos(
    linha: Linha, historico: Mapping[Any, float]
) -> dict[str, Any]:
    """Recalcula lags e janelas para uma data usando somente o histórico disponível."""
    data = linha["Date"]
    saida = dict(linha)
    saida.pop("Weekly_Sales", None)
    for semanas in (1, 2, 4, 52):
        valor = historico.get(data - timedelta(weeks=semanas))
        saida[f"lag_{semanas}"] = valor
        saida[f"lag_{semanas}_disponivel"] = valor is not None
    for tamanho in (4, 8):
        valores = [
            valor
            for semanas in range(1, tamanho + 1)
            if (valor := historico.get(data - timedelta(weeks=semanas))) is not None
        ]
        saida[f"rolling_count_{tamanho}"] = len(valores)
        saida[f"rolling_mean_{tamanho}"] = (
            sum(valores) / len(valores) if valores else None
        )
        if tamanho == 4:
            media = saida["rolling_mean_4"]
            saida["rolling_std_4"] = (
                (sum((v - media) ** 2 for v in valores) / (len(valores) - 1)) ** 0.5
                if len(valores) > 1
                else None
            )
    return saida


def prever_recursivamente(
    historico_treino: Sequence[Linha], futuro: Sequence[Linha], preditor: Preditor
) -> list[dict[str, Any]]:
    """Prevê datas em ordem; vendas previstas só entram no histórico na data seguinte.

    As linhas futuras podem conter alvo por conveniência da validação; o alvo é
    descartado antes de serem passadas ao preditor.
    """
    if not futuro:
        return []
    datas = sorted({r["Date"] for r in futuro})
    if list(dict.fromkeys(r["Date"] for r in futuro)) != datas:
        raise ValueError("As linhas futuras devem estar ordenadas cronologicamente.")
    historico: dict[tuple[Any, Any], dict[Any, float]] = {}
    for linha in historico_treino:
        serie = historico.setdefault((linha["Store"], linha["Dept"]), {})
        serie[linha["Date"]] = float(linha["Weekly_Sales"])
    resultados: list[dict[str, Any]] = []
    for data in datas:
        linhas_data = [r for r in futuro if r["Date"] == data]
        entrada = [
            _atributos_dinamicos(
                linha,
                historico.get((linha["Store"], linha["Dept"]), {}),
            )
            for linha in linhas_data
        ]
        previsoes = list(preditor(entrada))
        if len(previsoes) != len(linhas_data):
            raise ValueError("O preditor deve retornar uma previsão por linha.")
        for linha, previsao in zip(linhas_data, previsoes, strict=True):
            resultado = dict(linha)
            resultado["Weekly_Sales_previsto"] = float(previsao)
            resultados.append(resultado)
        # Atualiza só depois de prever todas as séries da mesma semana.
        for linha, previsao in zip(linhas_data, previsoes, strict=True):
            chave = (linha["Store"], linha["Dept"])
            historico.setdefault(chave, {})[data] = float(previsao)
    return resultados


__all__ = ["Preditor", "prever_recursivamente"]
