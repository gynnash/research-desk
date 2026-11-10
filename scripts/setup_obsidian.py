"""Keep a separate Obsidian projection of the workbench's origin/main."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
from urllib.parse import quote, unquote, urlsplit

import workbench
from offline import OfflineError
from setup_github import apply_system_github_proxy


class ObsidianSetupError(RuntimeError):
    """An actionable message that is safe to display in the setup UI."""


_MARKER = 'researchdesk-obsidian'
_MAIN = 'refs/remotes/origin/main'
_PATH_CONFIG = 'config/local/obsidian-vault.json'
# Standard Additions brings the chooser forward without a separate activation wait.
_FOLDER_PICKER = '''try
    set selectedFolder to choose folder with prompt "选择阅读库的空文件夹，或此工作台已有的阅读库。"
    return POSIX path of selectedFolder
on error number -128
    return ""
end try'''
_READING_PATTERNS = (
    '/README.md',
    '/研究首页.md',
    '/collection/**/*.md',
    '/summary/**/*.md',
    '/insights/**/*.md',
    '/articles/**/*.md',
    '/sources/papers/**/*.md',
    '/sources/blogs/**/*.md',
    '/sources/originals/**/*.md',
    '/reports/*/*.md',
    '/reports/*/解读/**/*.md',
    '/reports/*/reading/**/*.md',
    '!**/test/**',
    '!**/.*/**',
    '!**/.*',
)
_OBSIDIAN_EXCLUDE = b'/.obsidian/'
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
        self._default_path = parent.absolute() / (label + '-' + self._identity)
        self.path = self._default_path

    def _saved_path(self):
        try:
            config = workbench._path(self.root, _PATH_CONFIG)
            fd = os.open(config, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, encoding='utf-8') as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise ValueError('invalid configuration file')
                value = json.loads(handle.read(16384))
            if not isinstance(value, str) or not Path(value).is_absolute() or any(ord(c) < 32 for c in value):
                raise ValueError('invalid path')
            return Path(value)
        except FileNotFoundError:
            return self._default_path
        except (OSError, ValueError, OfflineError):
            raise ObsidianSetupError('无法读取保存的阅读库路径，请重新选择。') from None

    def _pick_folder(self):
        if sys.platform != 'darwin':
            raise ObsidianSetupError('请在 Mac 上打开本机向导选择阅读库路径。')
        try:
            result = subprocess.run(['/usr/bin/osascript', '-e', _FOLDER_PICKER],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    timeout=180, check=False, encoding='utf-8')
        except subprocess.TimeoutExpired:
            raise ObsidianSetupError('选择路径超时，请重新打开文件夹选择器。') from None
        except (OSError, UnicodeError):
            raise ObsidianSetupError('无法打开 Mac 文件夹选择器，请重试。') from None
        if result.returncode:
            raise ObsidianSetupError('无法打开 Mac 文件夹选择器，请重试。')
        selected = result.stdout.removesuffix('\n')
        return Path(selected) if selected else None

    def choose_path(self):
        try:
            selected = self._pick_folder()
            if selected is None:
                return False
            try:
                current = self._saved_path()
                self._safe_location(current)
            except (OSError, ObsidianSetupError):
                current = self._default_path
            self._safe_location(selected)
            if not selected.is_dir() or selected.is_mount():
                raise ObsidianSetupError('请选择磁盘中的空文件夹，或此工作台已有的阅读库。')
            if current.is_dir() and not selected.samefile(current) and self._overlaps(selected, current):
                raise ObsidianSetupError('请选择与当前阅读库分开的目录。')
            if any(selected.iterdir()):
                self._checkout(self._remote(self.root), selected)
            config = workbench._path(self.root, _PATH_CONFIG)
            workbench._write(config, (json.dumps(str(selected)) + '\n').encode('utf-8'))
            self.path = selected
            return True
        except (OSError, OfflineError):
            raise ObsidianSetupError('无法保存阅读库路径，请检查目录访问权限后重试。') from None

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

    @staticmethod
    def _overlaps(left, right):
        for child, parent in ((left, right), (right, left)):
            if child.is_relative_to(parent) or (parent.exists() and any(
                    part.exists() and part.samefile(parent) for part in (child, *child.parents))):
                return True
        return False

    def _safe_location(self, path=None):
        path = self.path if path is None else path
        if (not path.is_absolute() or '..' in path.parts or any(ord(c) < 32 for c in str(path))
                or any(part.casefold() in {'.git', '.obsidian'} for part in path.parts)
                or self._overlaps(path, self.root)
                or any(part.is_symlink() for part in (path, *path.parents))):
            raise ObsidianSetupError('阅读副本必须位于工作台之外，目录路径不能经过符号链接。')
        if any(part.exists() and not part.is_dir() for part in (path, *path.parents)):
            raise ObsidianSetupError('阅读副本路径已有文件占用，请先处理该路径。')
        if path != self._default_path and not path.parent.is_dir():
            raise ObsidianSetupError('所选阅读库的上级目录不可用，请重新连接磁盘或选择路径。')

    def _checkout(self, remote, path=None):
        path = self.path if path is None else path
        self._safe_location(path)
        git_dir = path / '.git'
        marker = git_dir / _MARKER
        conflict = '该目录已被占用，向导只更新自己创建的阅读副本。已有文件已保留。'
        if git_dir.is_symlink() or not git_dir.is_dir() or marker.is_symlink() or not marker.is_file():
            raise ObsidianSetupError(conflict)
        with marker.open('rb') as handle:
            if handle.read(64) != (self._identity + '\n').encode():
                raise ObsidianSetupError(conflict)
        for relative in ('config', 'config.worktree', 'HEAD', 'index', 'refs', 'packed-refs', 'objects',
                         'commondir', 'info', 'info/exclude', 'info/sparse-checkout'):
            if (git_dir / relative).is_symlink():
                raise ObsidianSetupError(conflict)
        top = Path(os.fsdecode(self._git(path, 'rev-parse', '--show-toplevel', message=conflict)).removesuffix('\n'))
        if (not top.is_absolute() or not top.samefile(path)
                or _reading_remote(self._remote(path)) != _reading_remote(remote)):
            raise ObsidianSetupError('阅读副本的 Git origin 或工作目录已变化，已保留现有文件。')
        if (path / '.obsidian').is_symlink():
            raise ObsidianSetupError('阅读副本的 Obsidian 设置目录使用了符号链接，已停止更新。')

    def _clean_main(self):
        if self._git(self.path, 'branch', '--show-current').strip() != b'main':
            raise ObsidianSetupError('阅读副本当前不在 main，已保留现有文件。')
        changes = self._git(self.path, 'status', '--porcelain', '-z', '--untracked-files=all')
        # Older copies can lack the local exclude until the next successful sync.
        if any(entry and not entry.startswith(b'?? .obsidian/') for entry in changes.split(b'\0')):
            raise ObsidianSetupError('阅读副本有本地改动，请先保存或移出这些文件，再刷新 GitHub 内容。')

    def status(self):
        result = {'state': 'not_ready', 'path': str(self.path), 'can_sync': False, 'can_open': False,
                  'can_choose_path': sys.platform == 'darwin',
                  'message': '同步后可在 Obsidian 中将此目录打开为仓库。'}
        try:
            self.path = self._saved_path()
            result['path'] = str(self.path)
            self._safe_location()
            remote = self._remote(self.root)
            if self.path.exists() and any(self.path.iterdir()):
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

    def _project(self, checkout):
        info = checkout / '.git' / 'info'
        if info.is_symlink():
            raise ObsidianSetupError('阅读副本的 Git 设置目录使用了符号链接，已停止更新。')
        info.mkdir(mode=0o700, exist_ok=True)
        fd = os.open(info / 'exclude', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'r+b') as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ObsidianSetupError('阅读副本的 Git 忽略文件位置已被占用。')
            existing = handle.read()
            if _OBSIDIAN_EXCLUDE not in existing.splitlines():
                if existing and not existing.endswith(b'\n'):
                    handle.write(b'\n')
                handle.write(_OBSIDIAN_EXCLUDE + b'\n')
        self._git(checkout, 'sparse-checkout', 'set', '--no-cone', '--', *_READING_PATTERNS,
                  message='无法设置阅读文件范围，请检查本机 Git 和阅读副本后重试。')

    def _check_projection_conflicts(self):
        # A sparse fast-forward can overwrite ignored files even with --no-overwrite-ignore.
        ignored = self._git(self.path, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z',
                            '--', ':(exclude,top).obsidian')
        if not ignored:
            return
        pathspec = [':(top,glob,icase)' + pattern[1:] for pattern in _READING_PATTERNS if pattern.startswith('/')]
        pathspec.extend(':(top,glob,exclude)' + pattern[1:] for pattern in _READING_PATTERNS if pattern.startswith('!'))
        incoming = self._git(self.path, 'diff', '--name-only', '--diff-filter=A', '--no-renames', '-z',
                             'HEAD', _MAIN, '--', *pathspec)

        def names(data):
            return [unicodedata.normalize('NFC', os.fsdecode(path)).casefold()
                    for path in data.split(b'\0') if path]

        local = names(ignored)
        if any(path == existing or path.startswith(existing + '/') or existing.startswith(path + '/')
               for path in names(incoming) for existing in local):
            raise ObsidianSetupError('GitHub 的新阅读文件与阅读副本中的本地文件冲突，已保留现有文件。')

    def _clone(self, remote):
        occupied = '阅读目录已被占用，已保留现有文件。'
        original = self.path.lstat() if self.path.exists() else None
        if original and (not stat.S_ISDIR(original.st_mode) or any(self.path.iterdir())):
            raise ObsidianSetupError(occupied)
        source, github_auth = _reading_remote(remote)
        with tempfile.TemporaryDirectory(prefix='.researchdesk-clone-', dir=self.path.parent) as scratch:
            staged = Path(scratch) / 'vault'
            self._git(self.root, 'clone', '--no-local', '--no-checkout', '--single-branch', '--branch', 'main',
                      '--no-tags', '--', source, str(staged), network=True, github_auth=github_auth,
                      message='无法克隆 GitHub 的 main。请检查网络、仓库权限和向导的 GitHub 登录。')
            self._validate_tree(staged)
            self._project(staged)
            self._git(staged, 'checkout', 'main', message='无法准备 main 的阅读文件。')
            (staged / '.git' / _MARKER).write_text(self._identity + '\n', encoding='ascii')
            staged.chmod(0o700)
            self._safe_location()
            if original is None:
                try:
                    self.path.mkdir(mode=0o700)
                except FileExistsError:
                    raise ObsidianSetupError(occupied) from None
            reservation = self.path.lstat()
            if original and (not os.path.samestat(original, reservation) or any(self.path.iterdir())):
                raise ObsidianSetupError(occupied)
            try:
                os.rename(staged, self.path)
            except OSError:
                if original is None:
                    try:
                        if os.path.samestat(self.path.lstat(), reservation):
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
        self._check_projection_conflicts()
        self._project(self.path)
        self._git(self.path, 'merge', '--ff-only', '--no-overwrite-ignore', _MAIN,
                  message='无法安全快进更新。请先处理阅读副本中的冲突文件。')

    def sync(self):
        try:
            self.path = self._saved_path()
            with self._lock():
                remote = self._remote(self.root)
                if self.path.exists() and any(self.path.iterdir()):
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
            self.path = self._saved_path()
            self._safe_location()
            if not self.path.exists() or not any(self.path.iterdir()):
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
            if (self.path / '.obsidian').is_dir():
                for name in ('研究首页.md', 'README.md'):
                    note = self.path / name
                    if note.is_file() and not note.is_symlink():
                        uri = 'obsidian://open?path=' + quote(str(note), safe='')
                        break
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
