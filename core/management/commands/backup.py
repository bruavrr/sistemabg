import sqlite3, zipfile
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
class Command(BaseCommand):
    help='Backup do SQLite e anexos. Pare o servidor antes para consistência entre arquivos e banco.'
    def add_arguments(self,parser): parser.add_argument('--output',default='backups')
    def handle(self,*args,**options):
        out=Path(options['output']).resolve(); out.mkdir(parents=True,exist_ok=True)
        if out.is_relative_to(settings.DATA_DIR.resolve()): raise CommandError('O destino deve ficar fora da pasta data.')
        target=out / ('bgstore-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.zip')
        connection.ensure_connection()
        with TemporaryDirectory() as tmp:
            db=Path(tmp)/'bgstore.sqlite3'
            with sqlite3.connect(db) as dest: connection.connection.backup(dest)
            with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
                archive.write(db,'bgstore.sqlite3')
                uploads=settings.DATA_DIR/'uploads'
                if uploads.exists():
                    for f in uploads.rglob('*'):
                        if f.is_file() and not f.is_symlink(): archive.write(f,str(f.relative_to(settings.DATA_DIR)))
        target.chmod(0o600)
        self.stdout.write(self.style.SUCCESS(f'Backup criado: {target}. Contém dados pessoais; guarde em local protegido.'))
