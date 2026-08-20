# -*- coding: utf-8 -*-
"""
Lightweight Local HTTP Development Server for Telegram Mini App
"""
import http.server
import socketserver
import os
import sys

PORT = 8030
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Allow cross-origin requests for testing
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

def run_server():
    # Force output flushing
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("==================================================================")
    print(" JKE TELEGRAM MINI APP LOCAL SERVER")
    print("==================================================================")
    print(f" Serving directory: {DIRECTORY}")
    print(f" Port: {PORT}")
    print(f" Local URL: http://localhost:{PORT}")
    print("==================================================================")
    
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            httpd.server_close()

if __name__ == '__main__':
    run_server()
