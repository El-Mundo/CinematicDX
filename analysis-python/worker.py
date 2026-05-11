#!/usr/bin/env python3

import signal
import time


running = True


def request_stop(signum=None, frame=None):
    global running
    running = False
    print("Python worker stopping", flush=True)


signal.signal(signal.SIGTERM, request_stop)
signal.signal(signal.SIGINT, request_stop)

print("Python worker started", flush=True)

try:
    while running:
        time.sleep(1)
except KeyboardInterrupt:
    request_stop()

print("Python worker stopped", flush=True)
