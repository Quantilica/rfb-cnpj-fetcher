---
dataset:
  id: estabelecimentos
  fonte: rfb-cnpj
  titulo: "Estabelecimentos do CNPJ"
  resumo: "Estabelecimentos (matriz e filiais) com CNPJ completo, situação cadastral, atividade econômica, endereço e contatos."
  orgao: "Receita Federal do Brasil (RFB)"
  pagina_oficial: "https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj"
  licenca: "Não declarada para os dados. O rodapé do site gov.br da Receita declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR) para o conteúdo do site, sem dizer que vale para o conjunto de dados. Não foi encontrada restrição de coleta ou redistribuição nos documentos lidos (conferido em 2026-11-10)"
  periodicidade: "mensal, uma pasta por competência (`AAAA-MM`)"
  cobertura: {inicio: 2023-05, fim: em-curso}
  unidade: "um estabelecimento (CNPJ de 14 dígitos) numa competência"
  granularidade: {espacial: "município (código da Receita), UF e CEP", temporal: "competência (mês)"}
  formato_bruto: "ZIPs com um arquivo de texto sem cabeçalho, latin-1, separador ponto e vírgula, todos os campos entre aspas duplas (inclusive os vazios), um registro por linha; layout dado pelo documento de metadados da Receita"
  lake: {estado: convertido, particoes: [ano, mes], chave: [ano, mes, cnpj_basico, cnpj_ordem, cnpj_dv], colunas: 30}
  unidades_de_medida: null
  dados_pessoais:
    - {coluna: nome_fantasia, categoria: "nome (pode ser o nome da pessoa física, nos empresários individuais)"}
    - {coluna: tipo_logradouro, categoria: "endereço"}
    - {coluna: logradouro, categoria: "endereço"}
    - {coluna: numero, categoria: "endereço"}
    - {coluna: complemento, categoria: "endereço"}
    - {coluna: bairro, categoria: "endereço"}
    - {coluna: cep, categoria: "endereço"}
    - {coluna: ddd1, categoria: "telefone"}
    - {coluna: telefone1, categoria: "telefone"}
    - {coluna: ddd2, categoria: "telefone"}
    - {coluna: telefone2, categoria: "telefone"}
    - {coluna: ddd_fax, categoria: "telefone"}
    - {coluna: fax, categoria: "telefone"}
    - {coluna: correio_eletronico, categoria: "e-mail"}
  eras:
    - {desde: 2026-05, mudanca: "`pais` passa a vir preenchido com `105` (Brasil) em parte dos estabelecimentos com endereço no país; antes só aparecia em endereços no exterior"}
  revisado_em: 2026-11-10
  versao_fetcher: 0.5.3
---

# Estabelecimentos do CNPJ

## Resumo

Os estabelecimentos do CNPJ: a matriz e cada filial de uma empresa, com o CNPJ completo (`cnpj_basico` + `cnpj_ordem` + `cnpj_dv`), a situação cadastral e o motivo, as atividades econômicas (CNAE), o endereço e os contatos. É a tabela mais pesada do cadastro: o arquivo `Estabelecimentos0` tem 2,2 GB compactado em 2026-10.

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `rfb-cnpj/estabelecimentos` |
| Órgão | Receita Federal do Brasil (RFB) |
| Página oficial | https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj |
| Licença | Não declarada para os dados. O rodapé do site gov.br da Receita declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR) para o conteúdo do site, sem dizer que vale para o conjunto de dados. Não foi encontrada restrição de coleta ou redistribuição nos documentos lidos (conferido em 2026-11-10) |
| Periodicidade | mensal, uma pasta por competência (`AAAA-MM`) |
| Cobertura | 2023-05 a em-curso |
| Unidade (uma linha) | um estabelecimento (CNPJ de 14 dígitos) numa competência |
| Granularidade | espacial: município (código da Receita), UF e CEP; temporal: competência (mês) |
| Formato bruto | ZIPs com um arquivo de texto sem cabeçalho, latin-1, separador ponto e vírgula, todos os campos entre aspas duplas (inclusive os vazios), um registro por linha; layout dado pelo documento de metadados da Receita |
| Estado no lake | convertido |
| Partições | `ano`, `mes` |
| Chave | `ano`, `mes`, `cnpj_basico`, `cnpj_ordem`, `cnpj_dv` |
| Colunas | 30 |
| Unidades de medida | — |
| Dados pessoais | `nome_fantasia` (nome (pode ser o nome da pessoa física, nos empresários individuais)); `tipo_logradouro` (endereço); `logradouro` (endereço); `numero` (endereço); `complemento` (endereço); `bairro` (endereço); `cep` (endereço); `ddd1` (telefone); `telefone1` (telefone); `ddd2` (telefone); `telefone2` (telefone); `ddd_fax` (telefone); `fax` (telefone); `correio_eletronico` (e-mail) |
| Eras | 2026-05: `pais` passa a vir preenchido com `105` (Brasil) em parte dos estabelecimentos com endereço no país; antes só aparecia em endereços no exterior |
| Revisado em | 2026-11-10 |
| Versão do fetcher | 0.5.3 |

## Origem e coleta

- O fetcher lista a pasta pública da Receita (`Dados/Cadastros/CNPJ/AAAA-MM/`) e baixa `Estabelecimentos0.zip a Estabelecimentos9.zip` de cada competência, em 10 arquivos. No bruto: `AAAA-MM/estabelecimentos/Estabelecimentos0 a Estabelecimentos9@AAAAMMDD.zip`, com um `.manifest.json` ao lado. O sufixo é a data de última modificação informada pelo servidor; nas competências 2023-05 a 2025-05 todos os arquivos têm 20250520, data em que foram coletados.
- Dentro de cada ZIP há um único arquivo de texto, sem cabeçalho, cujo nome não termina em `.csv` nem `.txt` (por exemplo `K3241.K03200Y0.D60711.EMPRECSV`). O trecho `D60711` é uma data (2026-07-11).
- Versões no bruto conferidas em 2026-11-10: uma por competência, 42 competências de 2023-05 a 2026-10; a fonte lista as mesmas 42 pastas. Cada competência é um retrato completo, não um incremento.

## Conteúdo

- Uma linha por estabelecimento por competência. A chave `cnpj_basico` + `cnpj_ordem` + `cnpj_dv` é única nas amostras convertidas (150.000 linhas por competência, sem duplicatas) e na amostra de 1,5 milhão de linhas de `Estabelecimentos5` de 2026-10, que converteu 1.500.000 registros sem perda (conferido em 2026-11-10).
- Cobertura na fonte e no bruto: 42 competências, 2023-05 a 2026-10. Os dados convertidos são **amostras**: as primeiras 150.000 linhas de `Estabelecimentos0` de quatro competências (e as 1,5 milhão de linhas citadas).
- `situacao_cadastral` nas amostras: `01` (nula), `02` (ativa), `03` (suspensa), `04` (inapta) e `08` (baixada). Em 2023-05, 68.860 de 150.000 linhas são baixadas e em 2026-07, 33.926: o arquivo `0` cobre faixas diferentes de CNPJ em cada competência, então as amostras não são comparáveis.
- `cnae_fiscal_secundaria` guarda vários CNAE separados por vírgula (cerca de um terço das linhas das amostras tem mais de um).
- Eras: a partir de 2026-05 o campo `pais` vem com `105` (Brasil) em parte dos estabelecimentos nacionais: 767 de 150.000 linhas em 2026-05, 14.230 em 2026-06, 15.353 em 2026-10 (amostras do primeiro arquivo). Antes, `pais` vinha em menos de 0,3% das linhas, todas com `uf` `EX` (exterior).

