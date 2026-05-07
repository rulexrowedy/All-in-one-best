import gc
import time
import os

try:
    import psutil
    def get_memory_usage():
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
except ImportError:
    def get_memory_usage():
        return 0.0

def cleanup_memory():
    gc.collect()

def memory_monitor():
    while True:
        try:
            mem = get_memory_usage()
            if mem > 400:
                gc.collect()
        except:
            pass
        time.sleep(60)

def main():
    print("FB Auto Tool - Comment & Post Automation")
    print(f"Current Memory: {get_memory_usage():.1f} MB")

if __name__ == "__main__":
    main()
