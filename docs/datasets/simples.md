---
dataset:
  id: simples
  fonte: rfb-cnpj
  titulo: "Simples Nacional e MEI"
  resumo: "Opção pelo Simples Nacional e pelo MEI de cada empresa, com as datas de opção e de exclusão."
  orgao: "Receita Federal do Brasil (RFB)"
  pagina_oficial: "https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj"
  licenca: "Não declarada para os dados. O rodapé do site gov.br da Receita declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR) para o conteúdo do site, sem dizer que vale para o conjunto de dados. Não foi encontrada restrição de coleta ou redistribuição nos documentos lidos (conferido em 2026-11-10)"
  periodicidade: "mensal, uma pasta por competência (`AAAA-MM`)"
  cobertura: {inicio: 2023-05, fim: em-curso}
  unidade: "uma empresa (raiz do CNPJ) com seus dados de opção pelo Simples Nacional e pelo MEI numa competência"
  granularidade: {espacial: "empresa / estabelecimento (sem geografia própria)", temporal: "competência (mês)"}
  formato_bruto: "ZIPs com um arquivo de texto sem cabeçalho, latin-1, separador ponto e vírgula, todos os campos entre aspas duplas (inclusive os vazios), um registro por linha; layout dado pelo documento de metadados da Receita"
  lake: {estado: convertido, particoes: [ano, mes], chave: [ano, mes, cnpj_basico], colunas: 7}
  unidades_de_medida: null
  dados_pessoais: nenhum
  eras: []
  revisado_em: 2026-11-10
  versao_fetcher: 0.5.3
---

# Simples Nacional e MEI

## Resumo

A situação de cada empresa no Simples Nacional e no regime do Microempreendedor Individual (MEI): se há opção, quando a empresa optou e quando foi excluída. Um arquivo único, `Simples.zip`, por competência (310 MB em 2026-10).

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `rfb-cnpj/simples` |
| Órgão | Receita Federal do Brasil (RFB) |
| Página oficial | https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj |
| Licença | Não declarada para os dados. O rodapé do site gov.br da Receita declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR) para o conteúdo do site, sem dizer que vale para o conjunto de dados. Não foi encontrada restrição de coleta ou redistribuição nos documentos lidos (conferido em 2026-11-10) |
| Periodicidade | mensal, uma pasta por competência (`AAAA-MM`) |
| Cobertura | 2023-05 a em-curso |
| Unidade (uma linha) | uma empresa (raiz do CNPJ) com seus dados de opção pelo Simples Nacional e pelo MEI numa competência |
| Granularidade | espacial: empresa / estabelecimento (sem geografia própria); temporal: competência (mês) |
| Formato bruto | ZIPs com um arquivo de texto sem cabeçalho, latin-1, separador ponto e vírgula, todos os campos entre aspas duplas (inclusive os vazios), um registro por linha; layout dado pelo documento de metadados da Receita |
| Estado no lake | convertido |
| Partições | `ano`, `mes` |
| Chave | `ano`, `mes`, `cnpj_basico` |
| Colunas | 7 |
| Unidades de medida | — |
| Dados pessoais | nenhum |
| Eras | nenhuma |
| Revisado em | 2026-11-10 |
| Versão do fetcher | 0.5.3 |

## Origem e coleta

- O fetcher lista a pasta pública da Receita (`Dados/Cadastros/CNPJ/AAAA-MM/`) e baixa `Simples.zip` de cada competência, em um arquivo. No bruto: `AAAA-MM/simples/Simples@AAAAMMDD.zip`, com um `.manifest.json` ao lado. O sufixo é a data de última modificação informada pelo servidor; nas competências 2023-05 a 2025-05 todos os arquivos têm 20250520, data em que foram coletados.
- Dentro de cada ZIP há um único arquivo de texto, sem cabeçalho, cujo nome não termina em `.csv` nem `.txt` (por exemplo `K3241.K03200Y0.D60711.EMPRECSV`). O trecho `D60711` é uma data (2026-07-11).
- Versões no bruto conferidas em 2026-11-10: uma por competência, 42 competências de 2023-05 a 2026-10; a fonte lista as mesmas 42 pastas. Cada competência é um retrato completo, não um incremento.

## Conteúdo