## Variáveis

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `cnpj_basico` | `CNPJ BÁSICO` | texto | Número base de inscrição no CNPJ (oito primeiros dígitos do CNPJ) | 8 dígitos | todo |
| `cnpj_ordem` | `CNPJ ORDEM` | texto | Número do estabelecimento de inscrição no CNPJ (do nono ao décimo segundo dígito) | 4 dígitos | todo |
| `cnpj_dv` | `CNPJ DV` | texto | Dígito verificador do número de inscrição no CNPJ (dois últimos dígitos) | 2 dígitos | todo |
| `identificador_matriz_filial` | `IDENTIFICADOR MATRIZ/FILIAL` | texto | Código do identificador matriz/filial | `1` matriz; `2` filial | todo |
| `nome_fantasia` | `NOME FANTASIA` | texto | Nome fantasia | — | todo |
| `situacao_cadastral` | `SITUAÇÃO CADASTRAL` | texto | Código da situação cadastral | `01` nula; `02` ativa; `03` suspensa; `04` inapta; `08` baixada (o metadado escreve `2`, os dados trazem `02`) | todo |
| `data_situacao_cadastral` | `DATA SITUAÇÃO CADASTRAL` | texto | Data do evento da situação cadastral | texto `AAAAMMDD`; `0`/`00000000` = sem data (mantido como texto) | todo |
| `motivo_situacao_cadastral` | `MOTIVO SITUAÇÃO CADASTRAL` | texto | Código do motivo da situação cadastral | 2 dígitos; tabela `motivos` | todo |
| `nome_cidade_exterior` | `NOME DA CIDADE NO EXTERIOR` | texto | Nome da cidade no exterior | — | todo |
| `pais` | `PAIS` | texto | Código do país | 3 dígitos; tabela `paises` | ver Conteúdo (2026-05) |
| `data_inicio_atividade` | `DATA DE INÍCIO ATIVIDADE` | texto | Data de início da atividade | texto `AAAAMMDD` | todo |
| `cnae_fiscal_principal` | `CNAE FISCAL PRINCIPAL` | texto | Código da atividade econômica principal do estabelecimento | 7 dígitos; tabela `cnaes` | todo |
| `cnae_fiscal_secundaria` | `CNAE FISCAL SECUNDÁRIA` | texto | Código(s) da(s) atividade(s) econômica(s) secundária(s), separados por vírgula | lista de códigos de 7 dígitos; tabela `cnaes` | todo |
| `tipo_logradouro` | `TIPO DE LOGRADOURO` | texto | Descrição do tipo de logradouro | — | todo |
| `logradouro` | `LOGRADOURO` | texto | Nome do logradouro onde se localiza o estabelecimento | — | todo |
| `numero` | `NÚMERO` | texto | Número onde se localiza o estabelecimento; `S/N` quando não há | — | todo |
| `complemento` | `COMPLEMENTO` | texto | Complemento do endereço (pode ter quebra de linha) | — | todo |
| `bairro` | `BAIRRO` | texto | Bairro onde se localiza o estabelecimento | — | todo |
| `cep` | `CEP` | texto | Código de endereçamento postal do logradouro | 8 dígitos (alguns vêm com 7) | todo |
| `uf` | `UF` | texto | Sigla da unidade da federação do estabelecimento | sigla; `EX` para exterior | todo |
| `municipio` | `MUNICÍPIO` | texto | Código do município de jurisdição onde se encontra o estabelecimento | 4 dígitos, códigos da Receita; tabela `municipios` | todo |
| `ddd1` | `DDD 1` | texto | DDD do primeiro telefone | — | todo |
| `telefone1` | `TELEFONE 1` | texto | Número do primeiro telefone | — | todo |
| `ddd2` | `DDD 2` | texto | DDD do segundo telefone | — | todo |
| `telefone2` | `TELEFONE 2` | texto | Número do segundo telefone | — | todo |
| `ddd_fax` | `DDD DO FAX` | texto | DDD do fax | — | todo |
| `fax` | `FAX` | texto | Número do fax | — | todo |
| `correio_eletronico` | `CORREIO ELETRÔNICO` | texto | E-mail do contribuinte | — | todo |
| `situacao_especial` | `SITUAÇÃO ESPECIAL` | texto | Situação especial da empresa | não informado pela fonte | todo |
| `data_situacao_especial` | `DATA DA SITUAÇÃO ESPECIAL` | texto | Data em que a empresa entrou em situação especial | texto `AAAAMMDD` | todo |
| `ano` | — (partição) | inteiro | Ano da competência (pasta `AAAA-MM`) | — | todo |
| `mes` | — (partição) | texto | Mês da competência (pasta `AAAA-MM`) | `01` a `12` | todo |

