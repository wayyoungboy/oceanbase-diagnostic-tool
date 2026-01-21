#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
obdiag Agent knowledge manager
"""


class KnowledgeManager:
    """Knowledge manager"""

    def __init__(self, context):
        self.context = context
        self.stdio = context.stdio
        self.providers = [OBIProvider(context), LocalProvider(context), BuiltinProvider(context)]

    def search(self, query: str, context: dict) -> dict:
        """Search knowledge"""
        for provider in self.providers:
            if provider.is_available():
                return provider.search(query, context)
        return {}


class OBIProvider:
    """OBI knowledge source"""

    def __init__(self, context):
        self.context = context
        self.stdio = context.stdio
        self._access_token = None
        self._token_expiry = None
        self._token_lock = False  # Prevent concurrent refresh

    def is_available(self) -> bool:
        """Check if available"""
        obi_config = self.context.config.get('knowledge', {}).get('obi', {})
        if not obi_config.get('enabled', False):
            return False

        base_url = obi_config.get('base_url', 'https://ai-api.oceanbase.com')
        app_code = obi_config.get('app_code', '')
        authorization = obi_config.get('authorization', '')

        return bool(app_code and authorization)

    def _get_access_token(self) -> str:
        """Get or refresh access_token with caching mechanism"""
        import time
        import threading

        # If token exists and not expired (with 2-minute buffer)
        if self._access_token and self._token_expiry:
            if time.time() < self._token_expiry - 120:  # Refresh 2 minutes early
                return self._access_token

        # Prevent concurrent refresh
        if self._token_lock:
            # Wait for other thread to complete refresh
            max_wait = 10  # Maximum wait 10 seconds
            start_time = time.time()
            while self._token_lock and time.time() - start_time < max_wait:
                time.sleep(0.1)
            return self._access_token

        self._token_lock = True
        try:
            obi_config = self.context.config.get('knowledge', {}).get('obi', {})
            base_url = obi_config.get('base_url', 'https://ai-api.oceanbase.com')
            app_code = obi_config.get('app_code', '')
            authorization = obi_config.get('authorization', '')

            auth_url = f"{base_url}/v1/authn/authenticate"
            params = {'app_code': app_code, 'authn_type': 'custom'}
            headers = {'Authorization': authorization}

            import requests

            response = requests.post(auth_url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                auth_data = response.json()
                self._access_token = auth_data.get('access_token')

                # Set token expiration time (30-minute validity)
                self._token_expiry = time.time() + 1800

                if self._access_token:
                    self.stdio.verbose("Successfully obtained new access_token")
                    return self._access_token

        except Exception as e:
            self.stdio.error(f"Failed to get access_token: {str(e)}")
        finally:
            self._token_lock = False

        return None

    def search(self, query: str, context: dict) -> dict:
        """Search knowledge, automatically handle token refresh"""
        if not self.is_available():
            return {}

        access_token = self._get_access_token()
        if not access_token:
            return {}

        try:
            import requests

            obi_config = self.context.config.get('knowledge', {}).get('obi', {})
            base_url = obi_config.get('base_url', 'https://ai-api.oceanbase.com')
            app_code = obi_config.get('app_code', '')

            chat_url = f"{base_url}/api/chat-messages"
            headers = {'Authorization': f'Bearer {access_token}', 'X-App-Code': app_code, 'Content-Type': 'application/json'}

            data = {'query': query, 'response_mode': 'blocking', 'inputs': {'enable_deepthink': 0}}

            response = requests.post(chat_url, headers=headers, json=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return {'answer': result.get('answer', ''), 'references': result.get('retriever_resources', [])}
            elif response.status_code == 401:
                # Token expired, force refresh and retry
                self._access_token = None
                self._token_expiry = None
                return self.search(query, context)  # Recursive retry once

        except Exception as e:
            self.stdio.error(f"OBI knowledge search failed: {str(e)}")

        return {}


class LocalProvider:
    """Local knowledge source"""

    def __init__(self, context):
        self.context = context

    def is_available(self) -> bool:
        """Check if available"""
        return True  # Always available

    def search(self, query: str, context: dict) -> dict:
        """Search knowledge"""
        return {}


class BuiltinProvider:
    """Built-in knowledge source"""

    def __init__(self, context):
        self.context = context

    def is_available(self) -> bool:
        """Check if available"""
        return True  # Always available

    def search(self, query: str, context: dict) -> dict:
        """Search knowledge"""
        return {}
