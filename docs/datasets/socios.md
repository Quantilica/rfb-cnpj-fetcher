---
dataset:
  id: socios
  fonte: rfb-cnpj
  titulo: "Sócios e administradores do CNPJ"
  resumo: "Quadro societário: sócios pessoas físicas e jurídicas e seus representantes legais, por empresa."
  orgao: "Receita Federal do Brasil (RFB)"
  pagina_oficial: "https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj"
  licenca: "Não declarada para os dados. O rodapé do site gov.br da Receita declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR) para o conteúdo do site, sem dizer que vale para o conjunto de dados. Não foi encontrada restrição de coleta ou redistribuição nos documentos lidos (conferido em 2026-11-10)"
  periodicidade: "mensal, uma pasta por competência (`AAAA-MM`)"
  cobertura: {inicio: 2023-05, fim: em-curso}
  unidade: "um vínculo de sócio (ou administrador) com uma empresa numa competência"
  granularidade: {espacial: "empresa / estabelecimento (sem geografia própria)", temporal: "competência (mês)"}
  formato_bruto: "ZIPs com um arquivo de texto sem cabeçalho, latin-1, separador ponto e vírgula, todos os campos entre aspas duplas (inclusive os vazios), um registro por linha; layout dado pelo documento de metadados da Receita"
  lake: {estado: convertido, particoes: [ano, mes], chave: [ano, mes, cnpj_basico, identificador_socio, cnpj_cpf_socio, nome_socio], colunas: 11}
  unidades_de_medida: null
  dados_pessoais:
    - {coluna: nome_socio, categoria: "nome (sócio pessoa física)"}
    - {coluna: cnpj_cpf_socio, categoria: "CPF parcialmente mascarado pela fonte (`***999999**`), para pessoa física"}
    - {coluna: representante_legal, categoria: "CPF do representante legal, mascarado pela fonte"}
    - {coluna: nome_representante_legal, categoria: "nome"}
    - {coluna: faixa_etaria, categoria: "faixa etária, derivada da data de nascimento"}
  eras:
    - {desde: 2026-08, mudanca: "o documento do sócio pessoa jurídica (`cnpj_cpf_socio`) passa de 14 para 8 dígitos"}
  revisado_em: 2026-11-10
  versao_fetcher: 0.5.3
---

# Sócios e administradores do CNPJ

## Resumo

O quadro de sócios e administradores (QSA) do CNPJ: para cada empresa, as pessoas físicas, jurídicas e estrangeiras que são sócias, com a data de entrada, a qualificação e o representante legal. A Receita mascara o CPF (oculta os três primeiros dígitos e os dois verificadores) e substitui a data de nascimento por uma faixa etária.

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `rfb-cnpj/socios` |
| Órgão | Receita Federal do Brasil (RFB) |
| Página oficial | https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj |
| Licença | Não declarada para os dados. O rodapé do site gov.br da Receita declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR) para o conteúdo do site, sem dizer que vale para o conjunto de dados. Não foi encontrada restrição de coleta ou redistribuição nos documentos lidos (conferido em 2026-11-10) |
| Periodicidade | mensal, uma pasta por competência (`AAAA-MM`) |
| Cobertura | 2023-05 a em-curso |
| Unidade (uma linha) | um vínculo de sócio (ou administrador) com uma empresa numa competência |
| Granularidade | espacial: empresa / estabelecimento (sem geografia própria); temporal: competência (mês) |
| Formato bruto | ZIPs com um arquivo de texto sem cabeçalho, latin-1, separador ponto e vírgula, todos os campos entre aspas duplas (inclusive os vazios), um registro por linha; layout dado pelo documento de metadados da Receita |
| Estado no lake | convertido |
| Partições | `ano`, `mes` |
| Chave | `ano`, `mes`, `cnpj_basico`, `identificador_socio`, `cnpj_cpf_socio`, `nome_socio` |
| Colunas | 11 |
| Unidades de medida | — |
| Dados pessoais | `nome_socio` (nome (sócio pessoa física)); `cnpj_cpf_socio` (CPF parcialmente mascarado pela fonte (`***999999**`), para pessoa física); `representante_legal` (CPF do representante legal, mascarado pela fonte); `nome_representante_legal` (nome); `faixa_etaria` (faixa etária, derivada da data de nascimento) |
| Eras | 2026-08: o documento do sócio pessoa jurídica (`cnpj_cpf_socio`) passa de 14 para 8 dígitos |
| Revisado em | 2026-11-10 |
| Versão do fetcher | 0.5.3 |