## No lake

- Dataset `rfb-cnpj/estabelecimentos`, particionado por `ano` (inteiro) e `mes` (texto de 2 dígitos, `05`); um Parquet por arquivo do bruto (`Estabelecimentos0.parquet` a `Estabelecimentos9.parquet`).
- O conversor lê o arquivo com o DuckDB em latin-1, `;` como separador, aspas duplas como delimitador e escape, sem cabeçalho (nomes do layout oficial), **tudo como texto**. Campo vazio vira nulo. Os zeros à esquerda dos códigos são mantidos.
- Datas ficam como texto `AAAAMMDD`; o valor "sem data" (`0` ou `00000000`) **não** vira nulo no lake.
- O conversor lê o arquivo de texto do ZIP qualquer que seja o nome dele: o ZIP real da Receita traz o arquivo sem extensão `.csv`/`.txt` (`K3241.K03200Y9.D61010.ESTABELE`).
- Os complementos de endereço com quebra de linha entre aspas são lidos por uma só thread do DuckDB (`parallel=false`); numa amostra de 1,5 milhão de linhas não houve registro perdido.

## Cuidados de uso

- **Conversão do ZIP real conferida.** O arquivo `Estabelecimentos9` de 2026-10, como a Receita o publica, foi convertido sem erro: 4.753.435 registros no bruto e 4.753.435 linhas no Parquet. Os testes do fetcher cobrem o nome de arquivo sem extensão.
- **Endereço, telefone e e-mail são dados de contato.** Em empresas individuais podem ser dados da pessoa; a página os lista no cabeçalho como inventário.
- **O CNPJ completo se monta com três colunas.** `cnpj_basico || cnpj_ordem || cnpj_dv` tem 14 dígitos.
- **Cada competência é um retrato completo e baixados continuam.** Estabelecimentos com situação `08` (baixada) permanecem nas competências seguintes; filtre `situacao_cadastral = '02'` para os ativos. A fonte descreve `2` para ativa; os dados trazem `02`.
- **Sentinelas de data como texto.** Data "sem data" aparece como `0` ou `00000000` em vez de nulo (por exemplo, `data_situacao_cadastral` `0` em 1 linha de 2023-05).
- **CEP com 7 dígitos.** Em 417 de 150.000 linhas de 2023-05 o CEP tem 7 dígitos (zero à esquerda perdido na fonte); cruzar CEP exige `LPAD(cep, 8, '0')`.
- **Município da Receita, não do IBGE.** `municipio` tem 4 dígitos e usa a tabela `municipios` da Receita; para cruzar com IBGE é preciso uma tabela de correspondência.
- **`pais` mudou em 2026-05.** Antes só marcava o exterior; depois `105` aparece também em estabelecimentos nacionais. Não use `pais IS NOT NULL` como "tem endereço no exterior"; use `uf = 'EX'`.
- **Mais de um CNAE por linha.** `cnae_fiscal_secundaria` é uma lista separada por vírgula; use `string_split` antes de contar atividades.
- **CNPJ alfanumérico.** O CNPJ alfanumérico foi anunciado para julho de 2026; as amostras de 2026-10 (primeiras e últimas 100 mil linhas de `Estabelecimentos0`) são numéricas, mas arquivos não amostrados podem trazer letras.
- **Arquivo 0 varia.** `Estabelecimentos0` cobre a faixa mais alta de CNPJ e muda de composição mês a mês; as amostras de competências diferentes não são comparáveis entre si.

## Exemplos

Estabelecimentos ativos por UF numa competência (os 5 maiores), em DuckDB:

```sql
SELECT uf, COUNT(*) AS ativos
FROM read_parquet('lake/rfb-cnpj/estabelecimentos/ano=2026/mes=10/*.parquet')
WHERE situacao_cadastral = '02' AND uf <> 'EX'
GROUP BY uf ORDER BY ativos DESC LIMIT 5;
```

## Referências

- Página de referência dos dados abertos do CNPJ (Receita Federal; não pôde ser lida por leitor automático na conferência de 2026-11-10): https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj
- Metadados do layout dos dados abertos do CNPJ (Receita Federal): https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf
