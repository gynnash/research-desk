"""Keep a separate local Obsidian reading copy of the workbench's origin/main."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import quote, unquote, urlsplit

from researchdesk_setup_github import apply_system_github_proxy


class ObsidianSetupError(RuntimeError):
    """An actionable message that is safe to display in the setup UI."""


_MARKER = 'researchdesk-obsidian'
_MAIN = 'refs/remotes/origin/main'
_GITHUB_REPO = re.compile(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+')
_GIT_OVERRIDE = {
    'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE', 'GIT_NAMESPACE',
    'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_CONFIG',
    'GIT_CONFIG_COUNT', 'GIT_CONFIG_PARAMETERS', 'GIT_SSH',
}


def _reading_directory():
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/ResearchDesk/obsidian-vaults'
    return Path.home() / '.local/share/ResearchDesk/obsidian-vaults'


def _normalized_remote(value, root):
    if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ObsidianSetupError('当前工作台的 Git origin 格式无效。')
    if re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+', value):
        return value
    try:
        url = urlsplit(value)
        if url.scheme in {'https', 'ssh'}:
            port = url.port  # Also reject invalid or non-numeric port syntax.
            if (not url.hostname or not url.path or url.query or url.fragment or url.password is not None
                    or port == 0 or (url.scheme == 'https' and url.username is not None)):
                raise ValueError
            return value
        if url.scheme == 'file' and url.netloc in {'', 'localhost'} and not url.query and not url.fragment:
            value = unquote(url.path)
            if not value.startswith('/'):
                raise ValueError
        elif url.scheme or '::' in value or value.startswith('-'):
            raise ValueError
        return str((root / value).resolve())
    except (ValueError, OSError, RuntimeError):
        raise ObsidianSetupError('Git origin 需要有效的 HTTPS、SSH 或本机仓库地址，地址中请勿包含凭据。') from None


def _github_repo(remote):
    match = re.fullmatch(r'git@github\.com:([^?#]+)', remote, re.IGNORECASE)
    if match:
        name = match[1]
    else:
        url = urlsplit(remote)
        ports = {'https': 443, 'ssh': 22}
        if (url.hostname != 'github.com' or url.scheme not in ports
                or url.port not in {None, ports[url.scheme]}):
            return None
        name = url.path.strip('/')
    name = name.removesuffix('.git')
    return name.casefold() if _GITHUB_REPO.fullmatch(name) else None


def _reading_remote(remote):
    repo = _github_repo(remote)
    return ('https://github.com/' + repo + '.git', True) if repo else (remote, False)


def _git_environment():
    env = {key: value for key, value in os.environ.items()
           if key not in _GIT_OVERRIDE and not key.startswith(('GIT_CONFIG_KEY_', 'GIT_CONFIG_VALUE_', 'GIT_TRACE'))}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_ASKPASS=shutil.which('false') or '/usr/bin/false',
               SSH_ASKPASS_REQUIRE='never', GIT_SSH_COMMAND='ssh -o BatchMode=yes',
               GCM_INTERACTIVE='Never', GH_PROMPT_DISABLED='1')
    return env


class ObsidianSetup:
    def __init__(self, root, vaults_directory=None):
        self.root = Path(root).resolve()
        self._identity = hashlib.sha256(os.fsencode(self.root)).hexdigest()[:16]
        label = re.sub(r'[^a-z0-9_-]+', '-', self.root.name.lower()).strip('-_')[:40] or 'researchdesk'
        parent = _reading_directory() if vaults_directory is None else Path(vaults_directory).expanduser()
        self.path = parent.absolute() / (label + '-' + self._identity)

    def _git(self, root, *args, message='无法读取 Git 仓库，请检查本机 Git 设置。',
             network=False, github_auth=False):
        command = ['git', '-C', str(root), '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                   '-c', 'protocol.allow=never', '-c', 'protocol.https.allow=always',
                   '-c', 'protocol.ssh.allow=always', '-c', 'protocol.file.allow=always']
        env = _git_environment()
        if github_auth:
            # Reuse the existing gh login on the Mac, or the scoped job token in Actions.
            # Apply only to this command, and bypass machine-wide URL rewriting.
            command += ['-c', 'credential.helper=', '-c', 'credential.https://github.com.helper=!gh auth git-credential']
            env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
            if network:
                apply_system_github_proxy(env)
        try:
            result = subprocess.run([*command, *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, env=env,
                                    timeout=90 if network else 10, check=False)
        except subprocess.TimeoutExpired:
            if network and github_auth:
                message = '从 GitHub 同步阅读库超时。请检查网络或代理后重试。'
            raise ObsidianSetupError(message) from None
        except OSError:
            raise ObsidianSetupError(message) from None
        if result.returncode:
            raise ObsidianSetupError(message)
        return result.stdout

    def _remote(self, root):
        raw = self._git(root, 'remote', 'get-url', 'origin',
                        message='找不到 Git origin。请先在向导连接自己的 GitHub 仓库。')
        return _normalized_remote(os.fsdecode(raw).removesuffix('\n'), root)

    def _safe_location(self):
        if ('..' in self.path.parts or self.path.is_relative_to(self.root) or self.root.is_relative_to(self.path)
                or any(path.is_symlink() for path in (self.path, *self.path.parents))):
            raise ObsidianSetupError('阅读副本必须位于工作台之外，目录路径不能经过符号链接。')
        if any(path.exists() and not path.is_dir() for path in (self.path, *self.path.parents)):
            raise ObsidianSetupError('阅读副本路径已有文件占用，请先处理该路径。')

    def _checkout(self, remote):
        self._safe_location()
        git_dir = self.path / '.git'
        marker = git_dir / _MARKER
        conflict = '该目录已被占用，向导只更新自己创建的阅读副本。已有文件已保留。'
        if git_dir.is_symlink() or not git_dir.is_dir() or marker.is_symlink() or not marker.is_file():
            raise ObsidianSetupError(conflict)
        with marker.open('rb') as handle:
            if handle.read(64) != (self._identity + '\n').encode():
                raise ObsidianSetupError(conflict)
        for relative in ('config', 'HEAD', 'index', 'refs', 'packed-refs', 'objects', 'commondir'):
            if (git_dir / relative).is_symlink():
                raise ObsidianSetupError(conflict)
        top = self._git(self.path, 'rev-parse', '--show-toplevel', message=conflict)
        if (Path(os.fsdecode(top).removesuffix('\n')) != self.path
                or _reading_remote(self._remote(self.path)) != _reading_remote(remote)):
            raise ObsidianSetupError('阅读副本的 Git origin 或工作目录已变化，已保留现有文件。')
        if (self.path / '.obsidian').is_symlink():
            raise ObsidianSetupError('阅读副本的 Obsidian 设置目录使用了符号链接，已停止更新。')

    def _clean_main(self):
        if self._git(self.path, 'branch', '--show-current').strip() != b'main':
            raise ObsidianSetupError('阅读副本当前不在 main，已保留现有文件。')
        if self._git(self.path, 'status', '--porcelain', '--untracked-files=all'):
            raise ObsidianSetupError('阅读副本有本地改动，请先保存或移出这些文件，再刷新 GitHub 内容。')

    def status(self):
        result = {'state': 'not_ready', 'path': str(self.path), 'can_sync': False, 'can_open': False,
                  'message': '同步后可在 Obsidian 中将此目录打开为仓库。'}
        try:
            self._safe_location()
            remote = self._remote(self.root)
            if self.path.exists():
                self._checkout(remote)
                result['can_open'] = True
                self._clean_main()
                result.update(state='ready', message='阅读副本已就绪。首次打开时请选择「打开文件夹作为仓库」。')
            result['can_sync'] = True
        except (ObsidianSetupError, OSError) as exc:
            result.update(state='blocked', message=str(exc) if isinstance(exc, ObsidianSetupError)
                          else '无法读取阅读副本，请检查目录访问权限。')
        return result

    @contextmanager
    def _lock(self):
        self._safe_location()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._safe_location()
        lock = self.path.parent / ('.' + self.path.name + '.lock')
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ObsidianSetupError('阅读副本的同步锁位置已被占用。')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ObsidianSetupError('阅读副本正在同步，请稍后重试。') from None
            yield
        finally:
            os.close(fd)

    def _validate_tree(self, checkout):
        for entry in self._git(checkout, 'ls-tree', '-rz', _MAIN).split(b'\0'):
            if not entry:
                continue
            metadata, _, path = entry.partition(b'\t')
            if (metadata.startswith((b'120000 ', b'160000 '))
                    or path.split(b'/', 1)[0].lower() == b'.obsidian'):
                raise ObsidianSetupError('GitHub 的 main 包含符号链接、子模块或 Obsidian 本地设置，已停止更新阅读副本。')

    def _clone(self, remote):
        source, github_auth = _reading_remote(remote)
        with tempfile.TemporaryDirectory(prefix='.researchdesk-clone-', dir=self.path.parent) as scratch:
            staged = Path(scratch) / 'vault'
            self._git(self.root, 'clone', '--no-local', '--no-checkout', '--single-branch', '--branch', 'main',
                      '--no-tags', '--', source, str(staged), network=True, github_auth=github_auth,
                      message='无法克隆 GitHub 的 main。请检查网络、仓库权限和向导的 GitHub 登录。')
            self._validate_tree(staged)
            self._git(staged, 'checkout', 'main', message='无法准备 main 的阅读文件。')
            (staged / '.git' / _MARKER).write_text(self._identity + '\n', encoding='ascii')
            staged.chmod(0o700)
            self._safe_location()
            try:
                self.path.mkdir(mode=0o700)
            except FileExistsError:
                raise ObsidianSetupError('阅读目录已被占用，已保留现有文件。') from None
            reservation = self.path.lstat()
            try:
                os.rename(staged, self.path)
            except OSError:
                current = self.path.lstat()
                if (current.st_dev, current.st_ino) == (reservation.st_dev, reservation.st_ino):
                    try:
                        self.path.rmdir()
                    except OSError:
                        pass
                raise

    def _update(self, remote):
        self._checkout(remote)
        self._clean_main()
        # Use explicit refspec and read-only credentials without storing a second remote.
        source, github_auth = _reading_remote(remote)
        self._git(self.path, 'fetch', '--no-tags', '--no-recurse-submodules', '--', source,
                  'refs/heads/main:' + _MAIN, network=True, github_auth=github_auth,
                  message='无法读取 GitHub 的 main。请检查网络、仓库权限和向导的 GitHub 登录。')
        self._validate_tree(self.path)
        self._checkout(remote)
        self._clean_main()
        self._git(self.path, 'merge-base', '--is-ancestor', 'HEAD', _MAIN,
                  message='阅读副本与 GitHub 的 main 已分叉或本地有独有提交，现有文件已保留。')
        self._git(self.path, 'merge', '--ff-only', '--no-overwrite-ignore', _MAIN,
                  message='无法安全快进更新。请先处理阅读副本中的冲突文件。')

    def sync(self):
        try:
            with self._lock():
                remote = self._remote(self.root)
                if self.path.exists():
                    self._update(remote)
                else:
                    self._clone(remote)
        except OSError:
            raise ObsidianSetupError('无法更新阅读副本，请检查目录访问权限或是否有其他程序正在写入。') from None

    def refresh_existing(self, expected_repo):
        """Update a provisioned vault after an Actions saver has pushed to main."""
        if not _GITHUB_REPO.fullmatch(expected_repo):
            raise ObsidianSetupError('GitHub 仓库标识无效，已跳过自动刷新。')
        try:
            self._safe_location()
            if not self.path.exists():
                return False
            with self._lock():
                remote = self._remote(self.root)
                if _github_repo(remote) != expected_repo.casefold():
                    raise ObsidianSetupError('执行器绑定工作台的 origin 与当前 GitHub 仓库不一致。')
                self._update(remote)
                return True
        except OSError:
            raise ObsidianSetupError('无法刷新阅读副本，请检查目录访问权限。') from None

    def open(self, *, finder=False):
        status = self.status()
        if not status['can_open']:
            raise ObsidianSetupError('请先准备可用的阅读副本，再打开目录。')
        if sys.platform != 'darwin':
            raise ObsidianSetupError('请复制阅读目录路径，在本机 Obsidian 中打开该文件夹。')
        if not finder:
            uri = 'obsidian://choose-vault'
            config = self.path / '.obsidian'
            readme = self.path / 'README.md'
            if config.is_dir() and readme.is_file() and not readme.is_symlink():
                uri = 'obsidian://open?path=' + quote(str(readme), safe='')
            if self._launch(uri):
                return
        if not self._launch('-R', str(self.path)):
            raise ObsidianSetupError('无法打开 Obsidian 或 Finder，请复制阅读目录路径后手动打开。')

    @staticmethod
    def _launch(*args):
        try:
            return subprocess.run(['/usr/bin/open', *args], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=10, check=False).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-existing', action='store_true', required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--expected-repo', required=True)
    args = parser.parse_args(argv)
    actions = os.environ.get('GITHUB_ACTIONS') == 'true'
    try:
        if not args.root.is_absolute() or not args.root.is_dir():
            raise ObsidianSetupError('执行器没有绑定有效的本机工作台。')
        if actions and (os.environ.get('GITHUB_REPOSITORY', '').casefold() != args.expected_repo.casefold()
                        or not os.environ.get('GH_TOKEN')):
            raise ObsidianSetupError('缺少当前仓库的只读授权，已跳过自动刷新。')
        updated = ObsidianSetup(args.root).refresh_existing(args.expected_repo)
    except ObsidianSetupError as exc:
        print(('::warning::' if actions else '') + str(exc), file=sys.stderr)
        return 1
    print('已刷新 Obsidian 阅读副本。' if updated else '本机尚未建立 Obsidian 阅读副本，已跳过。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
