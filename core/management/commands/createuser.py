import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from core.services import audit
class Command(BaseCommand):
    help='Cria usuário sem senha padrão. Administrador: --role admin; vendedor: --role seller.'
    def add_arguments(self,parser):
        parser.add_argument('username')
        parser.add_argument('--role',choices=['admin','seller'],default='seller')
    def handle(self,*args,**options):
        User=get_user_model()
        if User.objects.filter(username=options['username']).exists(): raise CommandError('Este usuário já existe.')
        user=User(username=options['username'],is_staff=options['role']=='admin',is_superuser=options['role']=='admin')
        password=getpass.getpass('Senha (não aparece ao digitar): ')
        if password!=getpass.getpass('Repita a senha: '): raise CommandError('Senhas diferentes.')
        try: validate_password(password,user)
        except ValidationError as e: raise CommandError(' '.join(e.messages))
        user.set_password(password); user.save()
        audit(user,'Usuário criado',user,{'perfil':options['role']})
        self.stdout.write(self.style.SUCCESS(f'Usuário {user.username} criado como {options["role"]}.'))
