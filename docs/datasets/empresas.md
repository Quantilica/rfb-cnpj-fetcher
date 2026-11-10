---
dataset:
  id: empresas
  fonte: rfb-cnpj
  titulo: "Empresas do CNPJ"
  resumo: "Dados cadastrais da empresa (raiz do CNPJ): razão social, natureza jurídica, capital social e porte."
  orgao: "Receita Federal do Brasil (RFB)"
  pagina_oficial: "https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj"
  licenca: "Não declarada para os dados. O rodapé do site gov.br da Receita declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR) para o conteúdo do site, sem dizer que vale para o conjunto de dados. Não foi encontrada restrição de coleta ou redistribuição nos documentos lidos (conferido em 2026-11-10)"
  periodicidade: "mensal, uma pasta por competência (`AAAA-MM`)"
  cobertura: {inicio: 2023-05, fim: em-curso}
  unidade: "uma empresa (raiz de 8 dígitos do CNPJ) numa competência"
  granularidade: {espacial: "empresa / estabelecimento (sem geografia própria)", temporal: "competência (mês)"}
  formato_bruto: "ZIPs com um arquivo de texto sem cabeçalho, latin-1, separador ponto e vírgula, todos os campos entre aspas duplas (inclusive os vazios), um registro por linha; layout dado pelo documento de metadados da Receita"
  lake: {estado: convertido, particoes: [ano, mes], chave: [ano, mes, cnpj_basico], colunas: 7}
  unidades_de_medida:
    capital_social: "não informado pela fonte (texto com vírgula decimal)"
  dados_pessoais:
    - {coluna: razao_social, categoria: "nome da pessoa física, nos empresários individuais; nesses casos o texto traz também o CPF completo, sem máscara"}
  eras: []
  revisado_em: 2026-11-10
  versao_fetcher: 0.5.3
---

# Empresas do CNPJ

## Resumo

A tabela de empresas do Cadastro Nacional da Pessoa Jurídica (CNPJ), publicada pela Receita Federal como dados abertos. Uma linha por empresa (a raiz de 8 dígitos do CNPJ), com razão social, natureza jurídica, qualificação do responsável, capital social, porte e, para órgãos públicos, o ente federativo responsável. O endereço e a situação estão em `estabelecimentos`.

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `rfb-cnpj/empresas` |
| Órgão | Receita Federal do Brasil (RFB) |
| Página oficial | https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj |
| Licença | Não declarada para os dados. O rodapé do site gov.br da Receita declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR) para o conteúdo do site, sem dizer que vale para o conjunto de dados. Não foi encontrada restrição de coleta ou redistribuição nos documentos lidos (conferido em 2026-11-10) |
| Periodicidade | mensal, uma pasta por competência (`AAAA-MM`) |
| Cobertura | 2023-05 a em-curso |
| Unidade (uma linha) | uma empresa (raiz de 8 dígitos do CNPJ) numa competência |
| Granularidade | espacial: empresa / estabelecimento (sem geografia própria); temporal: competência (mês) |
| Formato bruto | ZIPs com um arquivo de texto sem cabeçalho, latin-1, separador ponto e vírgula, todos os campos entre aspas duplas (inclusive os vazios), um registro por linha; layout dado pelo documento de metadados da Receita |
| Estado no lake | convertido |
| Partições | `ano`, `mes` |
| Chave | `ano`, `mes`, `cnpj_basico` |
| Colunas | 7 |
| Unidades de medida | `capital_social`: não informado pela fonte (texto com vírgula decimal) |
| Dados pessoais | `razao_social` (nome da pessoa física, nos empresários individuais; nesses casos o texto traz também o CPF completo, sem máscara) |
| Eras | nenhuma |
| Revisado em | 2026-11-10 |
| Versão do fetcher | 0.5.3 |

## Origem e coleta

