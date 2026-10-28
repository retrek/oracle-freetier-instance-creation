"""Install or run the reboot-safe, single-process macOS bot service."""
import fcntl
import os
from pathlib import Path
import plistlib
import subprocess
import sys

LABEL = 'com.jeff.oracle-free-tier'
SCRATCH = Path('/Volumes/SANDISK SSD/AgentScratch/tmp')


def agent_config(root):
    return {
        'Label': LABEL,
        # Start from the system shell; keep launchd itself outside the runtime folder.
        'ProgramArguments': ['/bin/zsh', '-c', 'exec "$@"', 'oracle-bot',
                             str(root / '.venv/bin/python'), '-B', str(root / 'macos_agent.py')],
        'WorkingDirectory': '/',
        'RunAtLoad': True,
        'KeepAlive': {'SuccessfulExit': False},
        'ThrottleInterval': 300,
        'EnvironmentVariables': {'TMPDIR': str(SCRATCH)},
        'StandardOutPath': str(Path.home() / 'Library/Logs/oracle-free-tier.log'),
        'StandardErrorPath': str(Path.home() / 'Library/Logs/oracle-free-tier.log'),
    }


def run(root):
    if not os.path.ismount('/Volumes/SANDISK SSD') or not SCRATCH.is_dir() or not os.access(SCRATCH, os.W_OK):
        raise RuntimeError('SANDISK scratch is unavailable; refusing to start')
    os.chdir(root)
    os.environ['TMPDIR'] = str(SCRATCH)
    with (root / '.macos-agent.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Oracle bot service is already running') from None
        if (root / 'INSTANCE_CREATED').is_file() and (root / 'INSTANCE_CREATED').stat().st_size:
            return 0
        child = subprocess.Popen([str(root / '.venv/bin/python'), '-B', '-u', 'main.py'])
        (root / 'main.pid').write_text(f'{child.pid}\n')
        awake = subprocess.Popen(['/usr/bin/caffeinate', '-i', '-w', str(child.pid)])
        try:
            result = child.wait()
        finally:
            awake.terminate()
            awake.wait()
        if (root / 'INSTANCE_CREATED').is_file() and (root / 'INSTANCE_CREATED').stat().st_size:
            subprocess.run(['/usr/bin/osascript', '-e', 'display notification "See INSTANCE_CREATED in the Oracle bot folder." with title "Oracle instance acquired" sound name "Glass"'], check=False)
            return 0
        # A clean exit without a receipt still needs retrying.
        return result or 1


def install(root):
    target = Path.home() / 'Library/LaunchAgents' / f'{LABEL}.plist'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('wb') as output:
        plistlib.dump(agent_config(root), output)
    target.chmod(0o600)
    print(f'Installed {target}; start with: launchctl bootstrap gui/{os.getuid()} "{target}"')


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    if sys.argv[1:] == ['--install']:
        install(root)
    elif sys.argv[1:]:
        raise SystemExit('Usage: python macos_agent.py [--install]')
    else:
        raise SystemExit(run(root))
