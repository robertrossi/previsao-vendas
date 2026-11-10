"""Transformações das bases brutas de treino e teste."""

from pathlib import Path

import duckdb

from previsao_vendas.banco_dados import conectar, criar_schemas


def transformar_bases(
    caminho_banco: str | Path | None = None,
) -> dict[str, int]:
    """Cria as bases tipadas e integradas de treino e teste.

    Retorna as contagens de saída e de registros sem correspondência nas
    tabelas complementares. As tabelas de origem permanecem inalteradas.
    """
    con = conectar(caminho_banco)
    try:
        criar_schemas(con)

        con.execute("BEGIN TRANSACTION")
        try:
            quantidade_treino = con.execute(
                "SELECT COUNT(*) FROM bruto.train"
            ).fetchone()[0]
            quantidade_teste = con.execute(
                "SELECT COUNT(*) FROM bruto.test"
            ).fetchone()[0]

            duplicidades_stores = con.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT Store
                    FROM bruto.stores
                    GROUP BY Store
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]
            duplicidades_features = con.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT Store, Date
                    FROM bruto.features
                    GROUP BY Store, Date
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]
            if duplicidades_stores or duplicidades_features:
                raise ValueError(
                    "Chaves duplicadas nas tabelas complementares: "
                    f"bruto.stores={duplicidades_stores}, "
                    f"bruto.features={duplicidades_features}"
                )

            divergencias_feriado_treino = con.execute(
                """
                SELECT COUNT(*)
                FROM bruto.train AS t
                INNER JOIN bruto.features AS f
                    ON t.Store = f.Store AND t.Date = f.Date
                WHERE t.IsHoliday IS DISTINCT FROM f.IsHoliday
                """
            ).fetchone()[0]
            divergencias_feriado_teste = con.execute(
                """
                SELECT COUNT(*)
                FROM bruto.test AS t
                INNER JOIN bruto.features AS f
                    ON t.Store = f.Store AND t.Date = f.Date
                WHERE t.IsHoliday IS DISTINCT FROM f.IsHoliday
                """
            ).fetchone()[0]
            if divergencias_feriado_treino or divergencias_feriado_teste:
                raise ValueError(
                    "Valores de IsHoliday divergentes entre vendas e features: "
                    f"treino={divergencias_feriado_treino}, "
                    f"teste={divergencias_feriado_teste}"
                )

            conversoes_invalidas_treino = con.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE TRY_CAST(t.Store AS INTEGER) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE TRY_CAST(t.Dept AS INTEGER) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE TRY_CAST(t.Date AS DATE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE TRY_CAST(t.IsHoliday AS BOOLEAN) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE TRY_CAST(t.Weekly_Sales AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE s.Size IS NOT NULL
                            AND TRY_CAST(s.Size AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.Temperature IS NOT NULL
                            AND TRY_CAST(f.Temperature AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.Fuel_Price IS NOT NULL
                            AND TRY_CAST(f.Fuel_Price AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.MarkDown1 IS NOT NULL
                            AND f.MarkDown1 <> 'NA'
                            AND TRY_CAST(f.MarkDown1 AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.MarkDown2 IS NOT NULL
                            AND f.MarkDown2 <> 'NA'
                            AND TRY_CAST(f.MarkDown2 AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.MarkDown3 IS NOT NULL
                            AND f.MarkDown3 <> 'NA'
                            AND TRY_CAST(f.MarkDown3 AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.MarkDown4 IS NOT NULL
                            AND f.MarkDown4 <> 'NA'
                            AND TRY_CAST(f.MarkDown4 AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.MarkDown5 IS NOT NULL
                            AND f.MarkDown5 <> 'NA'
                            AND TRY_CAST(f.MarkDown5 AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.CPI IS NOT NULL
                            AND f.CPI <> 'NA'
                            AND TRY_CAST(f.CPI AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.Unemployment IS NOT NULL
                            AND f.Unemployment <> 'NA'
                            AND TRY_CAST(f.Unemployment AS DOUBLE) IS NULL
                    )
                FROM bruto.train AS t
                LEFT JOIN bruto.stores AS s ON t.Store = s.Store
                LEFT JOIN bruto.features AS f
                    ON t.Store = f.Store AND t.Date = f.Date
                """
            ).fetchone()
            nomes_conversoes_treino = (
                "Store",
                "Dept",
                "Date",
                "IsHoliday",
                "Weekly_Sales",
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
            )
            invalidos_treino = dict(
                zip(nomes_conversoes_treino, conversoes_invalidas_treino, strict=True)
            )

            conversoes_invalidas_teste = con.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE TRY_CAST(t.Store AS INTEGER) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE TRY_CAST(t.Dept AS INTEGER) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE TRY_CAST(t.Date AS DATE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE TRY_CAST(t.IsHoliday AS BOOLEAN) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE s.Size IS NOT NULL
                            AND TRY_CAST(s.Size AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.Temperature IS NOT NULL
                            AND TRY_CAST(f.Temperature AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.Fuel_Price IS NOT NULL
                            AND TRY_CAST(f.Fuel_Price AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.MarkDown1 IS NOT NULL
                            AND f.MarkDown1 <> 'NA'
                            AND TRY_CAST(f.MarkDown1 AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.MarkDown2 IS NOT NULL
                            AND f.MarkDown2 <> 'NA'
                            AND TRY_CAST(f.MarkDown2 AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.MarkDown3 IS NOT NULL
                            AND f.MarkDown3 <> 'NA'
                            AND TRY_CAST(f.MarkDown3 AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.MarkDown4 IS NOT NULL
                            AND f.MarkDown4 <> 'NA'
                            AND TRY_CAST(f.MarkDown4 AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.MarkDown5 IS NOT NULL
                            AND f.MarkDown5 <> 'NA'
                            AND TRY_CAST(f.MarkDown5 AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.CPI IS NOT NULL
                            AND f.CPI <> 'NA'
                            AND TRY_CAST(f.CPI AS DOUBLE) IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE f.Unemployment IS NOT NULL
                            AND f.Unemployment <> 'NA'
                            AND TRY_CAST(f.Unemployment AS DOUBLE) IS NULL
                    )
                FROM bruto.test AS t
                LEFT JOIN bruto.stores AS s ON t.Store = s.Store
                LEFT JOIN bruto.features AS f
                    ON t.Store = f.Store AND t.Date = f.Date
                """
            ).fetchone()
            nomes_conversoes_teste = (
                "Store",
                "Dept",
                "Date",
                "IsHoliday",
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
            )
            invalidos_teste = dict(
                zip(nomes_conversoes_teste, conversoes_invalidas_teste, strict=True)
            )

            obrigatorios_invalidos = {
                f"treino.{coluna}": invalidos_treino[coluna]
                for coluna in ("Store", "Dept", "Date", "IsHoliday", "Weekly_Sales")
                if invalidos_treino[coluna]
            }
            obrigatorios_invalidos.update(
                {
                    f"teste.{coluna}": invalidos_teste[coluna]
                    for coluna in ("Store", "Dept", "Date", "IsHoliday")
                    if invalidos_teste[coluna]
                }
            )
            if obrigatorios_invalidos:
                detalhes = ", ".join(
                    f"{campo}={quantidade}"
                    for campo, quantidade in obrigatorios_invalidos.items()
                )
                raise ValueError(
                    "Conversões inválidas ou valores ausentes em campos "
                    f"obrigatórios: {detalhes}"
                )

            con.execute(
                """
                CREATE OR REPLACE TABLE processado.treino_base AS
                SELECT
                    TRY_CAST(t.Store AS INTEGER) AS Store,
                    TRY_CAST(t.Dept AS INTEGER) AS Dept,
                    TRY_CAST(t.Date AS DATE) AS Date,
                    TRY_CAST(t.Weekly_Sales AS DOUBLE) AS Weekly_Sales,
                    TRY_CAST(t.IsHoliday AS BOOLEAN) AS IsHoliday,
                    s.Type AS Store_Type,
                    TRY_CAST(s.Size AS DOUBLE) AS Store_Size,
                    TRY_CAST(f.Temperature AS DOUBLE) AS Temperature,
                    TRY_CAST(f.Fuel_Price AS DOUBLE) AS Fuel_Price,
                    TRY_CAST(NULLIF(f.MarkDown1, 'NA') AS DOUBLE) AS MarkDown1,
                    TRY_CAST(NULLIF(f.MarkDown2, 'NA') AS DOUBLE) AS MarkDown2,
                    TRY_CAST(NULLIF(f.MarkDown3, 'NA') AS DOUBLE) AS MarkDown3,
                    TRY_CAST(NULLIF(f.MarkDown4, 'NA') AS DOUBLE) AS MarkDown4,
                    TRY_CAST(NULLIF(f.MarkDown5, 'NA') AS DOUBLE) AS MarkDown5,
                    TRY_CAST(NULLIF(f.CPI, 'NA') AS DOUBLE) AS CPI,
                    TRY_CAST(NULLIF(f.Unemployment, 'NA') AS DOUBLE)
                        AS Unemployment,
                    COALESCE(f.MarkDown1 = 'NA', FALSE) AS MarkDown1_missing,
                    COALESCE(f.MarkDown2 = 'NA', FALSE) AS MarkDown2_missing,
                    COALESCE(f.MarkDown3 = 'NA', FALSE) AS MarkDown3_missing,
                    COALESCE(f.MarkDown4 = 'NA', FALSE) AS MarkDown4_missing,
                    COALESCE(f.MarkDown5 = 'NA', FALSE) AS MarkDown5_missing,
                    COALESCE(f.CPI = 'NA', FALSE) AS CPI_missing,
                    COALESCE(f.Unemployment = 'NA', FALSE) AS Unemployment_missing
                FROM bruto.train AS t
                LEFT JOIN bruto.stores AS s ON t.Store = s.Store
                LEFT JOIN bruto.features AS f
                    ON t.Store = f.Store AND t.Date = f.Date
                """
            )
            con.execute(
                """
                CREATE OR REPLACE TABLE processado.teste_base AS
                SELECT
                    TRY_CAST(t.Store AS INTEGER) AS Store,
                    TRY_CAST(t.Dept AS INTEGER) AS Dept,
                    TRY_CAST(t.Date AS DATE) AS Date,
                    TRY_CAST(t.IsHoliday AS BOOLEAN) AS IsHoliday,
                    s.Type AS Store_Type,
                    TRY_CAST(s.Size AS DOUBLE) AS Store_Size,
                    TRY_CAST(f.Temperature AS DOUBLE) AS Temperature,
                    TRY_CAST(f.Fuel_Price AS DOUBLE) AS Fuel_Price,
                    TRY_CAST(NULLIF(f.MarkDown1, 'NA') AS DOUBLE) AS MarkDown1,
                    TRY_CAST(NULLIF(f.MarkDown2, 'NA') AS DOUBLE) AS MarkDown2,
                    TRY_CAST(NULLIF(f.MarkDown3, 'NA') AS DOUBLE) AS MarkDown3,
                    TRY_CAST(NULLIF(f.MarkDown4, 'NA') AS DOUBLE) AS MarkDown4,
                    TRY_CAST(NULLIF(f.MarkDown5, 'NA') AS DOUBLE) AS MarkDown5,
                    TRY_CAST(NULLIF(f.CPI, 'NA') AS DOUBLE) AS CPI,
                    TRY_CAST(NULLIF(f.Unemployment, 'NA') AS DOUBLE)
                        AS Unemployment,
                    COALESCE(f.MarkDown1 = 'NA', FALSE) AS MarkDown1_missing,
                    COALESCE(f.MarkDown2 = 'NA', FALSE) AS MarkDown2_missing,
                    COALESCE(f.MarkDown3 = 'NA', FALSE) AS MarkDown3_missing,
                    COALESCE(f.MarkDown4 = 'NA', FALSE) AS MarkDown4_missing,
                    COALESCE(f.MarkDown5 = 'NA', FALSE) AS MarkDown5_missing,
                    COALESCE(f.CPI = 'NA', FALSE) AS CPI_missing,
                    COALESCE(f.Unemployment = 'NA', FALSE) AS Unemployment_missing
                FROM bruto.test AS t
                LEFT JOIN bruto.stores AS s ON t.Store = s.Store
                LEFT JOIN bruto.features AS f
                    ON t.Store = f.Store AND t.Date = f.Date
                """
            )

            quantidade_treino_saida = con.execute(
                "SELECT COUNT(*) FROM processado.treino_base"
            ).fetchone()[0]
            quantidade_teste_saida = con.execute(
                "SELECT COUNT(*) FROM processado.teste_base"
            ).fetchone()[0]
            if quantidade_treino_saida != quantidade_treino:
                raise ValueError(
                    "A quantidade de linhas do treino mudou após os JOINs: "
                    f"origem={quantidade_treino}, saída={quantidade_treino_saida}"
                )
            if quantidade_teste_saida != quantidade_teste:
                raise ValueError(
                    "A quantidade de linhas do teste mudou após os JOINs: "
                    f"origem={quantidade_teste}, saída={quantidade_teste_saida}"
                )

            duplicidades_treino = con.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT Store, Dept, Date
                    FROM processado.treino_base
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
                    FROM processado.teste_base
                    GROUP BY Store, Dept, Date
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]
            if duplicidades_treino or duplicidades_teste:
                raise ValueError(
                    "Chave Store + Dept + Date duplicada após transformação: "
                    f"treino={duplicidades_treino}, teste={duplicidades_teste}"
                )

            sem_loja_treino, sem_features_treino = con.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE s.Store IS NULL),
                    COUNT(*) FILTER (WHERE f.Store IS NULL)
                FROM bruto.train AS t
                LEFT JOIN bruto.stores AS s ON t.Store = s.Store
                LEFT JOIN bruto.features AS f
                    ON t.Store = f.Store AND t.Date = f.Date
                """
            ).fetchone()
            sem_loja_teste, sem_features_teste = con.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE s.Store IS NULL),
                    COUNT(*) FILTER (WHERE f.Store IS NULL)
                FROM bruto.test AS t
                LEFT JOIN bruto.stores AS s ON t.Store = s.Store
                LEFT JOIN bruto.features AS f
                    ON t.Store = f.Store AND t.Date = f.Date
                """
            ).fetchone()

            con.execute("COMMIT")
            return {
                "processado.treino_base": quantidade_treino_saida,
                "processado.teste_base": quantidade_teste_saida,
                **{
                    f"conversoes_invalidas.treino.{campo}": quantidade
                    for campo, quantidade in invalidos_treino.items()
                },
                **{
                    f"conversoes_invalidas.teste.{campo}": quantidade
                    for campo, quantidade in invalidos_teste.items()
                },
                "treino_sem_loja": sem_loja_treino,
                "treino_sem_features": sem_features_treino,
                "teste_sem_loja": sem_loja_teste,
                "teste_sem_features": sem_features_teste,
            }
        except Exception:
            con.execute("ROLLBACK")
            raise
    finally:
        con.close()


__all__ = ["transformar_bases"]
