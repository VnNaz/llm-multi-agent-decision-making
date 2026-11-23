import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from water_allocation.agents import LLMAgent


class Handler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        size = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(size))
        Handler.received.append(data)
        content = json.dumps({'bid': 65, 'reason': 'Save money and win if possible'})
        payload = json.dumps({'message': {'role': 'assistant', 'content': content}, 'done': True}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class OllamaAPITests(unittest.TestCase):
    def test_ollama_rest_chat_payload_and_json(self):
        Handler.received = []
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            a = LLMAgent({'provider':'ollama','model':'qwen2.5:7b','base_url':f'http://127.0.0.1:{httpd.server_port}', 'temperature':0.7,'timeout':5})
            bid, raw, attempts = a.choose([{'role':'system', 'content':'Rules'},
                                           {'role':'user','content':'Choose bid'}], balance=70)
            self.assertEqual(bid,65)
            self.assertEqual(attempts,1)
            self.assertEqual(Handler.received[0]['model'],'qwen2.5:7b')
            self.assertFalse(Handler.received[0]['stream'])
            self.assertEqual(Handler.received[0]['format'],'json')
            self.assertEqual(Handler.received[0]['options']['temperature'],.7)
            self.assertEqual(len(Handler.received[0]['messages']),2)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)


if __name__=='__main__': unittest.main()
