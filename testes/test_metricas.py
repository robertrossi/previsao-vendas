import math

import pytest

from previsao_vendas.avaliacao.metricas import (
    calcular_mae,
    calcular_rmse,
    calcular_wmae,
    mae,
    rmse,
    wmae,
)


def test_mae_calculo_correto() -> None:
    y_real = [100.0, 200.0, 300.0]
    y_previsto = [110.0, 190.0, 320.0]
    # Erros absolutos: 10, 10, 20 -> soma = 40 -> média = 40 / 3 = 13.3333...
    resultado = mae(y_real, y_previsto)
    assert resultado == pytest.approx(40.0 / 3.0)
    assert calcular_mae(y_real, y_previsto) == resultado


def test_rmse_calculo_correto() -> None:
    y_real = [100.0, 200.0, 300.0]
    y_previsto = [110.0, 190.0, 320.0]
    # Erros quadráticos: 100, 100, 400 -> soma = 600 -> média = 200
    resultado = rmse(y_real, y_previsto)
    assert resultado == pytest.approx(math.sqrt(200.0))
    assert calcular_rmse(y_real, y_previsto) == resultado


def test_wmae_calculo_correto_com_pesos_diferenciados() -> None:
    # Cenário:
    # Semana 1 (regular, peso 1): real 100, previsto 110 (erro = 10 * 1 = 10)
    # Semana 2 (feriado, peso 5): real 200, previsto 180 (erro = 20 * 5 = 100)
    # Soma dos erros ponderados: 10 + 100 = 110
    # Soma dos pesos: 1 + 5 = 6
    # WMAE esperado: 110 / 6 = 18.3333...
    y_real = [100.0, 200.0]
    y_previsto = [110.0, 180.0]
    e_feriado = [False, True]

    resultado = wmae(y_real, y_previsto, e_feriado)
    assert resultado == pytest.approx(110.0 / 6.0)
    assert calcular_wmae(y_real, y_previsto, e_feriado) == resultado


def test_metricas_com_previsao_perfeita_retornam_zero() -> None:
    y_real = [50.0, 120.0, 330.5]
    y_previsto = [50.0, 120.0, 330.5]
    e_feriado = [False, True, False]

    assert mae(y_real, y_previsto) == 0.0
    assert rmse(y_real, y_previsto) == 0.0
    assert wmae(y_real, y_previsto, e_feriado) == 0.0


def test_wmae_quando_todos_sao_feriados_equivale_ao_mae() -> None:
    y_real = [10.0, 20.0, 30.0]
    y_previsto = [15.0, 18.0, 25.0]
    e_feriado = [True, True, True]

    assert wmae(y_real, y_previsto, e_feriado) == pytest.approx(
        mae(y_real, y_previsto)
    )


def test_wmae_quando_nenhum_e_feriado_equivale_ao_mae() -> None:
    y_real = [10.0, 20.0, 30.0]
    y_previsto = [15.0, 18.0, 25.0]
    e_feriado = [False, False, False]

    assert wmae(y_real, y_previsto, e_feriado) == pytest.approx(
        mae(y_real, y_previsto)
    )


def test_wmae_permite_pesos_customizados() -> None:
    y_real = [100.0, 200.0]
    y_previsto = [110.0, 190.0]
    e_feriado = [False, True]

    # Peso regular = 2.0, Peso feriado = 10.0
    # Erro regular = 10 * 2.0 = 20
    # Erro feriado = 10 * 10.0 = 100
    # Soma = 120 / (2.0 + 10.0) = 120 / 12 = 10.0
    resultado = wmae(
        y_real, y_previsto, e_feriado, peso_feriado=10.0, peso_regular=2.0
    )
    assert resultado == pytest.approx(10.0)


def test_rejeita_sequencias_vazias() -> None:
    with pytest.raises(ValueError, match="não podem estar vazias"):
        mae([], [])

    with pytest.raises(ValueError, match="não podem estar vazias"):
        rmse([], [])

    with pytest.raises(ValueError, match="não podem estar vazias"):
        wmae([], [], [])


def test_rejeita_sequencias_com_tamanhos_diferentes() -> None:
    with pytest.raises(ValueError, match="mesmo tamanho"):
        mae([1.0, 2.0], [1.0])

    with pytest.raises(ValueError, match="mesmo tamanho"):
        rmse([1.0, 2.0], [1.0])

    with pytest.raises(ValueError, match="mesmo tamanho"):
        wmae([1.0, 2.0], [1.0], [False, True])

    with pytest.raises(
        ValueError, match="mesmo tamanho que os valores reais"
    ):
        wmae([1.0, 2.0], [1.0, 2.0], [False])


def test_suporta_diferentes_tipos_de_sequencias() -> None:
    y_real = (10, 20, 30)
    y_previsto = (12.0, 18.0, 30.0)
    e_feriado = (1, 0, 0)

    assert mae(y_real, y_previsto) == pytest.approx(4.0 / 3.0)
    assert rmse(y_real, y_previsto) == pytest.approx(math.sqrt(8.0 / 3.0))
    # wmae: feriado no item 1 (5 * 2 = 10), item 2 (1 * 2 = 2), item 3 (0) -> 12 / 7
    assert wmae(y_real, y_previsto, e_feriado) == pytest.approx(12.0 / 7.0)
