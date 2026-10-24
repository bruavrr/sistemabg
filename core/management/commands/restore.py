import sqlite3, zipfile, shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
class Command(BaseCommand):
    help='Restaura backup local. Exige servidor parado e --replace para substituir os dados atuais.'
    def add_arguments(self,parser):
        parser.add_argument('archive')
        parser.add_argument('--replace',action='store_true')
    def handle(self,*args,**options):
        if not options['replace']: raise CommandError('Faça backup do estado atual, pare o servidor e confirme com --replace.')
        archive=Path(options['archive']).resolve()
        if not archive.is_file(): raise CommandError('Arquivo não encontrado.')
        with TemporaryDirectory() as tmp:
            stage=Path(tmp)
            try:
                with zipfile.ZipFile(archive) as z:
                    for info in z.infolist():
                        p=Path(info.filename)
                        if p.is_absolute() or '..' in p.parts or not (info.filename=='bgstore.sqlite3' or (p.parts and p.parts[0]=='uploads')): raise CommandError('Backup contém caminho não permitido.')
                    z.extractall(stage)
                db=stage/'bgstore.sqlite3'
                if not db.is_file(): raise CommandError('Backup sem banco de dados.')
                with sqlite3.connect(db) as conn:
                    if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise CommandError('Banco corrompido.')
                    conn.execute('SELECT id FROM core_sale LIMIT 1')
                    conn.execute('SELECT id FROM auth_user LIMIT 1')
            except (zipfile.BadZipFile,sqlite3.DatabaseError) as e: raise CommandError(f'Backup inválido: {e}')
            connections.close_all()
            destination=settings.DATA_DIR
            incoming=destination/'uploads'
            if incoming.exists(): shutil.rmtree(incoming)
            if (stage/'uploads').exists(): shutil.copytree(stage/'uploads',incoming)
            shutil.copy2(db,destination/'bgstore.sqlite3')
            for suffix in ('-wal','-shm'):
                (destination/('bgstore.sqlite3'+suffix)).unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS('Backup restaurado. Execute migrate, check e depois inicie o servidor.'))
