# Especificação --- Transformação e preparação dos dados

## Projeto: Walmart Store Sales Forecasting

**Versão:** 1.3\
**Status:** Revisada --- regras temporais detalhadas\
**Objetivo:** construir bases tipadas, integradas e preparadas para
treinamento e previsão das vendas semanais por loja e departamento.

------------------------------------------------------------------------

## 1. Objetivo do projeto

Desenvolver um pipeline reproduzível de transformação de dados para o
desafio Walmart Store Sales Forecasting. O problema consiste em prever
`Weekly_Sales` para cada combinação de loja (`Store`), departamento
(`Dept`) e semana (`Date`).

A granularidade principal será `Store + Dept + Date`, com uma observação
por departamento de uma loja em uma semana. O pipeline utilizará Python
e DuckDB, preservará os dados originais e manterá separadas a ingestão,
a transformação e a preparação dos atributos para modelagem.

## 2. Fontes de dados

As tabelas originais estão no schema `bruto` do banco DuckDB.

  ------------------------------------------------------------------------------
  Tabela                               Registros esperados Descrição
  --------------------------- ---------------------------- ---------------------
  `bruto.train`                                    421.570 Histórico de vendas
                                                           para treinamento e
                                                           validação

  `bruto.test`                                     115.064 Registros destinados
                                                           à geração de
                                                           previsões

  `bruto.stores`                                        45 Características das
                                                           lojas

  `bruto.features`                                   8.190 Indicadores
                                                           econômicos,
                                                           temperatura,
                                                           combustível, feriados
                                                           e MarkDowns

  `bruto.sample_submission`                        115.064 Referência para o
                                                           formato de submissão
  ------------------------------------------------------------------------------

Todas as colunas da camada bruta são `VARCHAR`.

### 2.1 Períodos disponíveis

-   Treinamento: 05/02/2010 a 26/10/2012.
-   Teste: 02/11/2012 a 26/07/2013.
-   O conjunto de teste contém 39 semanas, identificadas por
    sextas-feiras.
-   O conjunto `features` cobre períodos de treinamento e teste.

## 3. Princípios obrigatórios

1.  Preservar integralmente as tabelas do schema `bruto`.
2.  Não excluir registros sem justificativa documentada.
3.  Não substituir valores ausentes automaticamente por zero.
4.  Preservar vendas negativas e iguais a zero.
5.  Não remover outliers somente por critérios estatísticos.
6.  Não criar combinações artificiais de loja e departamento.
7.  Preservar a separação temporal entre treinamento, validação e teste.
8.  Evitar vazamento de informação futura em atributos, treinamento e
    validação.
9.  Tornar as transformações reproduzíveis.
10. Implementar testes automatizados para validar os resultados.
11. Não duplicar os dados brutos nem exportar as bases processadas para
    novos arquivos CSV. As saídas persistidas desta etapa ficam no
    DuckDB.
12. Utilizar `CREATE OR REPLACE TABLE` nas tabelas de transformação para
    permitir reexecução reproduzível.

## 4. Camadas de dados

O banco DuckDB terá as seguintes camadas lógicas:

  -----------------------------------------------------------------------
  Schema                              Responsabilidade
  ----------------------------------- -----------------------------------
  `bruto`                             Dados originais carregados sem
                                      alterações

  `processado`                        Dados tipados, integrados e
                                      validados

  `features`                          Bases de treinamento e teste com
                                      atributos preparados para modelagem
  -----------------------------------------------------------------------

Os arquivos originais permanecem em `dados/brutos/`. As transformações
não os sobrescrevem. As tabelas processadas e de atributos permanecem no
DuckDB, no banco definido pela configuração central do projeto.

## 5. Transformações da base de treinamento

Criar ou substituir a tabela `processado.treino_base`.

