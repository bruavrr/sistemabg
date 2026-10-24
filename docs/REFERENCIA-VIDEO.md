# Referência funcional em vídeo — BG Store

Material fornecido pelo proprietário: vídeo de apresentação “O Melhor sistema para lojas de Smartphones”, identificador YouTube `fNa-Fyh4Azk`. Arquivo em 720p, duração aproximada de 8min34s. O arquivo foi lido localmente; quadros foram extraídos ao longo de toda a apresentação e telas relevantes examinadas em maior resolução. A análise é **visual**, sem transcrição do áudio. O vídeo e suas capturas não são distribuídos no repositório.

A referência orienta funcionalidades. Marca, cores, textos comerciais e dados demonstrativos do outro sistema não foram copiados. Os dados usados em testes são isolados do banco da loja. Uma tela ou item de menu não comprova todas as suas regras internas, integrações ou condições comerciais.

## Comparativo visual e implementação

Tempos aproximados dos trechos examinados:

| Trecho | O que aparece | BG Store |
| --- | --- | --- |
| 0:10 | Painel com período, faturamento, lucro, entradas e saídas | Painel por período com vendas e resultado, despesas, saldo financeiro, estoque, alertas e serviços entregues. Faturamento, resultado e caixa diferenciados. |
| 0:30–1:50 | Estoque individual, cadastro de aparelho, IMEIs, custos, estado e ações | Entrada e ficha individual, IMEIs únicos, checklist, anexos, status, comprovante, edição de preço/inspeção com auditoria e etiqueta imprimível. |
| 2:10 | Histórico de vendas | Lista com documentos, cancelamento administrativo, estoque e estornos preservados. |
| 2:30–3:50 | PDV com produtos, pagamentos, saldo, aparelho recebido em troca e canal | Resumo imediato em centavos, vários produtos, acessórios, desconto, pagamentos combinados, cartão por taxa cadastrada e troca vinculada. Canal é cadastro manual, sem integração social. |
| 4:10–4:30 | Documento de venda/garantia e ações da venda | Comprovante interno e garantia separados, dados da venda preservados e impressão/PDF. Não foram copiadas as cláusulas contratuais do vídeo. |
| 4:50 | Listagem de orçamentos | Propostas com validade e status, impressão e conversão em venda transacional. A conversão é uma implementação própria da BG Store; o vídeo não detalha suas regras. |
| 5:10 | Tabela de avaliação por modelo/GB e descontos por bateria, tela e detalhes | Tabela configurável, simulações salvas com parâmetros preservados, piso zero e preenchimento inicial de uma troca. Sem pesquisa de mercado ou consulta externa. |
| 5:30 | Dashboard de OS e menu com lista/Kanban/peças | Lista/Kanban, recebimento, diagnóstico, aprovação real registrada, limite autorizado, peças, etapas, histórico, impressão e cobrança pendente na entrega. Manutenção interna separada da assistência ao cliente. As transições são regras próprias documentadas abaixo. |
| 5:50 | Menus financeiro, pagar/receber e movimentos | Contas com filtros, quitação pelo meio efetivo, vínculo à venda/OS/caixa e estornos sem excluir registros. Sem movimentação bancária real. |
| 6:10 | Abertura/fechamento de caixa | Caixa físico único aberto, contagem inicial/final, diferença e movimentos; sangria/reforço com contrapartida, sem receita/despesa fictícia. |
| 6:30–6:50 | Agenda semanal | Agenda local com contatos, venda/OS, pendências, conclusão registrada e aniversariantes. Sem sincronização externa ou envio de mensagens. |
| 7:10–7:30 | Relatórios e filtros | Seis relatórios operacionais: vendas, estoque, pagamentos/taxas, clientes, OS e financeiro. CSV protegido contra fórmulas em textos e impressão/PDF. Não é DRE fiscal, consolidado multiloja ou implementação de todos os relatórios do menu. |
| 7:50–8:30 | Listagem de automações com gatilhos, menus de campanha/CRM/catálogo/API | Lembretes locais de pós-venda podem ser criados por venda. Mensagens, campanhas, API pública, CRM com funil, programa de indicação, cashback, catálogo online e automação externa não estão implementados. O vídeo não demonstra o fluxo completo desses menus. |

