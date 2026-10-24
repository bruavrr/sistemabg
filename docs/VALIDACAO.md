# Validações executadas

## Verificações originais — primeira versão

`python manage.py test --verbosity 1`: **24 testes passaram**, com banco de teste separado, sem inserir dados no banco da loja.

Cobertura dos fluxos:

- Entrada com IMEIs, movimento, auditoria e contas de aquisição/despesas.
- Duplicidade de IMEI entre slots e no mesmo formulário, além da restrição no banco.
- Venda com aparelho, acessórios, desconto, dinheiro e cartão com taxa fracionária; arredondamento e distribuição do resíduo entre parcelas.
- Venda repetida bloqueada; repetição da mesma solicitação não duplica a operação.
- Pagamentos que não fecham, cartão sem taxa e estoque insuficiente rejeitados sem registros parciais.
- Upgrade com avaliação e diferença paga, origem obrigatoriamente igual ao cliente e entrada atômica.
- Cancelamento restaura itens uma única vez, anula recebíveis e cria reembolso pendente para recebimentos efetivos.
- Cancelamento de upgrade bloqueado após revenda do aparelho recebido.
- Garantia de nove meses com ajuste de fim de mês; lacrado sem confirmação Apple fictícia.
- Abertura de todas as telas principais e documentos com IMEI e distinção fiscal.
- Permissões verificadas em GET/POST, proteção CSRF, bloqueio de tentativas de login e arquivos privados com proteção de caminhos.
- Quitação sem duplicação e despesas operacionais líquidas de estorno efetivamente recebido.
- Validação de CPF/CNPJ, custo médio e bloqueio de estoque negativo.
- Dados da loja preservados nos documentos da venda após mudança de configurações.
- Venda com troca enviada pelo fluxo HTTP real do Django.
- Criação de perfil vendedor, hash de senha e recusa de senha fraca.

`python manage.py check`: sem problemas.

`python manage.py makemigrations --check --dry-run`: sem alterações pendentes.

Instalação repetida por `sh scripts/install.sh`: concluída sem modificar registros comerciais ou arquivos de dependências.

## Navegador e servidor

Chromium real, banco separado em pasta temporária:

- Login; cadastro de contato; entrada com foto; venda Pix; resultado calculado; tela financeira.
- Documento de garantia renderizado e gerado como PDF.
- Envio de logo de teste e carregamento da imagem autenticada. A imagem usada não é a logo original da loja.
- Desktop 1440 px e celular 390 px: painel sem vazamento horizontal, menu móvel funcional e campos de troca habilitados apenas quando selecionados.
- Nenhum erro JavaScript nessa sequência.

Não foram testados fisicamente iPhone/Safari, impressora ou Windows neste ambiente Linux. Os documentos oferecem impressão/PDF pelo navegador; a forma final depende das opções de impressão do aparelho.

Servidor principal iniciado pelas instruções salvas: página de login HTTP 200. Banco principal verificado com zero usuários, contatos, aparelhos, acessórios, vendas e lançamentos; não há senha padrão.

## Backup e restauração

Com o servidor de QA parado, o comando de backup gerou ZIP. O comando de restauração carregou esse ZIP em outra pasta. Foram comparados registros comerciais, usuários, auditoria e conteúdo binário de todos os anexos: idênticos. Nenhum dado de QA foi misturado ao banco principal ou ao pacote de código.

## Modo produção local

Django com DEBUG=0, chave aleatória fora do código e Waitress em loopback:

- Página de login HTTP 200 com esquema HTTPS interno do proxy.
- Cookies Secure e cabeçalho HSTS presentes.
- `check --deploy`: dois avisos, W005 e W021, sobre HSTS em todos os subdomínios e preload. Essas opções dependem do domínio definitivo e permanecem desativadas por padrão; as demais verificações não apontaram problemas.

Não houve contratação, publicação, teste de domínio/TLS/Nginx em provedor nem teste de restauração de um novo ambiente da plataforma. A configuração de instalação/inicialização foi salva apenas como rascunho.

## Dependências externas e pendências

