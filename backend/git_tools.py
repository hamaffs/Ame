# Source Generated with Decompyle++
# File: git_tools.pyc (Python 3.11)

'''
Am├⌐ Git Tools ΓÇö strictly read-only git operations.

No commits, no pushes, no destructive operations.
Only status, log, diff, and branch listing.
'''
import os
import subprocess
_ALLOWED_COMMANDS = {
    'git_status': [
        'git',
        'status',
        '--porcelain',
        '-b'],
    'git_log': [
        'git',
        'log',
        '--oneline',
        '--no-color'],
    'git_diff': [
        'git',
        'diff',
        '--stat',
        '--no-color'],
    'git_branches': [
        'git',
        'branch',
        '-a',
        '--no-color'] }

def run_git_tool(tool_name = None, params = None):
    '''Execute a read-only git command. Returns structured result.'''
    if tool_name not in _ALLOWED_COMMANDS:
        return {
            'success': False,
            'error': f'''Unknown git tool: {tool_name}''' }
    path = None.get('path', '')
    if not path or os.path.isdir(path):
        return {
            'success': False,
            'error': f'''Invalid directory: {path}''' }
    check = subprocess.run([
        'git',
        'rev-parse',
        '--git-dir'], cwd = path, capture_output = True, text = True, timeout = 5)
    if check.returncode != 0:
        return {
            'success': False,
            'error': f'''Not a git repository: {path}''' }
# WARNING: Decompyle incomplete

