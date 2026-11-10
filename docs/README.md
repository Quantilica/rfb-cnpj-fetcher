# Receita Federal: dados abertos do CNPJ (`rfb-cnpj`)

O `rfb-cnpj-fetcher` coleta os dados abertos do Cadastro Nacional da Pessoa Jurídica (CNPJ) publicados pela Receita Federal do Brasil (RFB) e os converte para o lake em Parquet particionado por competência. O cadastro tem quatro tabelas de dados (empresas, estabelecimentos, sócios e Simples Nacional/MEI) e seis tabelas de domínio.

Página de referência: https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj (não pôde ser lida por leitor automático na conferência de 2026-11-10). Documento de layout lido: https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf

| Dataset | O que é | Arquivos por competência | Página |
|---|---|---|---|
| `empresas` | Razão social, natureza jurídica, capital social e porte, por raiz de CNPJ | 10 (`Empresas0` a `9`) | [empresas](datasets/empresas.md) |
| `estabelecimentos` | Matriz e filiais: CNPJ completo, situação, CNAE, endereço e contatos | 10 | [estabelecimentos](datasets/estabelecimentos.md) |
| `socios` | Quadro societário e representantes legais | 10 | [socios](datasets/socios.md) |
| `simples` | Opção pelo Simples Nacional e pelo MEI | 1 | [simples](datasets/simples.md) |
| `cnaes` | Tabela de atividades econômicas (CNAE) | 1 | [cnaes](datasets/cnaes.md) |
| `naturezas` | Tabela de naturezas jurídicas | 1 | [naturezas](datasets/naturezas.md) |
| `qualificacoes` | Tabela de qualificações de sócios | 1 | [qualificacoes](datasets/qualificacoes.md) |
| `municipios` | Tabela de municípios (códigos da Receita) | 1 | [municipios](datasets/municipios.md) |
| `paises` | Tabela de países | 1 | [paises](datasets/paises.md) |
| `motivos` | Tabela de motivos de situação cadastral | 1 | [motivos](datasets/motivos.md) |

## Como a Receita publica

- Uma pasta por competência (`AAAA-MM`) num servidor público de arquivos, com 37 ZIPs: 10 de empresas, 10 de estabelecimentos, 10 de sócios, um de Simples e seis de domínio. Na raiz há também um arquivo consolidado, `cnpj.tar.gz` (64 GB em 2026-01), que o fetcher não baixa. A fonte lista 42 competências, de 2023-05 a 2026-10 (conferido em 2026-11-10).
- Cada ZIP guarda um único arquivo de texto, sem cabeçalho, em latin-1, separado por ponto e vírgula e com todos os campos entre aspas. O layout está no documento de metadados da Receita. O nome do arquivo dentro do ZIP não termina em `.csv`: `K3241.K03200Y0.D60711.EMPRECSV` (empresas), `...ESTABELE` (estabelecimentos), `...SOCIOCSV` (sócios), `F.K03200$W.SIMPLES.CSV.D60711` (Simples) e `F.K03200$Z.D60711.CNAECSV` e similares (domínio).
- Cada competência é um retrato completo do cadastro, não um incremento. Os dez arquivos de empresas (e de estabelecimentos e sócios) dividem o cadastro por faixa de `cnpj_basico`; o arquivo `0` fica com a faixa mais alta e é o maior (571 MB de empresas e 2,2 GB de estabelecimentos em 2026-10).
- O fetcher guarda cada ZIP como `AAAA-MM/<grupo>/<Arquivo>@AAAAMMDD.zip`. O sufixo é a data de última modificação do servidor; as competências 2023-05 a 2025-05 têm todas 20250520, a data em que foram coletadas.
- O layout da Receita manda ocultar o CPF dos sócios e dos representantes (três primeiros dígitos e dois verificadores, conforme o art. 129, § 2º, da Lei nº 13.473/2017) e trocar a data de nascimento por uma faixa etária.

## Como os conjuntos se relacionam

- **CNPJ completo.** `cnpj_basico` (8 dígitos) liga `empresas`, `estabelecimentos`, `socios` e `simples`; o CNPJ de 14 dígitos é `cnpj_basico` + `cnpj_ordem` + `cnpj_dv`, só em `estabelecimentos`.
- **Domínios.** `empresas.natureza_juridica` → `naturezas`; `empresas.qualificacao_responsavel`, `socios.qualificacao_socio` e `socios.qualificacao_representante_legal` → `qualificacoes`; `estabelecimentos.motivo_situacao_cadastral` → `motivos`; `estabelecimentos.cnae_fiscal_*` → `cnaes`; `estabelecimentos.municipio` → `municipios`; `estabelecimentos.pais` e `socios.pais` → `paises`.
- **Códigos da Receita.** Município e país usam códigos próprios da Receita, diferentes dos do IBGE e dos de outras fontes.

## Quebras que valem para mais de um conjunto

| Desde | Mudança | Afeta |
|---|---|---|
| 2026-05 | `pais` passa a vir como `105` (Brasil) em parte dos estabelecimentos nacionais | `estabelecimentos` |
| 2026-08 | O documento do sócio pessoa jurídica passa de 14 para 8 dígitos | `socios` |

- A fonte anunciou o CNPJ alfanumérico para julho de 2026. Nas amostras conferidas, até 2026-10, todos os `cnpj_basico` são numéricos.

## Dados pessoais e licença

- `estabelecimentos` (nome fantasia, endereço, telefone, e-mail), `empresas` (razão social, que no empresário individual traz o nome e o CPF completo da pessoa) e `socios` (nome, CPF mascarado, faixa etária) trazem dados de pessoas. O cabeçalho de cada página os lista como inventário.
- A fonte não declara licença para os dados. O rodapé do site da Receita declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada para o conteúdo do site (https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR). Não foi encontrada restrição de coleta ou redistribuição nos documentos lidos.

## Conversão

O conversor lê os ZIPs como a Receita os publica, inclusive quando o arquivo de texto dentro deles não tem extensão `.csv` ou `.txt` (`K3241.K03200Y0.D61010.EMPRECSV`, `F.K03200$W.SIMPLES.CSV.D61010`). Isso exige o extra `analysis` com `quantilica-analytics` 0.11.2 ou superior. Conferido com ZIPs de 2026-10: os seis datasets de domínio e `simples` por inteiro, e `Empresas9`, `Estabelecimentos9` e `Socios9` (um dos dez arquivos de cada); nesses, o número de linhas do Parquet é igual ao de registros do bruto. Os demais arquivos de `empresas`, `estabelecimentos` e `socios` não foram convertidos nessa conferência. Os esquemas de referência vêm de amostras convertidas.
