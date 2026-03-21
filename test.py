print("Testing faster-whisper...")
try:
    from faster_whisper import WhisperModel
    print("Importing model...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()