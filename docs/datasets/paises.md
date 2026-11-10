---
dataset:
  id: paises
  fonte: rfb-cnpj
  titulo: "Países (tabela de domínio da Receita)"
  resumo: "Tabela de domínio da Receita Federal: código e nome do país."
  orgao: "Receita Federal do Brasil (RFB)"
  pagina_oficial: "https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj"
  licenca: "Não declarada para os dados. O rodapé do site gov.br da Receita declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR) para o conteúdo do site, sem dizer que vale para o conjunto de dados. Não foi encontrada restrição de coleta ou redistribuição nos documentos lidos (conferido em 2026-11-10)"
  periodicidade: "mensal, junto com a competência do cadastro"
  cobertura: {inicio: 2023-05, fim: em-curso}
  unidade: "um código de país e sua descrição"
  granularidade: {espacial: "não se aplica", temporal: "competência (mês)"}
  formato_bruto: "ZIPs com um arquivo de texto sem cabeçalho, latin-1, separador ponto e vírgula, todos os campos entre aspas duplas (inclusive os vazios), um registro por linha; layout dado pelo documento de metadados da Receita"
  lake: {estado: convertido, particoes: [ano, mes], chave: [ano, mes, codigo], colunas: 2}
  unidades_de_medida: null
  dados_pessoais: nenhum
  eras: []
  revisado_em: 2026-11-10
  versao_fetcher: 0.5.3
---

# Países (tabela de domínio da Receita)

## Resumo

Tabela de domínio que a Receita publica a cada competência para traduzir o código de país usado nos arquivos de empresas, estabelecimentos e sócios. Dois campos: `codigo` e `descricao`.

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `rfb-cnpj/paises` |
| Órgão | Receita Federal do Brasil (RFB) |
| Página oficial | https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj |
| Licença | Não declarada para os dados. O rodapé do site gov.br da Receita declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR) para o conteúdo do site, sem dizer que vale para o conjunto de dados. Não foi encontrada restrição de coleta ou redistribuição nos documentos lidos (conferido em 2026-11-10) |
| Periodicidade | mensal, junto com a competência do cadastro |
| Cobertura | 2023-05 a em-curso |
| Unidade (uma linha) | um código de país e sua descrição |
| Granularidade | espacial: não se aplica; temporal: competência (mês) |
| Formato bruto | ZIPs com um arquivo de texto sem cabeçalho, latin-1, separador ponto e vírgula, todos os campos entre aspas duplas (inclusive os vazios), um registro por linha; layout dado pelo documento de metadados da Receita |
| Estado no lake | convertido |
| Partições | `ano`, `mes` |
| Chave | `ano`, `mes`, `codigo` |
| Colunas | 2 |
| Unidades de medida | — |
| Dados pessoais | nenhum |
| Eras | nenhuma |
| Revisado em | 2026-11-10 |
| Versão do fetcher | 0.5.3 |

## Origem e coleta

- O fetcher lista a pasta pública da Receita (`Dados/Cadastros/CNPJ/AAAA-MM/`, servidor de arquivos da Receita) e baixa `Paises.zip` de cada competência. No bruto: `AAAA-MM/paises/Paises@AAAAMMDD.zip`, com um `.manifest.json` ao lado. O sufixo é a data de última modificação informada pelo servidor; nas competências 2023-05 a 2025-05 todos os arquivos têm 20250520, data em que foram coletados.
- Dentro do ZIP há um único arquivo de texto cujo nome termina sem extensão de texto (por exemplo `F.K03200$Z.D60711.CNAECSV`); o sufixo antes da data indica a tabela.
- Versões no bruto conferidas em 2026-11-10: uma por competência, 42 competências de 2023-05 a 2026-10; a fonte lista as mesmas 42 pastas.

## Conteúdo

- 255 códigos de 3 dígitos, de `000` a `999`, em todas as amostras; `105` é BRASIL e `249` é ESTADOS UNIDOS.
- Cobertura no bruto e na fonte: 42 competências, 2023-05 a 2026-10 (conferido em 2026-11-10). Amostras convertidas: 2023-05, 2025-06, 2026-07 e 2026-10; em todas, `codigo` é único e `descricao` não é nula.
- Os códigos são os usados em `pais` de `estabelecimentos` e de `socios`. Os nomes vêm em maiúsculas e sem acento (`COLIS POSTAUX` é o código `000`).

## Variáveis

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `codigo` | `CÓDIGO` | texto | Código de país | texto com zeros à esquerda | todo |
| `descricao` | `DESCRIÇÃO` | texto | Nome de país | — | todo |
| `ano` | — (partição) | inteiro | Ano da competência (pasta `AAAA-MM`) | — | todo |
| `mes` | — (partição) | texto | Mês da competência (pasta `AAAA-MM`) | `01` a `12` | todo |

## No lake

- Dataset `rfb-cnpj/paises`, particionado por `ano` (inteiro) e `mes` (texto de 2 dígitos, `05`); um Parquet por arquivo do bruto (`Paises.parquet`).
- O conversor lê o arquivo com o DuckDB em latin-1, `;` como separador, aspas duplas como delimitador e escape, sem cabeçalho (nomes do layout oficial), **tudo como texto**. Campo vazio vira nulo. Os zeros à esquerda dos códigos são mantidos.
- Datas ficam como texto `AAAAMMDD`; o valor "sem data" (`0` ou `00000000`) **não** vira nulo no lake.
- O conversor lê o arquivo de texto do ZIP qualquer que seja o nome dele: o ZIP real da Receita traz o arquivo sem extensão `.csv`/`.txt` (`F.K03200$Z.D61010.PAISCSV`).

## Cuidados de uso

- **Conversão do ZIP real conferida.** O arquivo `Paises` de 2026-10, como a Receita o publica, foi convertido sem erro: 255 registros no bruto e 255 linhas no Parquet. Os testes do fetcher cobrem o nome de arquivo sem extensão.
- **Códigos da Receita.** Não são ISO nem os da tabela de países do comércio exterior; cruze pelo nome com cuidado.
- **Cada competência repete a tabela inteira.** Para traduzir um código use a mesma competência do dado, ou a mais recente, e não junte todas as competências sem filtrar `ano` e `mes`.

## Exemplos

Descrição de país na competência mais recente do lake:

```python
import polars as pl

tab = (
    pl.scan_parquet("lake/rfb-cnpj/paises/**/*.parquet", hive_partitioning=True)
    .filter((pl.col("ano") == 2026) & (pl.col("mes") == "10"))
    .select("codigo", "descricao")
    .collect()
)
```

## Referências

- Página de referência dos dados abertos do CNPJ (Receita Federal; não pôde ser lida por leitor automático na conferência de 2026-11-10): https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj
- Metadados do layout dos dados abertos do CNPJ (Receita Federal): https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf
