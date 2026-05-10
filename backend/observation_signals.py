# Source Generated with Decompyle++
# File: observation_signals.pyc (Python 3.11)

__doc__ = 'Cheap signal extractors for the proactive observation gate.\n\nPure local code ΓÇö no model calls, no network. The context engine collects\nthese every ~10s and feeds them to a tiny local-Gemma classifier that\ndecides SPEAK / WATCH / IGNORE. Keeping signal extraction fast and cost-free\nis what lets the proactive loop run often enough to feel alive without\nburning tokens or CPU.\n'
from __future__ import annotations
import re
import time
from dataclasses import dataclass
_CATEGORY_PATTERNS: 'list[tuple[str, tuple[str, ...]]]' = [
    ('editor', ('visual studio code', 'vscode', ' - code', 'intellij', 'pycharm', 'webstorm', 'rider', 'clion', 'android studio', 'sublime text', 'notepad++', 'neovim', 'vim', 'emacs', 'cursor', 'zed', 'xcode', 'rstudio', 'spyder', 'jupyter')),
    ('terminal', ('powershell', 'command prompt', 'cmd.exe', 'windows terminal', 'bash', 'zsh', 'wsl', 'git bash', 'conemu', 'alacritty', 'tabby', 'hyper')),
    ('browser', ('chrome', 'firefox', 'edge', 'brave', 'opera', 'vivaldi', 'safari', 'arc', 'tor browser')),
    ('chat', ('discord', 'slack', 'microsoft teams', 'telegram', 'whatsapp', 'signal', 'messenger', 'zoom', 'google meet')),
    ('media', ('youtube', 'spotify', 'netflix', 'vlc', 'media player', 'twitch', 'obs', 'premiere pro', 'after effects', 'davinci resolve', 'audacity')),
    ('creative', ('photoshop', 'illustrator', 'figma', 'blender', 'touchdesigner', 'fl studio', 'ableton', 'logic pro', 'krita', 'gimp', 'procreate', 'sketch')),
    ('game', ('steam', 'epic games', 'minecraft', 'league of legends', 'valorant', 'fortnite', 'counter-strike', 'dota', 'overwatch')),
    ('system', ('settings', 'control panel', 'task manager', 'file explorer', 'system32', 'cmd '))]
# WARNING: Decompyle incomplete
