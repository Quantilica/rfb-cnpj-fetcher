# Changelog

## [0.3.0] - 2026-08-07
### Alterado
- Refatoração arquitetural: Remoção de dependências (`quantilica-cli` e `quantilica-catalog`) e limpeza de imports. Os fetchers agora são pacotes de extração puros, dependendo estritamente do `quantilica-core`.

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

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