### 5.1 Conversão dos tipos

  -------------------------------------------------------------------------------
  Coluna de saída         Tipo esperado           Origem/regra
  ----------------------- ----------------------- -------------------------------
  `Store`                 INTEGER                 `bruto.train.Store`

  `Dept`                  INTEGER                 `bruto.train.Dept`

  `Date`                  DATE                    `bruto.train.Date`

  `Weekly_Sales`          DOUBLE                  `bruto.train.Weekly_Sales`

  `IsHoliday`             BOOLEAN                 Indicador de feriado, conferido
                                                  entre vendas e features

  `Store_Type`            VARCHAR                 `bruto.stores.Type`

  `Store_Size`            DOUBLE                  `bruto.stores.Size`

  `Temperature`           DOUBLE                  `bruto.features.Temperature`

  `Fuel_Price`            DOUBLE                  `bruto.features.Fuel_Price`

  `MarkDown1` a           DOUBLE                  `bruto.features`
  `MarkDown5`                                     

  `CPI`                   DOUBLE                  `bruto.features.CPI`

  `Unemployment`          DOUBLE                  `bruto.features.Unemployment`
  -------------------------------------------------------------------------------

Usar conversões seguras, como `TRY_CAST`, quando apropriado. Valores não
convertíveis devem ser identificados e contabilizados nos testes de
qualidade. A transformação não deve alterar os valores da camada bruta.

### 5.2 Integração das tabelas

Integrar `bruto.train`, `bruto.stores` e `bruto.features` pelas chaves:

-   Treino com lojas: `train.Store = stores.Store`.
-   Treino com features:
    `train.Store = features.Store AND train.Date = features.Date`.

Utilizar `LEFT JOIN` para preservar cada registro de venda. Não agregar
lojas nem departamentos. Não multiplicar linhas em razão dos
relacionamentos; validar a unicidade das chaves correspondentes antes ou
durante a criação da saída.

### 5.3 Vendas negativas e iguais a zero

Foram identificados no treino 1.285 registros com vendas negativas e 73
com vendas iguais a zero. Os valores negativos aparecem nas 45 lojas,
com concentração observada no departamento 47.

Regras:

-   Preservar vendas negativas e iguais a zero.
-   Não converter valores negativos em absolutos nem substituí-los por
    zero.
-   Não excluir observações por serem negativas, zero ou extremas.
-   Manter esses valores disponíveis para avaliação durante a modelagem.

### 5.4 Valores ausentes

#### MarkDown1 a MarkDown5

Os campos promocionais possuem ausências, incluindo ausência conjunta
antes de 11/11/2011 e disponibilidade parcial em períodos posteriores.
Também foram observados padrões distintos por loja e tipo de loja.

Regras:

1.  Converter o marcador textual `NA` para `NULL` na camada processada.
2.  Não substituir automaticamente `NULL` por zero.
3.  Preservar valores numéricos disponíveis.
4.  Criar os indicadores booleanos ou binários `MarkDown1_missing`,
    `MarkDown2_missing`, `MarkDown3_missing`, `MarkDown4_missing` e
    `MarkDown5_missing`.

#### CPI e Unemployment

Foram identificados 585 registros ausentes em cada variável, simultâneos
para as lojas nas últimas 13 semanas disponíveis em `features`, de
03/05/2013 a 26/07/2013.

Regras:

1.  Converter o marcador textual `NA` para `NULL` na camada processada.
2.  Não substituir automaticamente os valores ausentes por zero.
3.  Preservar os valores disponíveis.
4.  Criar os indicadores `CPI_missing` e `Unemployment_missing` como
    booleanos ou inteiros binários.
5.  Tratar qualquer imputação posteriormente, exclusivamente na
    preparação do modelo, usando informações disponíveis até a data
    prevista. Não usar preenchimento retroativo com informação futura.

## 6. Transformações da base de teste

Criar ou substituir `processado.teste_base`, integrando `bruto.test`,
`bruto.stores` e `bruto.features` com as mesmas regras de tipagem e de
junção da base de treino.

Regras:

1.  Preservar os 115.064 registros e manter `Store`, `Dept` e `Date`.
2.  Integrar características de lojas e variáveis externas.
3.  Não criar `Weekly_Sales` com valores inventados.
4.  Não utilizar vendas reais do período de teste em nenhuma
    transformação.
