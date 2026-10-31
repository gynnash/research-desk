"""Keep real membership reservations when an operator clears old outputs."""

from pathlib import Path
import re

import researchdesk_offline as store


def archived_calls(root, month):
    path = Path(root) / 'config/research_state.yaml'
    if not path.exists():
        return 0
    if path.is_symlink():
        raise store.OfflineError('历史预算状态不可为符号链接')
    state = store.load_yaml(path)
    if (not isinstance(state, dict) or type(state.get('schema_version')) is not int
            or state['schema_version'] != 1 or not isinstance(state.get('usage_months'), dict)):
        raise store.OfflineError('历史预算状态无效，不能清零额度')
    for key, count in state['usage_months'].items():
        if (not isinstance(key, str) or not re.fullmatch(r'\d{4}-\d{2}', key)
                or type(count) is not int or count < 0):
            raise store.OfflineError('历史预算计数无效')
    return state['usage_months'].get(month, 0)