- O fetcher lista a pasta pública da Receita (`Dados/Cadastros/CNPJ/AAAA-MM/`) e baixa `Empresas0.zip a Empresas9.zip` de cada competência, em 10 arquivos. No bruto: `AAAA-MM/empresas/Empresas0 a Empresas9@AAAAMMDD.zip`, com um `.manifest.json` ao lado. O sufixo é a data de última modificação informada pelo servidor; nas competências 2023-05 a 2025-05 todos os arquivos têm 20250520, data em que foram coletados.
- Dentro de cada ZIP há um único arquivo de texto, sem cabeçalho, cujo nome não termina em `.csv` nem `.txt` (por exemplo `K3241.K03200Y0.D60711.EMPRECSV`). O trecho `D60711` é uma data (2026-07-11).
- Versões no bruto conferidas em 2026-11-10: uma por competência, 42 competências de 2023-05 a 2026-10; a fonte lista as mesmas 42 pastas. Cada competência é um retrato completo, não um incremento.

## Conteúdo

- Uma linha por empresa por competência. `cnpj_basico` é único dentro da competência nas amostras convertidas (150.000 linhas, 150.000 valores distintos, em 2023-05, 2025-06, 2026-07 e 2026-10).
- Cobertura na fonte e no bruto: 42 competências, 2023-05 a 2026-10 (conferido em 2026-11-10). Os dados convertidos são **amostras**: as primeiras 150.000 linhas de `Empresas0` de quatro competências.
- Os 10 arquivos dividem as empresas por faixa de `cnpj_basico`. O arquivo `Empresas0` é o maior (571 MB contra 78 a 99 MB dos demais em 2026-10) e começa em `41273589` nas amostras; os demais começam em `00000000` e vão subindo. Para o cadastro completo, leia os 10.
- Nas amostras, o `porte_empresa` tem os códigos `01`, `03` e `05`; 119.646 de 150.000 linhas de 2023-05 são `natureza_juridica` `2135` (Empresário Individual).
- Em 149.943 de 150.000 linhas `ente_federativo_responsavel` é nulo, nas amostras de 2023-05, 2025-06 e 2026-07 (regra do layout: só para a natureza `1XXX`).

## Variáveis

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `cnpj_basico` | `CNPJ BÁSICO` | texto | Número base de inscrição no CNPJ (oito primeiros dígitos do CNPJ) | 8 dígitos, com zeros à esquerda | todo |
| `razao_social` | `RAZÃO SOCIAL / NOME EMPRESARIAL` | texto | Nome empresarial da pessoa jurídica. Nos empresários individuais, é o nome da pessoa e o CPF completo | — | todo |
| `natureza_juridica` | `NATUREZA JURÍDICA` | texto | Código da natureza jurídica | 4 dígitos; tabela `naturezas` | todo |
| `qualificacao_responsavel` | `QUALIFICAÇÃO DO RESPONSÁVEL` | texto | Código da qualificação da pessoa física responsável pela empresa | 2 dígitos; tabela `qualificacoes` | todo |
| `capital_social` | `CAPITAL SOCIAL DA EMPRESA` | texto | Capital social da empresa, em texto com vírgula decimal (`20000,00`) | não informado pela fonte | todo |
| `porte_empresa` | `PORTE DA EMPRESA` | texto | Código do porte da empresa | `00` não informado; `01` micro empresa; `03` empresa de pequeno porte; `05` demais | todo |
| `ente_federativo_responsavel` | `ENTE FEDERATIVO RESPONSÁVEL` | texto | Preenchido para órgãos e entidades do grupo de natureza jurídica `1XXX`; nas demais fica em branco (nulo no lake) | texto, ex.: `UNIÃO`, `BAHIA`, `SÃO PAULO - SP` | todo |
| `ano` | — (partição) | inteiro | Ano da competência (pasta `AAAA-MM`) | — | todo |
| `mes` | — (partição) | texto | Mês da competência (pasta `AAAA-MM`) | `01` a `12` | todo |

## No lake

