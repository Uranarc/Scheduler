"""Exporta membros/eventos/atribuições para JSON e envia (git commit+push)
para o repositório, de onde o GitHub Action de notificações WhatsApp o lê.

Assume que esta app corre dentro de um clone local do próprio repositório
Scheduler (media_scheduler/ é uma subpasta), e que esse clone já tem
permissão de push configurada (SSH key ou credenciais guardadas).
"""
import json
import subprocess
from pathlib import Path

from media_scheduler.db.members import list_members_db
from media_scheduler.db.events import list_events_db
from media_scheduler.db.assignments import list_assignments_db

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../Scheduler
EXPORT_PATH = REPO_ROOT / 'schedule_data.json'


def _zone_key(zone: str) -> str:
    return (zone or '').strip().lower()


def build_payload() -> dict:
    members = [
        {'id': m['id'], 'name': m['name'], 'phone': m['phone'] or ''}
        for m in list_members_db()
    ]
    events = [
        {'id': e['id'], 'name': e['name'] or '', 'date': e['date']}
        for e in list_events_db()
    ]
    assignments = [
        {'event_id': a['evid'], 'zone': _zone_key(a['zone']), 'member_id': a['mid']}
        for a in list_assignments_db()
    ]
    return {'members': members, 'events': events, 'assignments': assignments}


def export_schedule_json() -> Path:
    payload = build_payload()
    EXPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return EXPORT_PATH


def _run_git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ['git', *args], cwd=str(REPO_ROOT), capture_output=True, text=True
    )


def sync_and_push() -> str:
    """Exporta a escala e faz commit+push. Devolve uma mensagem de resultado para mostrar na UI."""
    export_schedule_json()

    status = _run_git('status', '--porcelain', 'schedule_data.json')
    if status.returncode != 0:
        return f'Erro a verificar o git: {status.stderr.strip()}'
    if not status.stdout.strip():
        return 'Já estava tudo sincronizado (sem alterações).'

    for args in (
        ('add', 'schedule_data.json'),
        ('commit', '-m', 'Sincronizar escala (automático)'),
        ('push',),
    ):
        result = _run_git(*args)
        if result.returncode != 0:
            return f'Falhou em "git {" ".join(args)}":\n{result.stderr.strip()}'

    return 'Escala sincronizada e enviada com sucesso.'
