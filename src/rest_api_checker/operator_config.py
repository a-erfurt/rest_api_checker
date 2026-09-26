"""Small, non-secret defaults for the optional operator launcher only."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import tomllib

from .persistence.database import database_name, read_settings


class OperatorError(ValueError):
    """A safe, actionable message (never a raw driver/credential exception)."""


@dataclass(frozen=True)
class Config:
    root: Path
    research: Path
    env_file: Path
    database: str = 'rest_api_checker'
    container: str = 'rac-sql-env-20260926-sqlserver-1'
    compose_project: str = 'rac-sql-env-20260926'
    host: str = '127.0.0.1'
    port: int = 8000


ENV = dict(root='RAC_ROOT', research='RAC_RESEARCH', env_file='RAC_ENV_FILE',
           database='RAC_DATABASE', container='RAC_CONTAINER', compose_project='RAC_COMPOSE_PROJECT',
           host='RAC_WEB_HOST', port='RAC_WEB_PORT')


def config_path():
    return Path(os.environ.get('RAC_CONFIG', '~/.config/rest-api-checker/config.toml')).expanduser()


def load(overrides):
    path = config_path()
    try:
        values = tomllib.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        raise OperatorError('Cannot read local config.toml; use only documented non-secret settings.') from None
    if set(values) - set(ENV):
        raise OperatorError('Unknown config.toml setting. Credentials belong only in the private env file.')
    explicit_credentials = (getattr(overrides, 'env_file', None) is not None or 'env_file' in values
                            or any(key in os.environ for key in ('RAC_ENV_FILE', 'RAC_WEB_ENV_FILE')))
    defaults = dict(database='rest_api_checker', container='rac-sql-env-20260926-sqlserver-1',
                    compose_project='rac-sql-env-20260926', host='127.0.0.1', port=8000,
                    root=Path(__file__).resolve().parents[2], env_file=path.parent/'credentials.env')
    for key, env in ENV.items():
        # Retain the existing web launcher's environment names as aliases.
        alias = {'env_file': 'RAC_WEB_ENV_FILE', 'database': 'RAC_WEB_DATABASE'}.get(key)
        candidates = (getattr(overrides, key, None), os.environ.get(env),
                      os.environ.get(alias) if alias else None, values.get(key), defaults.get(key))
        values[key] = next((value for value in candidates if value is not None), None)
    try:
        for key in ('root', 'research', 'env_file'):
            value = values[key]
            if key == 'research' and value is None:
                value = values['root'].parent/'bachelor_rest_api_checker'
            values[key] = Path(value).expanduser().resolve()
        values['port'] = int(values['port'])
        if not 1 <= values['port'] <= 65535:
            raise ValueError()
        database_name(values['database'])
        for key in ('container', 'compose_project'):
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', values[key]):
                raise ValueError()
        if values['host'] not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError()
    except (TypeError, ValueError):
        raise OperatorError('Invalid local defaults: check paths, database/container names, loopback host and port.') from None
    if explicit_credentials and not values['env_file'].is_file():
        raise OperatorError('Configured credentials file is missing. Update its path with --env-file or in config.toml.')
    return Config(**values)


def credentials(config):
    try:
        if any(config.env_file.resolve().is_relative_to(root) for root in (config.root, config.research)):
            raise OperatorError('Keep the private credentials file outside both Git repositories.')
        if stat.S_IMODE(config.env_file.stat().st_mode) != 0o600:
            raise OperatorError('Credentials file must have permissions 0600. Set chmod 600 on your private env file.')
        settings = read_settings(config.env_file)
        if not settings['RAC_SQL_PASSWORD']:
            raise ValueError()
        return settings
    except OperatorError:
        raise
    except FileNotFoundError:
        raise OperatorError('Credentials missing. Use rac configure --env-file /absolute/private/credentials.env '
                            'with an existing 0600 file containing RAC_SQL_PASSWORD and RAC_SQL_PORT.') from None
    except (OSError, ValueError, KeyError):
        raise OperatorError('Credentials file is unreadable or invalid. Check RAC_SQL_PASSWORD, RAC_SQL_PORT '
                            'and optional RAC_SQL_USER privately; file contents are never displayed.') from None


def save(config):
    """Explicit one-time setup; never copy secrets or overwrite an existing file."""
    credentials(config)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with path.open('x') as stream:
            for key in ENV:
                value = getattr(config, key)
                stream.write(f'{key} = {json.dumps(str(value) if isinstance(value, Path) else value)}\n')
    except FileExistsError:
        raise OperatorError('Config already exists; edit its non-secret settings explicitly. Nothing was overwritten.') from None
    return dict(status='CONFIGURED', config=str(path))
