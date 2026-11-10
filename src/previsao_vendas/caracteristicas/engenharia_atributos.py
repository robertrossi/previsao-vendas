"""Engenharia de atributos temporais e históricos para treino e teste.

Este módulo constrói as tabelas `features.treino_modelagem` e
`features.teste_modelagem` a partir das bases tipadas e integradas em
`processado`, respeitando rigorosamente as restrições temporais para evitar
vazamento de dados (data leakage):

1. Atributos de calendário:
   - Derivados de `Date`: `Year`, `Month`, `Week`, `Quarter` e `DayOfYear`.
   - Gerados tanto para treino quanto para teste.

2. Atributos históricos de vendas (somente treino nesta etapa):
   - Agrupados por `Store` e `Dept`.
   - Lags definidos pela diferença exata de calendário:
     - `lag_1`: venda exatamente 1 semana (7 dias) antes.
     - `lag_2`: venda exatamente 2 semanas (14 dias) antes.
     - `lag_4`: venda exatamente 4 semanas (28 dias) antes.
     - `lag_52`: venda exatamente 52 semanas (364 dias) antes.
   - Indicadores de disponibilidade dos lags (`lag_X_disponivel`):
     - Booleano indicando se a observação correspondente existia no histórico.
   - Estatísticas móveis em janelas estritas de calendário:
     - Janela de 4 semanas: de 28 dias a 7 dias antes da data prevista.
     - Janela de 8 semanas: de 56 dias a 7 dias antes da data prevista.
     - Excluem a semana prevista e semanas futuras.
     - `rolling_mean_4` e `rolling_mean_8`: média das vendas observadas.
     - `rolling_std_4`: desvio-padrão amostral (NULL se houver menos de 2
       observações na janela).
     - `rolling_count_4` e `rolling_count_8`: contagem de observações válidas
       presentes na respectiva janela (sem preenchimento artificial por zero).

3. Separação entre treino e teste:
   - `features.teste_modelagem` recebe inicialmente apenas os atributos
     conhecidos antecipadamente (loja, departamento, variáveis externas e
     calendário).
   - Nenhuma venda real do conjunto de teste é utilizada.
   - Os lags e atributos históricos dinâmicos do teste serão atualizados
     exclusivamente na etapa posterior de previsão recursiva.
"""

from pathlib import Path

from previsao_vendas.banco_dados import conectar, criar_schemas