- Mercado Phone: URL solicitada retornou HTTP 403; o conteúdo não foi verificado.
- Logo original: visível na conversa, mas sem arquivo acessível no workspace. Deve ser enviada em Configurações.
- Taxas de cartão, dados da loja e termos precisam ser preenchidos/revisados pelo proprietário.
- NF-e/SEFAZ, IMEI/Apple, mensagens e assinatura digital: não integrados. OS, orçamentos, catálogo e CRM completos: não implementados.

## Atualização orientada pelo vídeo

Foram adicionados testes em `core/test_operations.py`, totalizando **47 testes automatizados**. Além dos fluxos iniciais, são verificados orçamento sem baixar estoque, conversão uma única vez, preço/validade revalidados, recusa de adulteração de itens, conversão HTTP, cálculo inverso de cartão, centavos das parcelas, avaliação com parâmetros preservados e piso zero, autorização/limite de OS, consumo de peças, retorno físico confirmado, entrega sem duplicar contas, custo de manutenção interna sem receita fictícia, bloqueio de liberação manual de aparelho em OS, custo médio de peças, caixa apenas com dinheiro, sangria com contrapartida, reembolso efetivo, fechamento preservado, tarefa local de pós-venda, conclusão com resultado, edição de preço sem alterar documento anterior, todas as telas/documentos/relatórios novos, CSV protegido contra fórmulas e permissões dos novos endpoints.

A análise visual do vídeo e o comparativo de escopo estão em `REFERENCIA-VIDEO.md`. Os limites da primeira versão descritos acima referentes a OS, orçamento e relatórios foram substituídos pelos módulos locais desta atualização; integrações externas continuam indisponíveis. O vídeo e registros de QA não fazem parte dos dados da loja ou do repositório.


Na validação desta atualização em Chromium real e banco isolado, passaram: orçamento → PDV → venda com pagamentos combinados, resumo em centavos, inclusão de linhas adicionais, recebimento físico no caixa, recebimento de OS → diagnóstico → autorização → peça → reparo → entrega, cálculo inverso de cartão, avaliação manual, agenda, relatórios e PDFs de orçamento/OS. As telas verificadas a 390px não apresentaram vazamento horizontal da página; tabelas e Kanban têm rolagem própria. Nenhum erro JavaScript ocorreu nessa sequência.

Foi restaurado um backup populado da versão inicial em diretório separado e aplicada a migração nova. Todos os valores das colunas originais foram comparados em todas as tabelas comerciais e de usuários: sem diferenças. `manage.py check`, verificação de migrações pendentes e `git diff --check` passaram. O banco principal permaneceu vazio, sem fixtures ou usuário de demonstração.

## Cadastro dentro da venda e nova interface

A suíte foi ampliada para **62 testes**. Os novos testes cobrem cadastro de cliente com CPF normalizado e canal de descoberta, seleção explícita de contato existente, dados inválidos sem persistência, entrada de aparelho e fornecedor com movimento/contas, proteção de IMEI/série e contra repetição, acessórios com custo/quantidade, recusa de estoque zero, cadastro seguido de venda com resultado correto e origem preservada, permanência dos cadastros quando a venda é inválida, permissões/CSRF/autoria das solicitações, diálogos e seleção por caixas, upload da marca, marca pública no acesso e manutenção da proteção dos demais anexos, além da recusa de imagem inválida sem substituir a marca existente.

No Chromium, com banco isolado, foi executada a sequência real: preencher observações/desconto/pagamento; cadastrar cliente com origem; tentar CPF duplicado e selecionar o existente; cadastrar aparelho, corrigir IMEI inválido sem fechar a janela, criar fornecedor, cadastrar acessório, incluir novas linhas e concluir a venda. Campos e seleções foram preservados; totais e resultado foram conferidos. Também foram verificados os diálogos e a página em 390px, e o envio de uma imagem técnica de marca com exibição no menu e login após sair. Nenhum erro JavaScript ocorreu. A imagem técnica não substitui a logo original e não é entregue como marca da loja.

Foi restaurado em diretório separado um backup populado da versão anterior e aplicada a migração 0003. Todas as colunas originais de todas as tabelas comerciais e usuários foram comparadas: sem diferenças. O banco principal continuou vazio. A página de referência visual voltou a responder HTTP 403; não foi afirmada reprodução exata do site.
