# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Alterado
- **Quebra de layout no lake: um Parquet por dataset e mês.** Os ZIPs do mesmo dataset e mês (`Empresas0` a `Empresas9`, `Estabelecimentos0` a `9`, `Socios0` a `9`, e também os arquivos únicos como `Simples` e `Cnaes`) viram um Parquet só, escrito por `LakeWriter.write_group`. Antes e depois, em `rfb-cnpj/<dataset>/ano=AAAA/mes=MM/`:
  - antes: `Empresas0.parquet` ... `Empresas9.parquet` (10 arquivos por mês em `empresas`, `estabelecimentos` e `socios`; 1 nos demais);
  - depois: `empresas_AAAAMM.parquet`, `estabelecimentos_AAAAMM.parquet`, `socios_AAAAMM.parquet`, `simples_AAAAMM.parquet`, `cnaes_AAAAMM.parquet`... (1 por dataset e mês, sem sufixo `-NNN`, qualquer que seja o tamanho).
  - As pastas `ano=`/`mes=` não mudam. Cada linha ganha a coluna `_origem` (o arquivo do ZIP de onde veio, ex.: `Empresas3`) e o rodapé do Parquet lista os ZIPs (`quantilica.members`, com sha256 e linhas de cada um). A parte do ZIP não vira coluna de dados: ela divide as empresas por faixa de CNPJ, sem significado de negócio.
  - Na reconversão os Parquets antigos do mês saem sozinhos depois que o novo é publicado, desde que o sha256 de origem de cada um seja de um ZIP do grupo; um Parquet antigo cujo ZIP já não está no bruto fica no lake (o grupo não tem as linhas dele) e deve ser apagado à mão.
- O mês é escrito numa passada só e em streaming (o DuckDB lê o CSV extraído e o Parquet do mês sai por `COPY`); só um ZIP fica extraído no disco por vez. `estabelecimentos` chega a cerca de 3 GB de Parquet por mês, acima da faixa de 64 MB a 1 GB do lake, porque o grupo é sempre um arquivo só.
- Um ZIP novo ou alterado reescreve o Parquet do mês inteiro, mas só o ZIP novo é extraído e lido; os outros têm as linhas copiadas do arquivo existente. A lista de ZIPs do mês no bruto é a lista completa do grupo: um ZIP que sai do bruto sai do Parquet. Se há duas safras (`@data`) do mesmo ZIP, só a mais recente entra.
- O reconversor passa a registrar `contract_version` (1) e `converter_version` ("1") em cada membro; mudar o layout ou a leitura do CSV e subir uma delas reconverte o mês.
- `ConvertResult.converted` e `skipped` continuam contando ZIPs; cada mensagem de `errors` agora começa pelo grupo (`socios_202610: ...`) e um ZIP com erro impede a escrita do mês daquele dataset.
- Exige `quantilica-analytics>=0.12.0` no extra `analysis` (`write_group`).
- Documentação dos dados: a seção "No lake" dos dez datasets descreve o arquivo mensal e `_origem`.

### Adicionado
- Testes: identidade do registro conferida.
- Testes de equivalência do agrupamento: o conteúdo do lake (linhas, colunas e tipos, linhas ordenadas por dataset e mês) é igual ao do conversor de um Parquet por ZIP (`tests/golden/lake_antes_do_agrupamento.json`, gerado antes da mudança), mais segunda execução sem reescrita, migração do layout antigo sem linhas duplicadas e `lake_audit` limpo.

### Corrigido
- CI: o pyproject declara o PyPI antes do índice Quantilica (`[[tool.uv.index]]`), e o workflow perde `--index` e `--index-strategy`. Com a estratégia padrão `first-index`, o `uv sync` só consulta o índice para o que não está no PyPI (`quantilica-analytics`) e deixa de receber o 503 intermitente que o GitHub Pages devolve a caminhos inexistentes.
- `catalog`: comentário no tratamento de falha de rede da descoberta do token de share, deixando explícito que o aviso do fallback (logo abaixo) já registra o erro. Sem mudança de comportamento.

## [0.7.0] - 2026-11-14

### Alterado
- Domínio temático do registro passa de `empresas` para `fiscal`, igual à área da fonte no hub do portal.
- Requer `quantilica-core>=0.19.0` (e `quantilica-cli>=0.17.0` como host).
- `FetcherInfo.licenca` passa a declarar a licença da fonte: Sem licença declarada; dados públicos pela Lei 12.527/2011 (LAI) e Decreto 8.777/2016.

### Adicionado
- O fetcher declara os fatos da fonte (`FetcherInfo`: id canônico, apelidos, órgão, licença, página e cadência) para o registro de fetchers da Quantilica.

## [0.6.0] - 2026-11-10

### Alterado
- Exige `quantilica-analytics>=0.11.2` no extra `analysis`: as versões 0.10.0 a 0.11.1 recusavam os ZIPs reais da Receita, cujo arquivo de dados não termina em `.csv` nem `.txt`.

### Adicionado
- Documentação dos dados em `docs/`, conforme a norma de documentação dos dados: página da fonte, página de cada um dos dez datasets com dicionário de todas as variáveis e esquema de referência do lake. Um teste a verifica.

## [0.5.3] - 2026-11-04

### Corrigido
- Sem o extra `analysis`, o comando `convert` termina com código 1 e a instrução de instalação (`quantilica install rfb-cnpj --extra analysis`), sem traceback.

### Alterado
- O diretório de saída padrão (`/data/rfb-cnpj`) passa a ser declarado explicitamente no plugin; o valor não muda.

## [0.5.2] - 2026-11-04

### Corrigido
- Política de frescor volta a F1 (`HEAD_OR_MANIFEST`): `REMOTE_ONLY` (F3, para fontes sem validadores) causava re-download diário de fontes com Last-Modified/ETag, porque descartava o Last-Modified e o nome do arquivo caía em `@hoje`.

### Alterado
- Exige `quantilica-core>=0.16.0`.

## [0.5.1] - 2026-10-29

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