- Dataset `rfb-cnpj/empresas`, particionado por `ano` (inteiro) e `mes` (texto de 2 dígitos, `05`); um Parquet por arquivo do bruto (`Empresas0.parquet` a `Empresas9.parquet`).
- O conversor lê o arquivo com o DuckDB em latin-1, `;` como separador, aspas duplas como delimitador e escape, sem cabeçalho (nomes do layout oficial), **tudo como texto**. Campo vazio vira nulo. Os zeros à esquerda dos códigos são mantidos.
- Datas ficam como texto `AAAAMMDD`; o valor "sem data" (`0` ou `00000000`) **não** vira nulo no lake.
- **Defeito: o conversor só lê arquivo de texto com extensão `.csv` ou `.txt` dentro do ZIP**, mas o ZIP real da Receita traz o arquivo sem essa extensão (`K3241.K03200Y0.D60711.EMPRECSV`). Convertido com a versão 0.5.3 do fetcher, o ZIP real termina em erro (`contains no data files (.csv/.txt)`). O esquema de referência e as conferências desta página vieram de amostras com o arquivo do ZIP renomeado para `.csv`.
- `capital_social` fica texto com vírgula decimal (`20000,00`): o módulo de leitura do fetcher converte para decimal, mas o conversor do lake não.

## Cuidados de uso

- **A conversão atual não aceita o ZIP como a Receita o publica.** O arquivo dentro do ZIP não termina em `.csv`/`.txt` (`K3241.K03200Y0.D60711.EMPRECSV`), e o conversor recusa o ZIP com `contains no data files`. Conferido com um ZIP real de 2026-10 em 2026-11-10. Os testes do fetcher passam porque usam um arquivo `.CSV`.
- **A razão social do empresário individual carrega o CPF completo.** Na amostra de 2023-05, 101.767 de 150.000 razões sociais terminam em 11 dígitos (83.523 em 2026-10); todas as 101.767 estão na natureza `2135` (Empresário Individual) e têm dígitos verificadores de CPF válidos, ou seja, são o CPF da pessoa, sem máscara. A máscara que a Receita aplica nos sócios não vale para este campo (conferido em 2026-11-10).
- **Texto, não número.** `capital_social` é texto com vírgula (`20000,00`); `cnpj_basico` tem zeros à esquerda. Converta com `REPLACE(capital_social, ',', '.')::DECIMAL(20,2)`. A unidade do capital não vem informada pela fonte.
- **Cada competência é um retrato completo.** A mesma empresa aparece em todas as competências em que existe; não some entre competências.
- **Os 10 arquivos não são uma amostra.** Eles dividem o cadastro por faixa de `cnpj_basico`; `Empresas0` concentra a faixa mais alta e cresce a cada mês (263 MB em 2023-05, 437 MB em 2025-06, 544 MB em 2026-07, 571 MB em 2026-10).
- **CNPJ alfanumérico.** A Receita anunciou o CNPJ alfanumérico a partir de julho de 2026. Nas amostras (primeiras e últimas 100 mil linhas de `Empresas0` de 2026-10) todos os `cnpj_basico` são numéricos de 8 dígitos; códigos com letras podem aparecer em arquivos ou competências não amostrados.
- **Código 0 em `porte_empresa`.** `00` é "não informado" e não aparece nas amostras.

## Exemplos

Empresários individuais e sociedades limitadas por porte, numa competência (sem tocar na razão social):

```python
import polars as pl

emp = pl.scan_parquet("lake/rfb-cnpj/empresas/**/*.parquet", hive_partitioning=True)
por_porte = (
    emp.filter((pl.col("ano") == 2026) & (pl.col("mes") == "10"))
    .group_by("natureza_juridica", "porte_empresa")
    .len()
    .sort("len", descending=True)
    .head(10)
    .collect()
)
```

## Referências

- Página de referência dos dados abertos do CNPJ (Receita Federal; não pôde ser lida por leitor automático na conferência de 2026-11-10): https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj
- Metadados do layout dos dados abertos do CNPJ (Receita Federal): https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf
