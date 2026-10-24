# Preparar hospedagem — sem publicação automática

Este projeto não contratou serviços, não publicou um site e não configurou domínio. As instruções abaixo são uma proposta para um servidor Linux único com disco persistente, HTTPS e backup. Uma pessoa responsável pela hospedagem deve ajustar domínio, caminhos e permissões reais.

## Requisitos

- Python 3.12, ambiente virtual, Nginx, domínio apontado para o servidor e certificado TLS válido.
- Usuário de sistema sem privilégios, por exemplo `bgstore`, dono do banco e dos anexos.
- Código em `/srv/bgstore`; diretório persistente de dados em `/var/lib/bgstore`; backups fora desses diretórios.
- Uma única instância com SQLite. Não use disco temporário de plataforma serverless. Para várias instâncias, implemente e valide a migração para PostgreSQL e armazenamento privado dos anexos.
- Rede: instalação usa `pypi.org` e `files.pythonhosted.org`. Não há APIs externas necessárias para a operação implementada.

## Configuração e instalação

No usuário da aplicação, crie o venv, instale o lock e execute as migrações. Configure variáveis no gerenciador de segredos do provedor ou em `/etc/bgstore.env` com permissão 600 (fora do repositório):

```ini
BG_DEBUG=0
BG_SECRET_KEY=SUBSTITUA_POR_CHAVE_ALEATORIA_FORTE
BG_ALLOWED_HOSTS=loja.seu-dominio.com.br
BG_DATA_DIR=/var/lib/bgstore
```

Gere a chave com `python -c "import secrets; print(secrets.token_urlsafe(64))"` no servidor e guarde-a apenas no armazenamento seguro. Não use o texto de exemplo. A aplicação recusa produção sem chave. Não use DEBUG=1 em hospedagem pública. `.env` não é lido automaticamente.

Carregue as variáveis no processo de instalação de forma segura; em um shell administrativo controlado, um EnvironmentFile compatível pode ser carregado com `set -a; . /etc/bgstore.env; set +a`. Não imprima o ambiente nem coloque segredos em comandos compartilhados.

```sh
cd /srv/bgstore
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy
.venv/bin/python manage.py createuser seuadministrador --role admin
```

O `check --deploy` pode apontar W005 e W021: a aplicação não força HSTS em todos os subdomínios nem solicita preload por padrão. São decisões do domínio real, não devem ser ativadas antes de garantir HTTPS permanente em todos os subdomínios. O teste local apresentou exatamente esses dois avisos; nenhuma falha nas demais verificações de segurança Django.

## Processo da aplicação

Exemplo de `/etc/systemd/system/bgstore.service`:

```ini
[Unit]
Description=BG Store
After=network.target

[Service]
User=bgstore
Group=bgstore
WorkingDirectory=/srv/bgstore
EnvironmentFile=/etc/bgstore.env
ExecStart=/srv/bgstore/.venv/bin/waitress-serve --listen=127.0.0.1:8000 --threads=2 --url-scheme=https --max-request-body-size=20971520 bgstore.wsgi:application
Restart=on-failure
UMask=0077
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

`--url-scheme=https` é apropriado **somente** com acesso externo exclusivamente pelo Nginx HTTPS abaixo e Waitress escutando em loopback. O Django não depende de cabeçalho Forwarded enviado pelo visitante. Não exponha a porta 8000 na internet. O modo de produção usa cookies Secure e redirecionamento HTTPS.

## Nginx

Modelo a adaptar após obter certificado real; os caminhos de certificado abaixo são exemplos de instalação Let's Encrypt, não arquivos entregues pelo projeto:

```nginx
server {
    listen 80;
    server_name loja.seu-dominio.com.br;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;
    server_name loja.seu-dominio.com.br;
    ssl_certificate /etc/letsencrypt/live/loja.seu-dominio.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/loja.seu-dominio.com.br/privkey.pem;
    client_max_body_size 20m;
    location /static/ {
        alias /srv/bgstore/staticfiles/;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Não crie um alias público para `data/` nem para os anexos: a rota `/arquivos/` exige login e serve arquivos pelo Django. O Nginx precisa ler apenas `staticfiles/`. Deixe o código legível pelo serviço; somente os diretórios de dados precisam ser graváveis. Use renovação automática do certificado e monitore sua validade.

Após revisão do operador: `nginx -t`, recarregar Nginx, `systemctl daemon-reload`, habilitar e iniciar `bgstore`. Estas ações não foram executadas neste ambiente.

## Validar e operar

1. Acesse o domínio HTTPS e faça login. Verifique estilo, anexos, permissões e impressão.
2. Cadastre dados reais da loja e logo. Revise os termos de garantia antes do uso e providencie emissão fiscal por sistema autorizado separado enquanto não houver integração.
3. Agende backup diário com o serviço parado durante o comando; copie o ZIP para armazenamento protegido fora do servidor. Teste restauração periodicamente em instância isolada. Configure retenção conforme a operação e obrigações aplicáveis.
4. Mantenha Python/Django/dependências atualizados com revisão e testes. Antes de cada atualização, faça backup; instale o lock, aplique migrações, rode testes e reinicie o processo. A reversão de código pode exigir restaurar o banco do backup anterior se as migrações forem incompatíveis.
5. Monitore logs de erro, uso de disco, disponibilidade e resultado dos backups. Não registre senhas, documentos ou conteúdo de arquivos nos logs de proxy.

O teste local em modo produção confirma somente o processo HTTP e configurações Django; não confirma DNS, TLS, Nginx ou disponibilidade de um provedor ainda não contratado.
