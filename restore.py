#!/usr/bin/env python3
"""Verifica/restaura o snapshot Linux do one sem sobrescrever dados sem backup."""
from pathlib import Path, PurePosixPath
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile


REPO = Path(__file__).resolve().parent


def verify(record):
    whole = hashlib.sha256()
    for part in record['parts']:
        path = REPO / part['file']
        digest = hashlib.sha256()
        size = 0
        with path.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                whole.update(chunk)
                size += len(chunk)
        if digest.hexdigest() != part['sha256'] or size != part['size']:
            raise ValueError(f'Arquivo incompleto ou alterado: {path}')
    if whole.hexdigest() != record['sha256']:
        raise ValueError(f'Checksum do conjunto invalido: {record["group"]}')
    print('SHA256 OK:', record['group'], flush=True)


def join_archive(record, target):
    with target.open('wb') as destination:
        for part in record['parts']:
            with (REPO / part['file']).open('rb') as source:
                shutil.copyfileobj(source, destination)


def checked_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError(f'Caminho invalido no backup: {name}')
    if path.parts[0] not in ('home', 'system', 'sources'):
        raise ValueError(f'Raiz invalida no backup: {name}')
    return path


def stage_archive(archive, staging, original_home, target_home):
    members = []
    with tarfile.open(archive, 'r:gz') as tar:
        for entry in tar:
            relative = checked_name(entry.name)
            target = staging.joinpath(*relative.parts)
            # Never write through a symbolic link from an earlier archive member.
            for parent in target.parents:
                if parent == staging:
                    break
                if parent.is_symlink():
                    raise ValueError(f'Membro atravessa link simbolico: {entry.name}')
            target.parent.mkdir(parents=True, exist_ok=True)
            if entry.isdir():
                target.mkdir(exist_ok=True)
            elif entry.issym():
                link = entry.linkname
                if link == original_home or link.startswith(original_home + '/'):
                    link = str(target_home) + link[len(original_home):]
                if target.exists() or target.is_symlink():
                    raise ValueError(f'Membro duplicado: {entry.name}')
                target.symlink_to(link)
            elif entry.isfile() or entry.islnk():
                if entry.islnk():
                    checked_name(entry.linkname)
                source = tar.extractfile(entry)
                if source is None:
                    raise ValueError(f'Conteudo ausente: {entry.name}')
                # Home references are adapted only in UTF-8 text, never binaries.
                if entry.size < 4 * 1024 * 1024:
                    data = source.read()
                    try:
                        if b'\0' not in data:
                            text = data.decode('utf-8')
                            data = text.replace(original_home, str(target_home)).encode('utf-8')
                    except UnicodeError:
                        pass
                    target.write_bytes(data)
                else:
                    with target.open('wb') as output:
                        shutil.copyfileobj(source, output)
            else:
                raise ValueError(f'Tipo nao permitido no backup: {entry.name}')
            if not entry.issym():
                target.chmod(entry.mode & 0o777)
            members.append((relative, entry.isdir(), entry.issym(), entry.mode & 0o777))
    return members


def exists(path):
    return path.exists() or path.is_symlink()


def install_home(staged, target, backup, directory, symlink, mode):
    if directory and target.is_dir() and not target.is_symlink():
        return
    if exists(target):
        if not symlink and not directory and target.is_file() and not target.is_symlink():
            if target.read_bytes() == staged.read_bytes() and (target.stat().st_mode & 0o777) == mode:
                return
        if exists(backup):
            raise ValueError(f'Colisao no diretorio de backup: {backup}')
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(backup))
    target.parent.mkdir(parents=True, exist_ok=True)
    if directory:
        target.mkdir(mode=mode)
    elif symlink:
        target.symlink_to(staged.readlink())
    else:
        shutil.copy2(staged, target)


def install_system(staged, relative, stamp, directory, symlink, mode):
    target = Path('/').joinpath(*relative.parts[1:])
    backup = Path('/var/backups') / ('one-desktops-' + stamp) / target.relative_to('/')
    if directory:
        subprocess.run(['sudo', 'install', '-d', '-m', f'{mode:o}', str(target)], check=True)
        return
    subprocess.run(['sudo', 'install', '-d', str(target.parent)], check=True)
    if exists(target):
        subprocess.run(['sudo', 'install', '-d', str(backup.parent)], check=True)
        subprocess.run(['sudo', 'mv', '--', str(target), str(backup)], check=True)
    if symlink:
        subprocess.run(['sudo', 'ln', '-s', '--', str(staged.readlink()), str(target)], check=True)
    else:
        subprocess.run(['sudo', 'install', '-m', f'{mode:o}', str(staged), str(target)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Verificar checksums (padrao; nao instala)')
    parser.add_argument('--apply', action='store_true', help='Restaurar arquivos do usuario com backup das colisoes')
    parser.add_argument('--system', action='store_true', help='Tambem restaurar entradas de sessao e wrappers usando sudo')
    parser.add_argument('--home', type=Path, default=Path.home(), help='Home de destino (padrao: usuario atual)')
    parser.add_argument('--group', action='append', help='Restaurar/verificar somente este grupo; pode repetir')
    args = parser.parse_args()
    if args.verify and args.apply:
        parser.error('Use --verify ou --apply, nao ambos.')
    if args.system and not args.apply:
        parser.error('--system exige --apply.')
    if args.apply and os.name != 'posix':
        parser.error('A restauracao exige Linux; --verify funciona tambem no Windows.')
    manifest = json.loads((REPO / 'manifest.json').read_text(encoding='utf-8'))
    records = [item for item in manifest['archives'] if not args.group or item['group'] in args.group]
    unknown = set(args.group or ()) - {item['group'] for item in records}
    if unknown:
        parser.error('Grupos desconhecidos: ' + ', '.join(sorted(unknown)))
    for record in records:
        verify(record)
    if not args.apply:
        print('Backup integro. Nenhum arquivo instalado.')
        return
    target_home = args.home.expanduser().resolve()
    target_home.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup_root = target_home / '.local/state' / ('one-restore-backup-' + stamp)
    if args.system:
        subprocess.run(['sudo', '-v'], check=True)
    installed = 0
    with tempfile.TemporaryDirectory(prefix='one-restore-') as temp:
        temporary = Path(temp)
        staging = temporary / 'staging'
        staging.mkdir()
        members = []
        for record in records:
            archive = temporary / 'current.tar.gz'
            join_archive(record, archive)
            members.extend(stage_archive(archive, staging, manifest['source_home'], target_home))
            archive.unlink()
        # Parents precede children. Existing unrelated files/directories are preserved.
        seen = set()
        for relative, directory, symlink, mode in sorted(members, key=lambda item: (len(item[0].parts), str(item[0]))):
            if str(relative) in seen:
                continue
            seen.add(str(relative))
            prefix = relative.parts[0]
            if prefix == 'system':
                if args.system and len(relative.parts) > 1:
                    install_system(staging.joinpath(*relative.parts), relative, stamp, directory, symlink, mode)
                continue
            tail = relative.parts[1:]
            if not tail:
                continue
            if prefix == 'sources':
                tail = ('.local', 'share', 'one-backup-sources', *tail)
            target = target_home.joinpath(*tail)
            backup = backup_root.joinpath(*tail)
            install_home(staging.joinpath(*relative.parts), target, backup, directory, symlink, mode)
            installed += 1
    print(f'Restauracao concluida: {installed} entradas em {target_home}')
    print(f'Arquivos anteriores preservados em: {backup_root}')
    print('Servicos e sessoes nao foram iniciados. Confira monitores/dependencias antes do login.')


if __name__ == '__main__':
    main()
