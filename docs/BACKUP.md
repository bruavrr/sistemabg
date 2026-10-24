# Backup e restauração

## O que deve ser protegido

A pasta `data/` contém SQLite e anexos. O ZIP de backup inclui o banco com usuários (hashes de senha) e os arquivos enviados, inclusive fotos e termos assinados. Contém dados pessoais e deve ficar protegido e com acesso restrito. Guarde uma cópia em outro dispositivo ou serviço seguro; a cópia no mesmo disco não protege de falha física. Não envie backups a um repositório público.

A exportação JSON da interface inclui os registros comerciais, mas não inclui arquivos anexos nem usuários/senhas. É para consulta/interoperabilidade; **não existe importador JSON nesta versão**. Para recuperar o sistema inteiro, use o ZIP de backup.

## Criar backup

1. Pare o servidor com Ctrl+C. Na hospedagem, pare o serviço. Isso impede que uma foto/documento seja anexado enquanto o banco é copiado.
2. Na pasta do projeto, execute no Windows:

```powershell
.\.venv\Scripts\python.exe manage.py backup
```

macOS/Linux:

```sh
.venv/bin/python manage.py backup
```

3. O comando informa o arquivo em `backups/bgstore-....zip`. Leve uma cópia para outro local protegido. Se desejar escolher a pasta:

```powershell
.\.venv\Scripts\python.exe manage.py backup --output "D:\BackupsBGStore"
```

4. Ligue o servidor novamente. A rotina usa a API de backup do SQLite, sem copiar um arquivo de banco aberto de forma insegura. O servidor deve estar parado para garantir consistência com os anexos.

Em produção, proteja também a variável `BG_SECRET_KEY` no gerenciador de segredos do provedor; ela não vai para o ZIP. A chave local de desenvolvimento pode ser recriada (isso encerra sessões existentes).

## Restaurar

1. Pare o servidor e faça backup do estado atual antes de substituir qualquer dado.
2. Use a **mesma versão do código** que criou o backup, ou uma versão posterior com migrações compatíveis. Não restaure um banco recente em código antigo.
3. Guarde o ZIP fora da pasta `data`.
4. Execute no Windows, substituindo o nome do arquivo:

```powershell
.\.venv\Scripts\python.exe manage.py restore "backups\bgstore-SEU-ARQUIVO.zip" --replace
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
```

No macOS/Linux, use `.venv/bin/python` e caminhos com `/`.

5. Ligue o servidor, entre com um usuário do backup e confira contatos, estoque, uma venda e um anexo. A restauração substitui os dados e anexos atuais; não mescla dois bancos.

O comando rejeita caminhos de arquivo externos à estrutura permitida e verifica a integridade SQLite antes da substituição. Execute somente backups de origem confiável, em máquina com espaço livre. Uma falha de disco durante substituição pode exigir nova restauração; por isso mantenha o backup anterior e não faça a operação com o servidor ligado.
