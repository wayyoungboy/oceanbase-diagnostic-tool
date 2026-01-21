#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
obdiag Agent memory manager
"""

from src.common.file_utils import FileUtils
import os
import json
from datetime import datetime


class MemoryManager:
    """Memory manager"""

    def __init__(self, context):
        self.context = context
        self.stdio = context.stdio
        self.session_store = SessionStore(context)
        self.case_store = CaseStore(context)

    def save_case(self, query: str, context: dict, result: dict):
        """Save case"""
        case = {'query': query, 'context': context, 'result': result, 'timestamp': datetime.now().isoformat()}
        self.case_store.save(case)

    def find_similar(self, query: str) -> list:
        """Find similar cases"""
        return self.case_store.search(query)


class SessionStore:
    """Session storage"""

    def __init__(self, context):
        self.context = context
        self.stdio = context.stdio
        self.session_dir = os.path.expanduser(context.config.get('memory', {}).get('session_dir', '~/.obdiag/ai_sessions'))

    def save_session(self, session_id: str, data: dict):
        """Save session"""
        os.makedirs(self.session_dir, exist_ok=True)
        session_file = os.path.join(self.session_dir, f"{session_id}.json")
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_session(self, session_id: str) -> dict:
        """Load session"""
        session_file = os.path.join(self.session_dir, f"{session_id}.json")
        if os.path.exists(session_file):
            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}


class CaseStore:
    """Case storage"""

    def __init__(self, context):
        self.context = context
        self.stdio = context.stdio
        self.case_dir = os.path.expanduser(context.config.get('memory', {}).get('case_dir', '~/.obdiag/ai_cases'))

    def save(self, case: dict):
        """Save case"""
        os.makedirs(self.case_dir, exist_ok=True)
        case_id = f"case_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        case_file = os.path.join(self.case_dir, f"{case_id}.json")
        with open(case_file, 'w', encoding='utf-8') as f:
            json.dump(case, f, ensure_ascii=False, indent=2)

    def search(self, query: str) -> list:
        """Search cases"""
        cases = []
        if not os.path.exists(self.case_dir):
            return cases

        for filename in os.listdir(self.case_dir):
            if filename.endswith('.json'):
                case_file = os.path.join(self.case_dir, filename)
                with open(case_file, 'r', encoding='utf-8') as f:
                    case = json.load(f)
                    cases.append(case)
        return cases