## Origem e coleta

- O fetcher lista a pasta pública da Receita (`Dados/Cadastros/CNPJ/AAAA-MM/`) e baixa `Socios0.zip a Socios9.zip` de cada competência, em 10 arquivos. No bruto: `AAAA-MM/socios/Socios0 a Socios9@AAAAMMDD.zip`, com um `.manifest.json` ao lado. O sufixo é a data de última modificação informada pelo servidor; nas competências 2023-05 a 2025-05 todos os arquivos têm 20250520, data em que foram coletados.
- Dentro de cada ZIP há um único arquivo de texto, sem cabeçalho, cujo nome não termina em `.csv` nem `.txt` (por exemplo `K3241.K03200Y0.D60711.EMPRECSV`). O trecho `D60711` é uma data (2026-07-11).
- Versões no bruto conferidas em 2026-11-10: uma por competência, 42 competências de 2023-05 a 2026-10; a fonte lista as mesmas 42 pastas. Cada competência é um retrato completo, não um incremento.

## Conteúdo

- Uma linha por vínculo sócio-empresa por competência. Não há chave única declarada: a combinação `cnpj_basico`, `identificador_socio`, `cnpj_cpf_socio` e `nome_socio` repete em 3 de 150.000 linhas de uma amostra (2023-05) e em nenhuma das demais (conferido em 2026-11-10).
- Cobertura na fonte e no bruto: 42 competências, 2023-05 a 2026-10. Os dados convertidos são **amostras**: as primeiras 150.000 linhas de `Socios0` de quatro competências.
- `identificador_socio` nas amostras de 2026-10: `2` pessoa física (146.437), `1` pessoa jurídica (3.529) e `3` estrangeiro (34).
- Para pessoa física, `cnpj_cpf_socio` tem 11 caracteres no padrão `***999999**` em todas as linhas amostradas; para estrangeiro, é nulo. `representante_legal` é `***000000**` em cerca de 97% das linhas (sem representante).
- **Era de 2026-08:** `cnpj_cpf_socio` do sócio pessoa jurídica tem 14 dígitos até 2026-07 (conferido em `Socios0` de 2023-05, 2025-09, 2025-12, 2026-03, 2026-06 e 2026-07) e 8 dígitos a partir de 2026-08 (conferido em `Socios0` e `Socios5` de 2026-08, 2026-09 e 2026-10).
- `faixa_etaria` vai de `0` (não se aplica) a `9`, conforme o layout; em 2026-10, 3.563 de 150.000 linhas (amostra) são `0`.

## Variáveis

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `cnpj_basico` | `CNPJ BÁSICO` | texto | Número base de inscrição no CNPJ da empresa | 8 dígitos | todo |
| `identificador_socio` | `IDENTIFICADOR DE SÓCIO` | texto | Código do identificador de sócio | `1` pessoa jurídica; `2` pessoa física; `3` estrangeiro | todo |
| `nome_socio` | `NOME DO SÓCIO (NO CASO PF) OU RAZÃO SOCIAL (NO CASO PJ)` | texto | Nome do sócio pessoa física ou razão social e/ou nome empresarial da pessoa jurídica ou do sócio estrangeiro | — | todo |
| `cnpj_cpf_socio` | `CNPJ/CPF DO SÓCIO` | texto | CPF ou CNPJ do sócio; o sócio estrangeiro não tem. O CPF vem descaracterizado (oculta os três primeiros e os dois últimos dígitos) | PF: `***999999**`; PJ: 14 dígitos até 2026-07 e 8 dígitos desde 2026-08 | todo |
| `qualificacao_socio` | `QUALIFICAÇÃO DO SÓCIO` | texto | Código da qualificação do sócio | 2 dígitos; tabela `qualificacoes` | todo |
| `data_entrada_sociedade` | `DATA DE ENTRADA SOCIEDADE` | texto | Data de entrada na sociedade | texto `AAAAMMDD` | todo |
| `pais` | `PAIS` | texto | Código do país do sócio estrangeiro | 3 dígitos; tabela `paises` | todo |
| `representante_legal` | `REPRESENTANTE LEGAL` | texto | Número do CPF do representante legal, descaracterizado como o do sócio | `***999999**`; `***000000**` = sem representante | todo |
| `nome_representante_legal` | `NOME DO REPRESENTANTE` | texto | Nome do representante legal | — | todo |
| `qualificacao_representante_legal` | `QUALIFICAÇÃO DO REPRESENTANTE LEGAL` | texto | Código da qualificação do representante legal | 2 dígitos; tabela `qualificacoes`; `00` = sem representante | todo |
| `faixa_etaria` | `FAIXA ETÁRIA` | texto | Código da faixa etária do sócio, a partir da data de nascimento do CPF | `1` 0-12 anos; `2` 13-20; `3` 21-30; `4` 31-40; `5` 41-50; `6` 51-60; `7` 61-70; `8` 71-80; `9` mais de 80; `0` não se aplica | todo |
| `ano` | — (partição) | inteiro | Ano da competência (pasta `AAAA-MM`) | — | todo |
| `mes` | — (partição) | texto | Mês da competência (pasta `AAAA-MM`) | `01` a `12` | todo |