5.  Manter estrutura compatível com a base de treino, exceto pela
    ausência da variável-alvo.

## 7. Engenharia de atributos

Criar ou substituir no DuckDB:

-   `features.treino_modelagem`.
-   `features.teste_modelagem`.

Os atributos só podem usar informações disponíveis na data de previsão.

### 7.1 Atributos de calendário

Derivar de `Date` e preservar a coluna original:

  Atributo      Descrição
  ------------- -------------------------
  `Year`        Ano
  `Month`       Mês
  `Week`        Número da semana no ano
  `Quarter`     Trimestre
  `DayOfYear`   Dia do ano

Os indicadores `IsMonthStart` e `IsMonthEnd` ficam fora da implementação
inicial. `IsHoliday` permanece booleano.

### 7.2 Atributos das lojas

Preservar `Store`, `Dept`, `Store_Type` e `Store_Size`. Tratar
`Store_Type` como categórica na preparação do modelo. `Store` e `Dept`
são identificadores categóricos ou codificados de acordo com o
algoritmo; seus números não devem ser presumidos como escalas
quantitativas.

### 7.3 Variáveis econômicas e ambientais

Preservar `Temperature`, `Fuel_Price`, `CPI` e `Unemployment`. Não
normalizar nem padronizar nesta camada. Se o algoritmo exigir
escalonamento, ajustar essa transformação somente nos dados de treino de
cada divisão temporal.

### 7.4 Variáveis promocionais

Preservar `MarkDown1` a `MarkDown5` e os respectivos indicadores de
ausência. Não atribuir significado específico a cada campo MarkDown,
pois as categorias não estão identificadas no dataset.

### 7.5 Atributos históricos de vendas

Considerar inicialmente, por combinação de `Store` e `Dept`:

-   `lag_1`: venda da mesma combinação exatamente uma semana de
    calendário antes.
-   `lag_2`: venda exatamente duas semanas de calendário antes.
-   `lag_4`: venda exatamente quatro semanas de calendário antes.
-   `lag_52`: venda exatamente 52 semanas de calendário antes.
-   `rolling_mean_4`: média das vendas observadas nas quatro semanas de
    calendário anteriores.
-   `rolling_mean_8`: média das vendas observadas nas oito semanas de
    calendário anteriores.
-   `rolling_std_4`: desvio-padrão amostral das vendas observadas nas
    quatro semanas de calendário anteriores.

#### Regras para os lags

1.  Agrupar por `Store` e `Dept` e ordenar cronologicamente.
2.  Definir os lags pela diferença entre datas de calendário, e não pela
    posição da linha anterior disponível.
3.  Usar exclusivamente observações com data anterior à data prevista.
4.  Não incluir a venda da própria semana no cálculo de nenhum atributo
    histórico.
5.  Se não existir observação exatamente na semana correspondente ao
    lag, retornar `NULL`; não utilizar a observação anterior mais
    próxima como substituta.
6.  Não criar observações para semanas sem registro e não interpretá-las
    como venda zero.
7.  Não utilizar vendas reais do conjunto de teste.
8.  Criar indicadores de disponibilidade dos lags, ou documentar
    claramente como a ausência será tratada pelo estimador.
9.  Validar a disponibilidade dos atributos por combinação de loja e
    departamento.

#### Regras para médias e desvio-padrão móveis

1.  Considerar as quatro ou oito semanas de calendário imediatamente
    anteriores à data prevista, excluindo a semana prevista.
2.  Calcular as estatísticas somente sobre vendas efetivamente
    observadas nessas semanas.
3.  Não preencher semanas ausentes com zero.
4.  Criar colunas auxiliares `rolling_count_4` e `rolling_count_8`,
    indicando quantas observações válidas entraram em cada janela.
5.  Se não houver observações válidas na janela, retornar `NULL`. Se
    houver menos observações do que o tamanho nominal da janela,
    calcular a estatística com as observações disponíveis e manter a
    contagem para explicitar a cobertura.
