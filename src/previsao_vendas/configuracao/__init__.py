"""Caminhos centrais do projeto previsao-vendas."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CaminhosProjeto:
    """Caminhos usados pelo projeto, todos derivados de sua raiz."""

    raiz: Path

    @property
    def dados_brutos(self) -> Path:
        return self.raiz / "dados" / "brutos"

    @property
    def dados_intermediarios(self) -> Path:
        return self.raiz / "dados" / "intermediarios"

    @property
    def banco_duckdb(self) -> Path:
        return self.dados_intermediarios / "previsao_vendas.duckdb"

    @property
    def mlruns(self) -> Path:
        return self.raiz / "mlruns"


def obter_caminhos(raiz_projeto: Path | None = None) -> CaminhosProjeto:
    """Retorna os caminhos do projeto sem depender do diretório de trabalho.

    Quando ``raiz_projeto`` não é informado, a raiz é derivada da localização
    deste pacote no layout ``src/previsao_vendas``.
    """
    raiz = (
        Path(raiz_projeto).resolve()
        if raiz_projeto is not None
        else Path(__file__).resolve().parents[3]
    )
    return CaminhosProjeto(raiz=raiz)


__all__ = ["CaminhosProjeto", "obter_caminhos"]
