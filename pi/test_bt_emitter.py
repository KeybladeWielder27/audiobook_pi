"""Standalone test for the KCX_BT_EMITTER bridge -- run directly with
python3 test_bt_emitter.py, no interactive shell needed."""
print("Importing config...")
import config
print("  OK")

print("Importing display...")
import display
print("  OK")

print("Importing bt_emitter...")
import bt_emitter
print("  OK")

print("Sending AT+GMR? ...")
response = bt_emitter.send_command("AT+GMR?")
print("Response:", response)