Também há simulador de cartão usando taxas reais cadastradas. O acesso a NF-e/SEFAZ, Apple/IMEI, WhatsApp/Instagram e assinatura digital continua indisponível até existir integração real. Não há botões que anunciem sucesso desses serviços.

## Regras operacionais adotadas

### Orçamentos

Não reservam estoque nem geram financeiro. Os itens, valores e dados das partes ficam registrados na proposta. Orçamento vencido/cancelado não é convertido. Na conversão, cliente, itens, quantidades, desconto, disponibilidade e preços devem corresponder; preço alterado exige nova proposta. Uma proposta gera no máximo uma venda. Uma venda cancelada continua vinculada à proposta original; não a convertemos novamente sem uma nova proposta.

### Assistência e peças

Etapas: recebida → diagnóstico → aguardando aprovação → aprovada → reparo → pronta → entregue. Pode cancelar antes da entrega; “pronta” pode voltar para reparo. Somente administradores atualizam execução/valores, aplicam peças e registram etapas; vendedores podem receber e consultar OS.

Aprovação exige texto de autorização real (data/meio/escopo) e limite. Aplicar peças não pode ultrapassar o limite. “Pronta” exige serviço executado descrito. A entrega é idempotente e cria contas pendentes, sem confirmar recebimento. A assistência ao cliente não altera o estoque de aparelhos vendidos; peças são baixadas do estoque de assistência.

Se a OS vincula aparelho do estoque, trata-se de manutenção interna: ele fica indisponível em manutenção. Na conclusão, peças a custo e custo de mão de obra são incorporados ao aparelho. Não há receita ou conta a receber fictícia. A mão de obra gera conta a pagar; a compra das peças já tem seu próprio lançamento. O estoque é liberado ao encerrar. Para cancelar com peças aplicadas, o operador precisa confirmar seu retorno físico em condição de estoque; peças danificadas/usadas exigem regularização antes do cancelamento. Não há devolução/cancelamento de OS entregue ou assinatura digital de aprovação nesta versão.

### Dinheiro físico e financeiro

O saldo global do painel é a soma de movimentos financeiros quitados. A gaveta do caixa físico é outra medida: fundo contado na abertura mais movimentos efetivos em dinheiro vinculados enquanto está aberto. Pix, banco e cartão não alteram a gaveta. A contagem de abertura não é receita. Movimentos anteriores ao caixa não são vinculados retroativamente.

Uma sangria ou reforço lança dois movimentos opostos (caixa e banco), resultando em zero no saldo global. Nenhuma transferência é executada no banco. O fechamento preserva esperado, contado e diferença; não cria ajuste artificial para esconder divergências. Um reembolso de venda afeta a gaveta apenas quando quitado efetivamente em dinheiro.

### Agenda e pós-venda

Por padrão, o lembrete automático está desativado (`0` dias). Quando configurado, uma venda gera uma tarefa local futura; repetir a mesma solicitação não duplica a tarefa. Cancelar a venda cancela as tarefas pendentes vinculadas, preservando o histórico. Tarefas concluídas exigem resultado do atendimento. Aniversário é um campo opcional e não dispara mensagem.

### Relatórios

Resultados de vendas excluem cancelamentos, que permanecem no histórico. Serviços entregues ao cliente são separados de manutenção interna e de vendas de aparelhos. O estoque é posição atual, incluindo peças, e independe do período. Financeiro permite ver vencimentos e fluxo por data efetiva; não é contabilidade fiscal. As listagens operacionais têm limites de exibição, mas o relatório/CSV inclui todos os registros filtrados.