6.  Para `rolling_std_4`, utilizar o desvio-padrão amostral; se houver
    menos de duas observações válidas, retornar `NULL`.

#### Cálculo no treino e geração no teste

Para cada linha de treino, calcular os atributos históricos usando
somente registros anteriores à data daquela linha. A implementação
deverá garantir isso por construção e incluir testes que detectem
qualquer uso da venda da própria semana ou de semanas futuras.

Para o conjunto de teste, separar os atributos conhecidos
antecipadamente (calendário, loja, departamento e variáveis externas
disponíveis) dos atributos históricos dinâmicos.

A tabela `features.teste_modelagem` poderá armazenar os atributos
conhecidos antecipadamente. Os lags e as estatísticas móveis do teste
deverão ser atualizados durante a execução da previsão recursiva, em
ordem cronológica, e não calculados antecipadamente usando vendas reais
do período de teste.

Na primeira semana do teste, utilizar o histórico observado disponível
no treino. Nas semanas seguintes, utilizar as previsões produzidas
anteriormente para alimentar os atributos históricos posteriores. Nunca
consultar `Weekly_Sales` real do teste.

Aplicar a estratégia recursiva às 39 semanas do conjunto de teste.

## 8. Prevenção de vazamento temporal

Não utilizar:

-   Vendas futuras para construir atributos históricos.
-   Estatísticas calculadas com dados posteriores à data prevista.
-   Médias móveis que incluam a própria semana prevista.
-   `Weekly_Sales` real do conjunto de teste.
-   Estatísticas da validação para ajustar o pré-processamento.
-   Previsões ou informações calculadas com dados posteriores ao
    instante que está sendo simulado.

Imputação, escalonamento e codificação que aprendam parâmetros devem ser
ajustados somente nos dados de treino de cada divisão cronológica.

### 8.1 Simulação de validação

A validação temporal deverá simular o mesmo cenário operacional da
previsão do teste. Para cada janela de validação:

1.  Definir uma data de corte: somente observações anteriores ou iguais
    ao período de treinamento da janela podem ser usadas como vendas
    observadas.
2.  Prever as semanas seguintes em ordem cronológica.
3.  Após a primeira semana prevista, alimentar os atributos históricos
    das semanas seguintes com as previsões produzidas anteriormente,
    nunca com as vendas reais das semanas já previstas.
4.  Manter as vendas reais do período de validação isoladas para cálculo
    das métricas, sem disponibilizá-las ao processo de previsão.
5.  Repetir a avaliação em pelo menos uma janela temporal posterior, se
    a quantidade de dados permitir.

Os critérios de divisão, horizonte e métricas deverão ser documentados
antes da comparação dos modelos. A validação não poderá utilizar
informação futura para ajustar atributos ou parâmetros do
pré-processamento.

## 9. Tratamento de outliers

A exploração identificou assimetria positiva nas vendas e diferenças
entre lojas e departamentos. Critérios IQR global, por loja e por
departamento podem produzir resultados diferentes.

Regras:

1.  Não excluir outliers nesta etapa.
2.  Não aplicar winsorização automaticamente.
3.  Não limitar vendas máximas.
4.  Preservar valores extremos.
5.  Avaliar o impacto na modelagem antes de decidir qualquer tratamento.

## 10. Cobertura de lojas e departamentos

Existem departamentos com cobertura desigual entre tipos de loja e
combinações com poucas observações ou lacunas temporais.

Regras:

1.  Não criar combinações ausentes artificialmente.
2.  Não interpretar ausência de registro como venda zero.
3.  Preservar as combinações que existem em treino e teste.
4.  Validar a unicidade da chave `Store + Dept + Date`.
5.  Investigar duplicidades antes de qualquer remoção.

## 11. Saídas esperadas

  -----------------------------------------------------------------------
  Tabela                              Conteúdo
  ----------------------------------- -----------------------------------
  `processado.treino_base`            Treino tipado e integrado

  `processado.teste_base`             Teste tipado e integrado, sem
                                      variável-alvo

  `features.treino_modelagem`         Treino com atributos derivados sem
                                      vazamento temporal

  `features.teste_modelagem`          Teste com atributos e previsão
                                      recursiva
  -----------------------------------------------------------------------

