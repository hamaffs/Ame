# Source Generated with Decompyle++
# File: planner.pyc (Python 3.11)

'''
Am├⌐ Agent Planner ΓÇö breaks a natural language goal into up to 5 executable steps.
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
AVAILABLE_TOOLS = [
    'web_search_ddg',
    'scrape_and_summarize',
    'open_url',
    'google_search',
    'run_web_task',
    'search_files',
    'type_text',
    'copy_to_clipboard',
    'take_screenshot',
    'run_terminal_command',
    'analyze_screen',
    'analyze_webcam',
    'play_song_on_spotify',
    'play_spotify_by_mood',
    'play_music_on_youtube',
    'open_application',
    'close_application',
    'set_volume',
    'get_current_time',
    'get_current_date',
    'organize_desktop',
    'clean_desktop',
    'list_desktop']
_PLAN_PROMPT = 'You are a task planner for an AI assistant. Break the goal into at most 5 concrete steps.\n\nAvailable tools: {tools}\n\nGoal: {goal}\n\nReturn ONLY valid JSON:\n{{\n  "goal": "{goal}",\n  "steps": [\n    {{\n      "step": 1,\n      "tool": "tool_name",\n      "description": "What this step does",\n      "parameters": {{"param": "value"}},\n      "critical": true\n    }}\n  ]\n}}\n\nRules:\n- Use the simplest sequence possible ΓÇö fewer steps is better.\n- "critical": true means failure of this step should abort or replan.\n- parameters must match the tool\'s expected inputs.\n- If the goal is simple enough for one tool, use one step.\nJSON only:'

def _call_gemini(prompt = None, api_key = None):
    '''Kept for backward compatibility ΓÇö prefer route(Purpose.AGENT_PLAN).'''
    contents = [
        {
            'parts': [
                {
                    'text': prompt }] }]
    resp = call_task_model(contents, api_key = api_key, timeout = 15)
    return extract_text(resp)


def _route_agent(prompt = None):
    '''Route through the purpose router for agent plans.'''
    pass
# WARNING: Decompyle incomplete


def _parse_json_response(raw = None):
    '''Strip markdown fences and parse JSON.'''
    if raw.startswith('```'):
        parts = raw.split('```')
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith('json'):
            raw = raw[4:]
    return json.loads(raw.strip())


def create_plan(goal = None):
    '''Break goal into up to 5 steps.'''
    if not os.getenv('GOOGLE_AI_STUDIO_KEY'):
        api_key = os.getenv('GEMINI_API_KEY')
        fallback = {
            'goal': goal,
            'steps': [
                {
                    'step': 1,
                    'tool': 'web_search_ddg',
                    'description': f'''Search for: {goal}''',
                    'parameters': {
                        'query': goal },
                    'critical': True }] }
        if not api_key:
            return fallback
        prompt = _PLAN_PROMPT.format(tools = ', '.join(AVAILABLE_TOOLS), goal = goal)
        raw = _route_agent(prompt)
        plan = _parse_json_response(raw)
        steps = plan.get('steps', [])[:5]
        plan['steps'] = steps
        return plan
# WARNING: Decompyle incomplete


def replan(goal = None, completed_steps = None, failed_step = None, error = ('goal', str, 'completed_steps', list, 'failed_step', dict, 'error', str, 'return', dict)):
    '''Create a revised plan that works around the failure.'''
    if not os.getenv('GOOGLE_AI_STUDIO_KEY'):
        api_key = os.getenv('GEMINI_API_KEY')
        completed_desc = completed_steps()
        failed_desc = failed_step.get('description', '')
        prompt = f'''You are replanning a task after a step failed.\n\nGoal: {goal}\nAlready completed: {json.dumps(completed_desc)}\nFailed step: {failed_desc}\nError: {error}\n\nCreate a new plan for ONLY the remaining work (skip completed steps).\nAvailable tools: {', '.join(AVAILABLE_TOOLS)}\n\nReturn ONLY valid JSON:\n{{"goal": "{goal}", "steps": [{{"step": 1, "tool": "...", "description": "...", "parameters": {{}}, "critical": false}}]}}\nJSON only:'''
        raw = _route_agent(prompt)
        plan = _parse_json_response(raw)
        plan['steps'] = plan.get('steps', [])[:5]
        return plan
# WARNING: Decompyle incomplete