def gerar_atributos(
    caminho_banco: str | Path | None = None,
) -> dict[str, int]:
    """Gera atributos de calendário e históricos para modelagem.

    Cria ou substitui as tabelas `features.treino_modelagem` e
    `features.teste_modelagem` no DuckDB. Retorna um dicionário com as
    contagens de saída e indicadores de disponibilidade dos lags.
    """
    con = conectar(caminho_banco)
    try:
        criar_schemas(con)
        con.execute("CREATE SCHEMA IF NOT EXISTS features")

        con.execute("BEGIN TRANSACTION")
        try:
            tabelas_existentes = {
                linha[0]
                for linha in con.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'processado'
                    """
                ).fetchall()
            }
            if (
                "treino_base" not in tabelas_existentes
                or "teste_base" not in tabelas_existentes
            ):
                raise ValueError(
                    "Tabelas processado.treino_base e processado.teste_base "
                    "são necessárias para a engenharia de atributos."
                )

            quantidade_treino = con.execute(
                "SELECT COUNT(*) FROM processado.treino_base"
            ).fetchone()[0]
            quantidade_teste = con.execute(
                "SELECT COUNT(*) FROM processado.teste_base"
            ).fetchone()[0]

            con.execute(
                """
                CREATE OR REPLACE TABLE features.treino_modelagem AS
                WITH estatisticas_moveis AS (
                    SELECT
                        Store,
                        Dept,
                        Date,
                        AVG(Weekly_Sales) OVER w4 AS rolling_mean_4,
                        AVG(Weekly_Sales) OVER w8 AS rolling_mean_8,
                        STDDEV_SAMP(Weekly_Sales) OVER w4 AS rolling_std_4,
                        COUNT(Weekly_Sales) OVER w4::INTEGER AS rolling_count_4,
                        COUNT(Weekly_Sales) OVER w8::INTEGER AS rolling_count_8
                    FROM processado.treino_base
                    WINDOW
                        w4 AS (
                            PARTITION BY Store, Dept
                            ORDER BY Date
                            RANGE BETWEEN INTERVAL 28 DAY PRECEDING
                                      AND INTERVAL 7 DAY PRECEDING
                        ),
                        w8 AS (
                            PARTITION BY Store, Dept
                            ORDER BY Date
                            RANGE BETWEEN INTERVAL 56 DAY PRECEDING
                                      AND INTERVAL 7 DAY PRECEDING
                        )
                )
                SELECT
                    t.Store,
                    t.Dept,
                    t.Date,
                    t.Weekly_Sales,
                    t.IsHoliday,
                    t.Store_Type,
                    t.Store_Size,
                    t.Temperature,
                    t.Fuel_Price,
                    t.MarkDown1,
                    t.MarkDown2,
                    t.MarkDown3,
                    t.MarkDown4,
                    t.MarkDown5,
                    t.CPI,
                    t.Unemployment,
                    t.MarkDown1_missing,
                    t.MarkDown2_missing,
                    t.MarkDown3_missing,
                    t.MarkDown4_missing,
                    t.MarkDown5_missing,
                    t.CPI_missing,
                    t.Unemployment_missing,
                    EXTRACT(year FROM t.Date)::INTEGER AS Year,
                    EXTRACT(month FROM t.Date)::INTEGER AS Month,
                    EXTRACT(week FROM t.Date)::INTEGER AS Week,
                    EXTRACT(quarter FROM t.Date)::INTEGER AS Quarter,
                    EXTRACT(doy FROM t.Date)::INTEGER AS DayOfYear,
                    l1.Weekly_Sales::DOUBLE AS lag_1,
                    l2.Weekly_Sales::DOUBLE AS lag_2,
                    l4.Weekly_Sales::DOUBLE AS lag_4,
                    l52.Weekly_Sales::DOUBLE AS lag_52,
                    (l1.Weekly_Sales IS NOT NULL)::BOOLEAN AS lag_1_disponivel,
                    (l2.Weekly_Sales IS NOT NULL)::BOOLEAN AS lag_2_disponivel,
                    (l4.Weekly_Sales IS NOT NULL)::BOOLEAN AS lag_4_disponivel,
                    (l52.Weekly_Sales IS NOT NULL)::BOOLEAN AS lag_52_disponivel,
                    em.rolling_mean_4::DOUBLE AS rolling_mean_4,
                    em.rolling_mean_8::DOUBLE AS rolling_mean_8,
                    em.rolling_std_4::DOUBLE AS rolling_std_4,
                    em.rolling_count_4::INTEGER AS rolling_count_4,
                    em.rolling_count_8::INTEGER AS rolling_count_8
                FROM processado.treino_base AS t
                INNER JOIN estatisticas_moveis AS em
                    ON t.Store = em.Store AND t.Dept = em.Dept AND t.Date = em.Date
                LEFT JOIN processado.treino_base AS l1
                    ON t.Store = l1.Store
                   AND t.Dept = l1.Dept
                   AND l1.Date = (t.Date - INTERVAL 1 WEEK)::DATE
                LEFT JOIN processado.treino_base AS l2
                    ON t.Store = l2.Store
                   AND t.Dept = l2.Dept
                   AND l2.Date = (t.Date - INTERVAL 2 WEEK)::DATE
                LEFT JOIN processado.treino_base AS l4
                    ON t.Store = l4.Store
                   AND t.Dept = l4.Dept
                   AND l4.Date = (t.Date - INTERVAL 4 WEEK)::DATE
                LEFT JOIN processado.treino_base AS l52
                    ON t.Store = l52.Store
                   AND t.Dept = l52.Dept
                   AND l52.Date = (t.Date - INTERVAL 52 WEEK)::DATE
                ORDER BY t.Store, t.Dept, t.Date
                """
            )

            con.execute(
                """
                CREATE OR REPLACE TABLE features.teste_modelagem AS
                SELECT
                    t.Store,
                    t.Dept,
                    t.Date,
                    t.IsHoliday,
                    t.Store_Type,
                    t.Store_Size,
                    t.Temperature,
                    t.Fuel_Price,
                    t.MarkDown1,
                    t.MarkDown2,
                    t.MarkDown3,
                    t.MarkDown4,
                    t.MarkDown5,
                    t.CPI,
                    t.Unemployment,
                    t.MarkDown1_missing,
                    t.MarkDown2_missing,
                    t.MarkDown3_missing,
                    t.MarkDown4_missing,
                    t.MarkDown5_missing,
                    t.CPI_missing,
                    t.Unemployment_missing,
                    EXTRACT(year FROM t.Date)::INTEGER AS Year,
                    EXTRACT(month FROM t.Date)::INTEGER AS Month,
                    EXTRACT(week FROM t.Date)::INTEGER AS Week,
                    EXTRACT(quarter FROM t.Date)::INTEGER AS Quarter,
                    EXTRACT(doy FROM t.Date)::INTEGER AS DayOfYear
                FROM processado.teste_base AS t
                ORDER BY t.Store, t.Dept, t.Date
                """
            )

            quantidade_treino_saida = con.execute(
                "SELECT COUNT(*) FROM features.treino_modelagem"
            ).fetchone()[0]
            quantidade_teste_saida = con.execute(
                "SELECT COUNT(*) FROM features.teste_modelagem"
            ).fetchone()[0]

            if quantidade_treino_saida != quantidade_treino:
                raise ValueError(
                    "A quantidade de linhas do treino mudou na geração de atributos: "
                    f"origem={quantidade_treino}, saída={quantidade_treino_saida}"
                )
            if quantidade_teste_saida != quantidade_teste:
                raise ValueError(
                    "A quantidade de linhas do teste mudou na geração de atributos: "
                    f"origem={quantidade_teste}, saída={quantidade_teste_saida}"
                )

            duplicidades_treino = con.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT Store, Dept, Date
                    FROM features.treino_modelagem
                    GROUP BY Store, Dept, Date
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]
            duplicidades_teste = con.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT Store, Dept, Date
                    FROM features.teste_modelagem
                    GROUP BY Store, Dept, Date
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]

            if duplicidades_treino or duplicidades_teste:
                raise ValueError(
                    "Chave Store + Dept + Date duplicada após geração de atributos: "
                    f"treino={duplicidades_treino}, teste={duplicidades_teste}"
                )

            contagem_lag_1 = con.execute(
                "SELECT COUNT(*) FROM features.treino_modelagem WHERE lag_1_disponivel"
            ).fetchone()[0]
            contagem_lag_2 = con.execute(
                "SELECT COUNT(*) FROM features.treino_modelagem WHERE lag_2_disponivel"
            ).fetchone()[0]
            contagem_lag_4 = con.execute(
                "SELECT COUNT(*) FROM features.treino_modelagem WHERE lag_4_disponivel"
            ).fetchone()[0]
            contagem_lag_52 = con.execute(
                "SELECT COUNT(*) FROM features.treino_modelagem WHERE lag_52_disponivel"
            ).fetchone()[0]

            con.execute("COMMIT")
            return {
                "features.treino_modelagem": quantidade_treino_saida,
                "features.teste_modelagem": quantidade_teste_saida,
                "treino_lag_1_disponivel": contagem_lag_1,
                "treino_lag_2_disponivel": contagem_lag_2,
                "treino_lag_4_disponivel": contagem_lag_4,
                "treino_lag_52_disponivel": contagem_lag_52,
            }
        except Exception:
            con.execute("ROLLBACK")
            raise
    finally:
        con.close()


gerar_caracteristicas = gerar_atributos

__all__ = ["gerar_atributos", "gerar_caracteristicas"]
