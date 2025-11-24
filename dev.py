import subprocess
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class ReloadHandler(FileSystemEventHandler):
    def __init__(self, command):
        self.command = command
        self.process = self.start_process()

    def start_process(self):
        return subprocess.Popen(self.command)

    def on_any_event(self, event):
        if event.src_path.endswith(".py"):
            print("🔄 File changed! Reloading...")
            self.process.kill()
            self.process = self.start_process()


if __name__ == "__main__":
    handler = ReloadHandler(["python", "main.py"])
    observer = Observer()
    observer.schedule(handler, ".", recursive=True)
    observer.start()

    print("▶️ Bot running with auto-reload")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    handler.process.kill()
    observer.join()
