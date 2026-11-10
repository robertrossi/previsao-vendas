from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from previsao_vendas.configuracao import obter_caminhos


def test_obtem_caminhos_da_raiz_do_projeto_independente_do_diretorio(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    caminhos = obter_caminhos()
    raiz_esperada = Path(__file__).resolve().parents[1]

    assert caminhos.raiz == raiz_esperada
    assert caminhos.dados_brutos == raiz_esperada / "dados" / "brutos"
    assert caminhos.dados_intermediarios == raiz_esperada / "dados" / "intermediarios"
    assert (
        caminhos.banco_duckdb
        == raiz_esperada / "dados" / "intermediarios" / "previsao_vendas.duckdb"
    )
    assert caminhos.mlruns == raiz_esperada / "mlruns"


def test_permite_raiz_temporaria_para_isolar_caminhos(tmp_path: Path) -> None:
    raiz_temporaria = tmp_path / "projeto-teste"

    caminhos = obter_caminhos(raiz_temporaria)

    assert caminhos.raiz == raiz_temporaria.resolve()
    assert caminhos.dados_brutos == raiz_temporaria / "dados" / "brutos"
    assert caminhos.dados_intermediarios == raiz_temporaria / "dados" / "intermediarios"
    assert (
        caminhos.banco_duckdb
        == raiz_temporaria / "dados" / "intermediarios" / "previsao_vendas.duckdb"
    )
    assert caminhos.mlruns == raiz_temporaria / "mlruns"
    assert not raiz_temporaria.exists()


def test_instancia_de_caminhos_e_imutavel(tmp_path: Path) -> None:
    caminhos = obter_caminhos(tmp_path)

    with pytest.raises(FrozenInstanceError):
        caminhos.raiz = tmp_path / "outra-raiz"
