# BG Store

Sistema web de gestão de uma loja de iPhones. Python + Django 5.2 LTS, SQLite persistente, interface responsiva em preto, dourado e branco. Começa vazio, sem clientes, aparelhos, vendas ou senhas padrão.

**Primeiro acesso:** siga [LEIA-ME — abrir no computador](docs/COMECE-AQUI.md).

## Implementado

- Login com senha criptografada, CSRF, sessões, limitação de tentativas (5 por usuário em 15 minutos), administrador e vendedor com verificações no servidor.
- Aparelhos individuais com IMEIs únicos entre ambos os slots, série única, fotos, nota fiscal de origem anexada, custo, despesas de entrada, preço, procedência e checklist manual.
- Compra gera conta a pagar. Troca/upgrade é concluída junto da venda e recebe avaliação como crédito, sem criar pagamento fictício da aquisição.
- Clientes/fornecedores com validação de CPF/CNPJ opcional e histórico de vendas, entradas, documentos e atendimentos.
- Acessórios com quantidade, mínimo, reposição, custo médio ponderado e movimentações com histórico.
- Venda de vários aparelhos e acessórios, desconto total, Pix, dinheiro e cartão combinados. Preço vem do cadastro. Taxas de cartão não vêm preenchidas: cadastre as contratadas. Parcelas têm previsão de recebimento, não confirmação bancária.
- Transações atômicas, atualização condicional de estoque, restrição de venda ativa por aparelho e chave de idempotência no formulário de venda.
- Cancelamento administrativo sem apagar registros: restaura estoque, anula recebíveis não quitados e cria estornos pendentes para valores recebidos. Só quite estorno quando o dinheiro realmente sair. Aparelho de troca já vendido impede cancelar a venda original.
- Garantia de seminovo BG Store por nove meses de calendário; Apple de um ano para lacrados, separada e **sem inventar confirmação ou vencimento**. Datas de ativação e vencimento Apple e sua fonte são registradas manualmente. Atendimentos e PDF assinado podem ser anexados.
- Entrada, comprovante de venda e termo de garantia imprimíveis ou salvos em PDF pelo navegador. Todos identificados como documentos internos, não fiscais. Dados da loja, cliente, itens e minuta de garantia das vendas são preservados no momento da conclusão.
- Financeiro com contas, quitação manual, despesas por categoria, recebíveis líquidos de cartão, anulação/estorno de lançamentos avulsos e saldo de caixa. Painel por período com faturamento, resultado das vendas, caixa, despesas operacionais pagas, estoque a custo, aparelhos parados e garantias a vencer.
- Histórico de ações e estoque; exportação JSON; backup e restauração do banco, usuários e anexos.

## Limites honestos desta versão

Não emite NF-e/NFC-e nem documento fiscal de entrada. Não se conecta a SEFAZ, Apple, consultas de IMEI, WhatsApp, Instagram, bancos, maquininhas ou assinatura digital. Não há OS completa, orçamento, catálogo público, funil de CRM ou relatório avançado. A tela Módulos informa esses estados sem simular execução. Reservas são apenas um status do aparelho, sem prazo ou sinal.

Não há edição retroativa de custos ou preços dos aparelhos nesta versão; cadastre-os cuidadosamente antes da entrada. Não há devolução parcial, crédito maior que o valor de uma venda, troca de vários aparelhos de uma vez, crediário ou fluxo de devolução de compra ao fornecedor. Ajustes de perdas de acessórios registram estoque, mas não geram despesa automaticamente. Compras vinculadas exigem conciliação por lançamentos identificados, sem apagar o histórico. Quantidades e despesas de entrada não indicam pagamento: a compra fica a pagar até a quitação.

O resultado por venda é total menos custos dos itens e taxas; **não é lucro líquido contábil**. Despesas vinculadas ao aparelho entram no custo e não são deduzidas duas vezes. O dashboard usa pagamentos efetivos para despesas operacionais. As categorias de despesas são texto informado pela loja. O estoque é uma avaliação operacional, não uma contabilidade fiscal. Valores são calculados no servidor com Decimal e arredondamento de taxas por meio de pagamento; o resíduo de centavos vai para a última parcela. Datas em America/Sao_Paulo.

SQLite atende a operação inicial de uma loja em um único servidor, com gravações curtas. Operações simultâneas podem exigir repetir a solicitação após conferir o histórico. Mais usuários, múltiplas instâncias e hospedagem com volume compartilhado requerem migração planejada para PostgreSQL. Não coloque o SQLite em pasta sincronizada em tempo real por OneDrive/Dropbox nem use múltiplas réplicas da aplicação com bancos separados.

As telas listam os últimos 200 registros (financeiro e auditoria: 300). A exportação contém todos os registros. Não há exclusão de registros comerciais pela interface. O histórico é operacional; um administrador do próprio servidor ainda controla o banco.

## Desenvolvimento

Python 3.12 ou superior (3.12 usado na validação).

```sh
python -m venv .venv
# Linux/macOS:
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createuser seuusuario --role admin
.venv/bin/python manage.py runserver
```

No Windows, troque `.venv/bin/python` por `.venv\Scripts\python.exe`.

```sh
.venv/bin/python manage.py test
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
```

Os testes usam banco isolado temporário. Nunca carregam registros fictícios no banco da loja. Os dados ficam em `data/`, ignorado pelo Git. A chave de desenvolvimento é gerada localmente em `data/.development-key`. Não existe senha inicial. `.env` não é carregado automaticamente: use variáveis do processo ou o EnvironmentFile da hospedagem.

## Organização

- `core/models.py`: cadastros, estoque, venda, pagamentos, contas, garantias e auditoria.
- `core/services.py`: operações atômicas de entrada, venda e cancelamento; cálculos monetários.
- `core/forms.py`: validação dos formulários e anexos (até 8 MB por arquivo).
- `core/views.py`: autenticação, permissões e fluxos HTTP.
- `core/templates/`, `core/static/`: interface e documentos, sem dependências de CDN.
- `core/tests.py`: testes automatizados dos fluxos essenciais e proteções.
- `core/management/commands/`: usuários, backup e restauração.
- `docs/HOSPEDAGEM.md`: preparação para hospedagem, sem contratação ou publicação.
- `docs/BACKUP.md`: recuperação passo a passo.

## Identidade e referência

O nome BG Store e as cores são usados em uma interface própria. A logo anexada na conversa não ficou acessível como arquivo no workspace; a tela Configurações permite enviar o original em PNG/JPG (não substituímos a marca por uma logo inventada). Até o envio, o sistema mostra as letras BG.

Referência solicitada: https://mercadophone.app.br/recursos/. O acesso automatizado à página retornou HTTP 403 neste ambiente, portanto não foi possível verificar seu conteúdo. As funções implementadas partem da lista fornecida pelo proprietário da BG Store; não há cópia de marca nem declaração de paridade com a Mercado Phone.