## No lake

- Dataset `rfb-cnpj/socios`, particionado por `ano` (inteiro) e `mes` (texto de 2 dígitos, `05`); um Parquet por arquivo do bruto (`Socios0.parquet` a `Socios9.parquet`).
- O conversor lê o arquivo com o DuckDB em latin-1, `;` como separador, aspas duplas como delimitador e escape, sem cabeçalho (nomes do layout oficial), **tudo como texto**. Campo vazio vira nulo. Os zeros à esquerda dos códigos são mantidos.
- Datas ficam como texto `AAAAMMDD`; o valor "sem data" (`0` ou `00000000`) **não** vira nulo no lake.
- O conversor lê o arquivo de texto do ZIP qualquer que seja o nome dele: o ZIP real da Receita traz o arquivo sem extensão `.csv`/`.txt` (`K3241.K03200Y9.D61010.SOCIOCSV`).

## Cuidados de uso

- **Conversão do ZIP real conferida.** O arquivo `Socios9` de 2026-10, como a Receita o publica, foi convertido sem erro: 2.019.150 registros no bruto e 2.019.150 linhas no Parquet. Os testes do fetcher cobrem o nome de arquivo sem extensão.
- **Dados pessoais.** A tabela traz nome de pessoas físicas, CPF parcialmente mascarado, nome e CPF mascarado do representante legal e faixa etária. O cabeçalho lista as colunas como inventário; os exemplos desta página não reproduzem valores.
- **O CPF mascarado não identifica a pessoa.** Os seis dígitos do meio repetem entre pessoas diferentes; não use `cnpj_cpf_socio` como identificador de pessoa.
- **O documento do sócio PJ mudou em 2026-08.** Até 2026-07, 14 dígitos (CNPJ completo); a partir de 2026-08, 8 dígitos. Séries históricas de "sócios PJ" que cruzem pelo CNPJ completo precisam tratar as duas formas.
- **Sem chave única garantida.** Repetições raras existem (3 em 150.000 linhas de uma amostra); deduplique antes de contar vínculos.
- **Sentinelas de representante.** `representante_legal` `***000000**` e `qualificacao_representante_legal` `00` indicam ausência de representante, não uma pessoa.
- **Cada competência é um retrato completo.** Não some sócios entre competências.

## Exemplos

Quantidade de vínculos por qualificação numa competência (sem identificar pessoas):

```python
import polars as pl

soc = pl.scan_parquet("lake/rfb-cnpj/socios/**/*.parquet", hive_partitioning=True)
qual = pl.read_parquet("lake/rfb-cnpj/qualificacoes/ano=2026/mes=10/*.parquet")
top = (
    soc.filter((pl.col("ano") == 2026) & (pl.col("mes") == "10"))
    .group_by("qualificacao_socio")
    .len()
    .collect()
    .join(qual, left_on="qualificacao_socio", right_on="codigo", how="left")
    .sort("len", descending=True)
    .head(5)
)
```

## Referências

- Página de referência dos dados abertos do CNPJ (Receita Federal; não pôde ser lida por leitor automático na conferência de 2026-11-10): https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj
- Metadados do layout dos dados abertos do CNPJ (Receita Federal): https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf
