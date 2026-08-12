# rfb-cnpj-fetcher

O `rfb-cnpj-fetcher` é um pacote responsável por baixar e organizar os dados públicos de CNPJ da Receita Federal do Brasil. Ele coleta os arquivos brutos (ZIP) do repositório oficial da Receita Federal [`arquivos.receitafederal.gov.br`](https://arquivos.receitafederal.gov.br/), organizados por competência mensal, permitindo o acompanhamento de todo o cadastro (empresas, estabelecimentos, sócios, etc.).

Para acessar a documentação completa do ecossistema, incluindo este pacote, visite: [https://docs.quantilica.com](https://docs.quantilica.com)


## Instalação

```bash
# Via índice Quantilica
pip install rfb-cnpj-fetcher --extra-index-url https://quantilica.github.io/quantilica-index/simple/

# Ou via quantilica-cli
quantilica install rfb-cnpj
```

## Uso

### CLI standalone

```bash
# Listar competências disponíveis
rfb-cnpj-fetcher list

# Baixar competência mais recente (todos os grupos)
rfb-cnpj-fetcher sync

# Baixar grupos específicos da competência mais recente
rfb-cnpj-fetcher sync empresas socios simples

# Baixar competência específica
rfb-cnpj-fetcher sync --competencia 2025-07

# Listar arquivos sem baixar (dry-run)
rfb-cnpj-fetcher sync --dry-run

# Histórico completo
rfb-cnpj-fetcher sync --all

# Saída customizada
rfb-cnpj-fetcher sync -o /mnt/dados/rfb-cnpj
```

### Via quantilica-cli

```bash
quantilica rfb-cnpj list
quantilica rfb-cnpj sync
quantilica rfb-cnpj sync empresas socios --competencia 2025-07
quantilica rfb-cnpj sync --dry-run simples cnaes
```

## Grupos disponíveis

| Grupo | Conteúdo |
|---|---|
| `empresas` | CNPJ básico, razão social, natureza jurídica, porte |
| `estabelecimentos` | CNPJ completo, endereço, telefone, situação cadastral |
| `socios` | Quadro societário, qualificação, faixa etária |
| `simples` | Opção Simples Nacional e MEI |
| `cnaes` | Tabela de CNAEs |
| `naturezas` | Tabela de naturezas jurídicas |
| `qualificacoes` | Tabela de qualificações de sócios |
| `municipios` | Tabela de municípios IBGE |
| `paises` | Tabela de países |
| `motivos` | Tabela de motivos de situação cadastral |

## Estrutura de saída

```
/data/rfb-cnpj/
└── 2025-07/
    ├── empresas/
    │   ├── Empresas0@20250710.zip
    │   └── Empresas0@20250710.zip.manifest.json
    ├── estabelecimentos/
    │   └── Estabelecimentos0@20250710.zip
    ├── socios/
    │   └── Socios0@20250710.zip
    └── simples/
        └── Simples@20250710.zip
```

Cada arquivo `.zip` é acompanhado de um manifesto JSON com checksum SHA-256,
URL de origem, produtor e timestamp de download.

## Changelog

Ver [CHANGELOG.md](CHANGELOG.md).

## Licença

MIT — ver [LICENSE](LICENSE).