- Uma linha por empresa (`cnpj_basico`) por competência. O `cnpj_basico` é único nas amostras convertidas (150.000 por competência).
- Cobertura na fonte e no bruto: 42 competências, 2023-05 a 2026-10. Os dados convertidos são **amostras**: as primeiras 150.000 linhas de `Simples` de quatro competências.
- `opcao_simples` nas amostras: `S` ou `N` (nunca nulo). Em 2026-10, 58.662 de 150.000 são `S`; `opcao_mei` `S` em 3.281.
- As datas ausentes vêm como `00000000` (e continuam como texto no lake): 56.496 de 150.000 `data_exclusao_simples` em 2026-10, 143.133 de `data_opcao_mei`.

## Variáveis

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `cnpj_basico` | `CNPJ BÁSICO` | texto | Número base de inscrição no CNPJ (oito primeiros dígitos) | 8 dígitos | todo |
| `opcao_simples` | `OPÇÃO PELO SIMPLES` | texto | Indicador da existência da opção pelo Simples | `S` sim; `N` não; em branco = outros | todo |
| `data_opcao_simples` | `DATA DE OPÇÃO PELO SIMPLES` | texto | Data de opção pelo Simples | texto `AAAAMMDD`; `00000000` = sem data | todo |
| `data_exclusao_simples` | `DATA DE EXCLUSÃO DO SIMPLES` | texto | Data de exclusão do Simples | texto `AAAAMMDD`; `00000000` = sem data | todo |
| `opcao_mei` | `OPÇÃO PELO MEI` | texto | Indicador da existência da opção pelo MEI | `S` sim; `N` não; em branco = outros | todo |
| `data_opcao_mei` | `DATA DE OPÇÃO PELO MEI` | texto | Data de opção pelo MEI | texto `AAAAMMDD`; `00000000` = sem data | todo |
| `data_exclusao_mei` | `DATA DE EXCLUSÃO DO MEI` | texto | Data de exclusão do MEI | texto `AAAAMMDD`; `00000000` = sem data | todo |
| `ano` | — (partição) | inteiro | Ano da competência (pasta `AAAA-MM`) | — | todo |
| `mes` | — (partição) | texto | Mês da competência (pasta `AAAA-MM`) | `01` a `12` | todo |

## No lake

- Dataset `rfb-cnpj/simples`, particionado por `ano` (inteiro) e `mes` (texto de 2 dígitos, `05`); um Parquet por arquivo do bruto (`Simples.parquet`).
- O conversor lê o arquivo com o DuckDB em latin-1, `;` como separador, aspas duplas como delimitador e escape, sem cabeçalho (nomes do layout oficial), **tudo como texto**. Campo vazio vira nulo. Os zeros à esquerda dos códigos são mantidos.
- Datas ficam como texto `AAAAMMDD`; o valor "sem data" (`0` ou `00000000`) **não** vira nulo no lake.
- O conversor lê o arquivo de texto do ZIP qualquer que seja o nome dele: o ZIP real da Receita traz o arquivo sem extensão `.csv`/`.txt` (`F.K03200$W.SIMPLES.CSV.D61010`).

## Cuidados de uso

- **Conversão do ZIP real conferida.** O arquivo `Simples` de 2026-10, como a Receita o publica, foi convertido sem erro: 50.806.102 registros no bruto e 50.806.102 linhas no Parquet. Os testes do fetcher cobrem o nome de arquivo sem extensão.
- **`00000000` não é nulo.** As datas ausentes ficam como o texto `00000000`; converter com `strptime` sem tratar o valor falha. Use `NULLIF(data, '00000000')`.
- **Sem dados do Simples = ausência de linha, não `N`.** A tabela só traz as empresas que a Receita listou; cruze com `empresas` por `cnpj_basico` com `LEFT JOIN`.
- **Exclusão não é fim do regime atual.** Uma empresa pode ter opção, exclusão e nova opção; o arquivo traz o retrato das datas na competência.
- **Cada competência é um retrato completo.** Não some empresas entre competências.

## Exemplos

Empresas optantes pelo Simples na competência de 2026-10 (contagem por opção):

```sql
SELECT opcao_simples, opcao_mei, COUNT(*) AS empresas
FROM read_parquet('lake/rfb-cnpj/simples/ano=2026/mes=10/*.parquet')
GROUP BY ALL ORDER BY empresas DESC;
```

## Referências

- Página de referência dos dados abertos do CNPJ (Receita Federal; não pôde ser lida por leitor automático na conferência de 2026-11-10): https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj
- Metadados do layout dos dados abertos do CNPJ (Receita Federal): https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf
