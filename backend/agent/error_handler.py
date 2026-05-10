# Source Generated with Decompyle++
# File: error_handler.pyc (Python 3.11)

'''
Am├⌐ Agent Error Handler ΓÇö analyzes step failures and decides how to proceed.
'''
import sys
import os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding = 'utf-8', errors = 'replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding = 'utf-8', errors = 'replace')
import json
from backend import load_env
from backend.gemini_client import call_task_model, extract_text, AllModelsExhaustedError
from backend.providers import route, Purpose
from backend.thinking_emotion import ThinkingEmotion
load_env()
DECISIONS = [
    'retry',
    'skip',
    'replan',
    'abort']
_ERROR_PROMPT = 'An AI assistant step failed. Decide how to proceed.\n\nStep: {step_description}\nTool: {tool}\nError: {error}\nAttempt number: {attempt}\n\nDecide: retry / skip / replan / abort\n\nRules:\n- retry: transient error (network timeout, rate limit). Max 2 retries.\n- skip: step is non-critical and can be omitted safely.\n- replan: critical step failed but the goal is still achievable differently.\n- abort: goal is impossible or the error is fatal.\n\nReturn ONLY valid JSON:\n{{\n  "decision": "retry|skip|replan|abort",\n  "reason": "one sentence why",\n  "fix_suggestion": "what to try differently (optional)",\n  "user_message": "brief message to tell the user"\n}}\nJSON only:'

def analyze_error(step = None, error = None, attempt = None):
    '''Analyze a step failure and return a decision dict.'''
    if not os.getenv('GOOGLE_AI_STUDIO_KEY'):
        api_key = os.getenv('GEMINI_API_KEY')
        is_critical = step.get('critical', False)
        if attempt >= 2:
            decision = 'replan' if is_critical else 'skip'
        elif 'timeout' in error.lower() or 'rate' in error.lower():
            decision = 'retry'
        elif is_critical:
            decision = 'replan'
        else:
            decision = 'skip'
    fallback = {
        'decision': decision,
        'reason': f'''Step failed after {attempt} attempt(s): {error[:100]}''',
        'fix_suggestion': '',
        'user_message': f'''Hit a snag on \'{step.get('description', 'step')}\', trying to work around it.''' }
    if not api_key:
        if is_critical and decision == 'skip':
            fallback['decision'] = 'replan'
        return fallback
    prompt = _ERROR_PROMPT.format(step_description = step.get('description', ''), tool = step.get('tool', ''), error = error, attempt = attempt)
# WARNING: Decompyle incomplete

