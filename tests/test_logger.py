from agent.logger import KeystrokeLogger

if __name__ == '__main__':
    # Test the logger
    print("🧪 Testing Keystroke Logger")
    print("Type something for 10 seconds...")

    logger = KeystrokeLogger()
    logger.start_logging()  # Press ESC to stop

    # After stopping, show stats
    stats = logger.get_stats()
    print("\n📊 Keystroke Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")