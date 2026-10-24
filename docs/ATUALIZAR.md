# Atualizar a BG Store que já está no seu computador

Esta atualização acrescenta orçamentos, resumo de PDV, OS/peças, caixa físico, agenda, relatórios e simuladores. É preciso atualizar os arquivos **e aplicar a migração do banco**; apenas recarregar o navegador não instala a versão nova.

## Mac — versão baixada por ZIP

1. No terminal onde o sistema está ligado, pressione **Control+C** para desligar.
2. Na pasta antiga, faça backup:

```sh
.venv/bin/python manage.py backup
```

3. Guarde o ZIP de backup fora da pasta do programa. A pasta `data` também precisa ser preservada: contém seus usuários, registros e anexos.
4. No GitHub, abra https://github.com/bruavrr/sistemabg e escolha **Code → Download ZIP**. Extraia em uma **pasta nova**.
5. Antes de iniciar essa nova cópia, copie **a pasta `data` inteira da instalação antiga para a pasta nova**, no mesmo nível do `manage.py`. Se você nunca chegou a cadastrar usuário ou registro, pode iniciar vazio e criar o administrador como no guia inicial. Não apague a pasta antiga até conferir tudo.
6. Abra a nova pasta no VS Code e escolha **Terminal → Novo Terminal**. Execute um comando por vez:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8010
```

7. No navegador do seu computador, digite `http://127.0.0.1:8010`. Se copiou `data`, seu usuário e senha continuam os mesmos. O terminal precisa ficar aberto. Se iniciou vazio, crie antes o administrador conforme `COMECE-AQUI.md`.
8. Confira seus registros antigos e os novos menus. Movimentos anteriores não são inventados ou inseridos em caixas físicos novos. Lançamentos antigos cujo meio efetivo não estava registrado aparecem como “Não informado”.

## Se usa Git

Pare o servidor, faça backup e preserve alterações locais. Com a árvore limpa e na branch `main`, execute `git pull --ff-only`, instale `requirements.lock`, aplique `manage.py migrate`, execute `manage.py check` e reinicie. Não use reset ou apague `data` para resolver atualização.

## Windows

Siga os mesmos passos de preservação e nova pasta. Nos comandos, use `py -3.12 -m venv .venv` na criação e `.\.venv\Scripts\python.exe` no lugar de `.venv/bin/python`.

## Depois de atualizar

- Configure as taxas reais de cartão e as tabelas de avaliação antes de usar os simuladores.
- Em Configurações, “Dias para lembrete local de pós-venda” permanece em zero até você ativar. Configurar dias cria tarefas na agenda nas novas vendas; não envia mensagens.
- Abra um caixa físico com o dinheiro que você realmente contou antes de registrar novas vendas em dinheiro.
- Aplique os fluxos de aprovação e estoque na OS; manutenção interna e serviço ao cliente têm tratamento financeiro distinto.
- A atualização não configura integração fiscal, mensagens, Apple, IMEI ou assinatura digital.
