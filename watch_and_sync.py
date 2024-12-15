import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess

class SyncHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(('.txt')):
            try:
                print(f"Detected change in {event.src_path}. Syncing to GitHub...")
                subprocess.run(["git", "add", "*.txt"])
                subprocess.run(["git", "commit", "-m", "Auto-updated .txt files"])
                subprocess.run(["git", "push", "https://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@github.com/Titan6371/opxtitan.git", "HEAD:main"], check=True)

                print(f"Error syncing to GitHub: {e}")

if __name__ == "__main__":
    path_to_watch = os.getcwd()
    event_handler = SyncHandler()
    observer = Observer()
    observer.schedule(event_handler, path=path_to_watch, recursive=False)
    print(f"Watching for changes in {path_to_watch}...")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