As quatro tabelas permanecem no DuckDB e mantêm a granularidade
original. `Weekly_Sales` existe somente nas bases de treino e validação;
não deve ser criada na base de teste.

## 12. Testes e critérios de aceitação

### 12.1 Integridade dos registros

-   `processado.treino_base`: 421.570 registros.
-   `processado.teste_base`: 115.064 registros.
-   Nenhuma perda de linhas por causa dos `LEFT JOIN`.
-   Nenhuma duplicidade inesperada em `Store + Dept + Date`.
-   As saídas de características preservam a granularidade de suas
    respectivas entradas.

### 12.2 Integridade das chaves e tipos

-   `Store` e `Dept` devem ser conversíveis para valores válidos.
-   `Date` deve ser válida e pertencer ao período esperado.
-   `IsHoliday` deve ser booleano.
-   Contabilizar valores que não puderem ser convertidos.
-   Preservar a granularidade definida.

### 12.3 Integridade das vendas

-   Preservar os 1.285 registros negativos identificados no treino.
-   Preservar os 73 registros iguais a zero.
-   Não excluir valores extremos.
-   A soma das vendas antes e depois da integração deve ser igual.

### 12.4 Integridade dos relacionamentos

-   Verificar correspondência entre lojas.
-   Verificar correspondência de loja e data com `features`.
-   Confirmar que os `JOINs` não multiplicaram registros.
-   Identificar campos complementares sem correspondência.

### 12.5 Integridade temporal

-   O treino permanece até 26/10/2012.
-   O teste começa em 02/11/2012 e termina em 26/07/2013.
-   A previsão recursiva percorre cronologicamente as 39 semanas de
    teste.
-   A validação simula o horizonte de previsão sem utilizar vendas
    futuras observadas.
-   Nenhum atributo histórico usa informação posterior à data prevista.

### 12.6 Reprodutibilidade

-   A reexecução com as mesmas entradas produz resultados consistentes.
-   As tabelas de transformação podem ser recriadas com
    `CREATE OR REPLACE TABLE`.
-   Os dados brutos e arquivos originais não são alterados.
-   Os testes usam dados sintéticos e banco temporário, sem acesso de
    escrita ao banco oficial.

## 13. Organização do projeto

Reutilizar a estrutura existente do projeto, preservando as
nomenclaturas em português. A especificação oficial desta etapa fica em
`documentacao/spec/transformacao_dados.md`; a `SPEC.md` existente
permanece preservada.

``` text
previsao-vendas/
├── dados/
│   ├── brutos/
│   ├── intermediarios/
│   └── processados/
├── documentacao/
│   └── spec/
│       └── transformacao_dados.md
├── notebooks/
├── sql/
├── src/
│   └── previsao_vendas/
│       ├── banco_dados/
│       ├── configuracao/
│       ├── ingestao/
│       ├── processamento/
│       ├── caracteristicas/
│       ├── modelos/
│       ├── avaliacao/
│       └── monitoramento/
├── testes/
├── pyproject.toml
├── uv.lock
├── .gitignore
├── README.md
└── SPEC.md
```

As tabelas processadas são persistidas no DuckDB, sem gerar cópias CSV.
Não criar o diretório `tests/`; utilizar `testes/`. Não mover nem
excluir arquivos existentes sem autorização.

## 14. Etapas de implementação

Implementar e validar em etapas, sem desenvolver todo o pipeline de uma
só vez:

1.  Transformar e validar `processado.treino_base` e
    `processado.teste_base`.
2.  Gerar e validar atributos de calendário e históricos em
    `features.treino_modelagem` e `features.teste_modelagem`.
3.  Validar a previsão recursiva e a simulação de validação temporal nos
    mesmos termos do horizonte de teste.

Antes de cada etapa, comparar o contrato com os módulos existentes,
validar a saída e documentar incompatibilidades encontradas. Não alterar
a camada `bruto` nem os arquivos originais.
