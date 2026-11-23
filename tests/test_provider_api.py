"""Проверка трёх API по локальным HTTP-заглушкам без реальных ключей."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from common.llm import LLMClient


class APIHandler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.received.append((self.path, dict(self.headers), data))
        if self.path.endswith('/api/chat'):
            response = {'message': {'content': '{"move":"Rock"}'}}
        elif self.path.endswith('/chat/completions'):
            response = {'choices': [{'message': {'content': '{"move":"Rock"}'}}]}
        else:
            response = {'content': [{'type':'text','text':'{"bid": 30}' }]}
        body = json.dumps(response).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class ProviderTests(unittest.TestCase):
    def test_three_providers_with_http_stub(self):
        APIHandler.received = []
        http = ThreadingHTTPServer(('127.0.0.1',0), APIHandler)
        thread = threading.Thread(target=http.serve_forever,daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{http.server_port}'
            with patch.dict(os.environ, {'OPENAI_API_KEY':'test-key', 'ANTHROPIC_API_KEY':'test-key'}):
                for provider in ('ollama','openai','anthropic'):
                    with self.subTest(provider=provider):
                        cfg = {'provider':provider,'model':'test-model','base_url':url,'temperature':0.7,
                               'timeout':5,'max_tokens':64}
                        client = LLMClient(cfg)
                        response = client.chat([{'role':'system','content':'Rules'},
                                                {'role':'user','content':'Choose'}], seed=42)
                        self.assertIn('{',response)
            self.assertEqual([x[0] for x in APIHandler.received],
                             ['/api/chat','/v1/chat/completions','/v1/messages'])
            self.assertEqual(APIHandler.received[0][2]['options']['temperature'],0.7)
            self.assertEqual(APIHandler.received[0][2]['options']['seed'],42)
            self.assertEqual(APIHandler.received[1][2]['model'],'test-model')
            self.assertIn('x-api-key', {k.lower():v for k,v in APIHandler.received[2][1].items()})
        finally:
            http.shutdown();http.server_close();thread.join(timeout=2)

    def test_key_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                LLMClient({'provider':'anthropic','model':'test-model'})
