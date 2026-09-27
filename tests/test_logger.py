from data_collector.logger import KeystrokeLogger

# Test the logger
print("🧪 Testing Keystroke Logger")
print("Type something for 10 seconds...")

logger = KeystrokeLogger()
logger.start_logging()  # Press ESC to stop

# After stopping, show stats
stats = logger.get_keystroke_stats()
print("\n📊 Keystroke Statistics:")
for key, value in stats.items():
    print(f"  {key}: {value}")