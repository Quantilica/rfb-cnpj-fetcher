# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Corrigido
- `convert` fixa aspas duplas como `quote` e `escape` na leitura dos ZIPs. Antes, o
  DuckDB podia detectar o apóstrofo de uma razão social (`D'AGUA`) como escape e
  abortar o arquivo com `CSV Error on Line`; numa competência inteira, metade dos
  arquivos de empresas, estabelecimentos e sócios falhava.
- `convert` lê os ZIPs com uma só thread do DuckDB: há complementos de endereço com
  quebra de linha entre aspas, que o leitor paralelo recusa.
- Arquivos com bytes entre 0x80 e 0x9F (válidos em Latin-1) deixam de falhar com
  "File is not latin-1 encoded".
- Extra `analysis` exige `quantilica-analytics>=0.6.0`.

## [0.5.0] - 2026-10-27

### Adicionado
- Módulo `rfb_cnpj_fetcher.lake` e entry point `quantilica.lake`: conversão dos arquivos ZIP da Receita Federal para o formato universal Parquet com particionamento Hive (`ano=/mes=`).
- Comandos CLI `convert` e `pipeline` integrados via SDK do `FetcherApp`, com suporte a `--lake`, `--dataset` e `--force`.
- Extra `analysis` agora inclui `duckdb>=1.2.0` e `quantilica-analytics>=0.5.0` para conversão em streaming com metadados de proveniência e descritor `_dataset.json`.
- Dependência de base `quantilica-core` atualizada para `>=0.13.0` para conformidade com o contrato de layout Hive.

## [0.4.0] - 2026-10-20

### Adicionado
- `rfb_cnpj_fetcher.reader` (extra `analysis`): `read_file()` lê um ZIP baixado num
  DataFrame Polars tipado, com o layout dos dez grupos da Receita (Latin-1, `;`,
  campos entre aspas). Códigos (partes do CNPJ, CNAE, natureza, município, país)
  ficam como texto, com zeros à esquerda; `capital_social` é `Decimal(20, 2)`; datas
  `AAAAMMDD` viram `Date`, e só as sentinelas de "sem data" (`0`, `00000000`, vazio)
  viram nulo. Conversões estritas: linha com número de campos diferente do layout,
  data inválida ou capital não numérico levantam `ValueError` em vez de deslocar
  colunas ou virar nulo.
- `write_parquet()` delega ao `quantilica.analytics.writer.to_parquet`, com a
  proveniência do manifesto quando o ZIP de origem tem `.manifest.json`.

### Corrigido
- README: o grupo `municipios` traz o código de município da Receita (4 dígitos),
  não o do IBGE.

## [0.3.2] - 2026-10-20

### Corrigido
- Fallback do token de share e PROPFIND WebDAV resiliente a respostas XML vazias.
- Download sem header `Authorization` em URLs públicas via `dav/files/{token}`.
- Pin de `pytest-cov>=7.1` no grupo dev.

### Removido
- Removida dependência não utilizada `beautifulsoup4`.

### Alterado
- `cli.py` protege o import do plugin; sem o host a CLI standalone sai com código 1 e orienta `quantilica install rfb-cnpj`.

## [0.3.1] - 2026-08-30
### Alterado
- Docstrings de exceção atualizadas para os tipos `httpx2` (`httpx2.HTTPError`), alinhadas à migração do `quantilica-core`.
- Dependência `quantilica-core` elevada para `>=0.6.0`.

## [0.3.0] - 2026-08-07
### Alterado
- Refatoração arquitetural: Remoção de dependências (`quantilica-cli` e `quantilica-catalog`) e limpeza de imports. Os fetchers agora são pacotes de extração puros, dependendo estritamente do `quantilica-core`.

## [0.2.0] - 2026-08-02

### Alterado

- Atualizada a origem de dados para o repositório Nextcloud da Receita Federal
  em `https://arquivos.receitafederal.gov.br/`.
- Implementada navegação e listagem via protocolo WebDAV (`/public.php/webdav/Dados/Cadastros/CNPJ/`)
  com resolução dinâmica do token de compartilhamento público e cabeçalhos de autenticação Basic.

## [0.1.0] - 2026-08-02


Versão inicial do pacote.

### Adicionado

- Descoberta dinâmica de competências e arquivos via scraping do índice HTTP
  do portal `dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/`.
- CLI standalone (`rfb-cnpj-fetcher`) com subcomandos `sync` e `list`
  (argparse, sem dependência de Typer/Rich).
- Plugin Typer para integração com `quantilica-cli` (`quantilica rfb-cnpj`).
- Suporte a 10 grupos de dados brutos: `empresas`, `estabelecimentos`,
  `socios`, `simples`, `cnaes`, `naturezas`, `qualificacoes`, `municipios`,
  `paises` e `motivos`.
- Opção `--competencia YYYY-MM` para selecionar competência específica.
- Opção `--all` para sincronizar o histórico completo de competências.
- Seleção de grupos por argumentos posicionais (`sync empresas socios`).
- Manifesto SHA-256 por arquivo via `quantilica-core`.
- Barras de progresso duplas (batch + bytes) via Rich + `quantilica.core.cli`.
- Storage seguindo convenção de nomenclatura `<base>@<YYYYMMDD>.zip` do ecossistema.
