# Como abrir a BG Store no seu computador

Você abre o sistema no navegador, mas precisa deixar um pequeno servidor rodando no computador. Os dados ficam gravados em um arquivo de banco, não no navegador. Não precisa contratar hospedagem para usar localmente.

## 1. Baixe os arquivos

No GitHub, abra https://github.com/bruavrr/sistemabg, clique em **Code → Download ZIP** e escolha **Extrair tudo** após baixar. Guarde a pasta em um local seu, por exemplo `C:\BGStore` no Windows. Não execute de dentro do ZIP. A pasta correta contém `manage.py`, `requirements.lock`, `core` e `bgstore`.

O código fica disponível no repositório `bruavrr/sistemabg`. O ZIP contém o código; o banco vazio é criado na preparação descrita abaixo.

## 2. Instale o Python

Instale o Python **3.12** pelo site oficial https://www.python.org/downloads/. No Windows, marque **Add python.exe to PATH**. Feche e reabra o terminal após instalar.

## 3. Abra o terminal na pasta

Windows: abra a pasta extraída no Explorador, clique na barra de endereço, digite `powershell` e aperte Enter. Não precisa executar como administrador.

macOS: abra o Terminal, digite `cd ` (com espaço), arraste a pasta BGStore para o Terminal e aperte Enter.

## 4. Prepare o sistema — só na primeira vez

**Windows (PowerShell):** execute uma linha de cada vez e aguarde terminar:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createuser seuusuario --role admin
```

Troque `seuusuario` pelo nome que você deseja. O programa pede a senha duas vezes. **Nada aparece enquanto você digita a senha; isso é normal.** Use senha forte com pelo menos oito caracteres. Não há senha padrão. Você não precisa ativar o ambiente virtual nem mudar a política de execução do Windows.

**macOS / Linux:**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createuser seuusuario --role admin
```

Se Linux informar que o módulo venv está ausente, instale o pacote `python3-venv` pelo gerenciador da sua distribuição e repita a primeira linha.

## 5. Ligue e abra

Windows:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

macOS / Linux:

```sh
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

No **seu computador**, abra o navegador e digite `http://127.0.0.1:8000`. Entre com o usuário e senha que criou. Este é um endereço local para uso no seu computador, não um site publicado pela conversa.

Deixe o terminal aberto. Para desligar, volte ao terminal e aperte **Ctrl+C**. Seus registros permanecem salvos. Nos próximos dias, repita apenas este passo para ligar; não precisa reinstalar ou criar o usuário novamente.

## 6. Configure a loja e use na ordem

1. Em **Configurações**, preencha os dados reais da BG Store e envie a logo original anexada à conversa, salva no computador em PNG/JPG. Revise a minuta dos termos antes de imprimir para clientes.
2. Cadastre clientes e fornecedores em **Clientes e fornecedores**. CPF/CNPJ é opcional; quando preenchido, os dígitos são validados e duplicidades bloqueadas.
3. Cadastre as taxas reais das maquininhas nas Configurações antes de aceitar cartão. Informe taxa, parcelas e intervalo em dias entre recebimentos previstos. Os recebimentos não são conciliados automaticamente.
4. Registre **Entrada de aparelho**. Confira IMEI, série e valores, faça o checklist e anexe fotos/nota de origem quando houver. Imprima o comprovante interno. A compra gera conta a pagar, não pagamento automático.
5. Cadastre acessórios e suas quantidades reais. Só administradores cadastram/repoem acessórios ou conciliam o financeiro.
6. Em **Nova venda**, selecione o cliente, os produtos, o desconto e os pagamentos. Marque as caixas dos aparelhos que deseja incluir. Você também pode cadastrar o cliente, aparelho e acessório pelos botões da própria venda. Em troca, marque a opção e preencha o aparelho recebido; a origem deve ser o cliente da venda. Informe a avaliação como custo de aquisição. A soma dos pagamentos precisa ser total da venda menos avaliação.
7. Ao concluir, abra o comprovante e o termo de garantia. Clique em **Imprimir / salvar em PDF**; na janela do navegador, selecione a impressora ou **Salvar como PDF**. São documentos internos, não notas fiscais.
8. No **Financeiro**, quite as compras realmente pagas e os cartões realmente recebidos. Pix e dinheiro entram no caixa na venda. Não crie outra despesa para uma compra já lançada.
9. Cadastre vencimento Apple apenas com informação real e sua fonte. Garantias de seminovos são calculadas por nove meses de calendário. Atendimentos ficam na ficha da garantia.

## 7. Crie um vendedor

Pare o servidor com Ctrl+C e execute, trocando o nome:

```powershell
.\.venv\Scripts\python.exe manage.py createuser vendedor --role seller
```

No macOS/Linux use `.venv/bin/python`. Ligue o servidor novamente. O vendedor opera contatos, aparelhos, vendas e atendimentos; não altera configurações, não cancela vendas, não quita contas e não exporta os dados. Ele vê preços e resultados das vendas para operar a loja; os indicadores financeiros globais do painel e o módulo Financeiro ficam com administradores.

O administrador inicial é superusuário e também pode gerenciar usuários em Configurações → Gerenciar usuários. Ao criar vendedor por essa tela, deixe desmarcados **Equipe** e **Superusuário**. Usuário de equipe com permissões específicas é um recurso avançado do Django; nesta versão o perfil administrativo da aplicação é definido pela marcação Equipe (`is_staff`).

## 8. Faça backup

Antes de atualizar o sistema e diariamente após encerrar o expediente, siga [BACKUP.md](BACKUP.md). Copiar apenas o código ou exportar JSON não preserva todos os dados e anexos.

## Acesso pelo celular na mesma rede

O computador precisa estar ligado e ambos devem estar no mesmo Wi-Fi. Descubra o IPv4 do computador (`ipconfig` no Windows). Exemplo: se ele for `192.168.1.20`, no mesmo PowerShell:

```powershell
$env:BG_ALLOWED_HOSTS="localhost,127.0.0.1,192.168.1.20"
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

No celular, digite `http://192.168.1.20:8000`. Substitua pelo IP real. Se o Windows perguntar sobre firewall, permita apenas a rede privada que você controla. Use esta modalidade somente para desenvolvimento em rede confiável: ela usa HTTP. Para acesso pela internet e operação comercial com HTTPS, siga o guia de hospedagem. Não abra portas do roteador para o runserver.

## Se algo der errado

- `py não reconhecido`: instale Python com PATH, reabra o terminal; tente `python --version`.
- `manage.py não encontrado`: o terminal está na pasta errada. Volte à pasta que contém `manage.py`.
- `No module named django`: execute a instalação usando o Python dentro de `.venv` mostrado acima.
- `no such table`: pare o servidor e execute `manage.py migrate` com o mesmo Python.
- `Port already in use`: outro servidor está ligado. Pare-o ou use `127.0.0.1:8002` e abra essa porta no navegador.
- Esqueceu a senha? Pare o servidor e execute `manage.py changepassword seuusuario` com o Python da `.venv`. Não apague o banco.
- Cinco senhas incorretas bloqueiam o usuário por 15 minutos. Aguarde o prazo.
- O sistema não fica acessível com o computador desligado. Hospedagem é uma etapa separada.
