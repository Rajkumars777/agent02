import sys
import os
import time

# Add the backend directory to sys.path
backend_dir = r"c:\Users\rajak\Music\Agent02\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from capabilities.desktop import open_app, type_text, press_key, get_screen_size
    
    print(f"Screen Size: {get_screen_size()}")
    
    # Test 1: Open Calculator
    print("Testing: Open Calculator...")
    res = open_app("calculator")
    print(res)
    
    # Wait for app to focus
    time.sleep(2)
    
    # Test 2: Type something
    print("Testing: Typing '6+7='...")
    res = type_text("6+7=")
    print(res)
    
    # Test 3: Press Enter
    # time.sleep(1)
    # print("Testing: Pressing Enter...")
    # res = press_key("enter")
    # print(res)
    
    print("\nVerification Script Completed.")
    
except Exception as e:
    print(f"Error during verification: {e}")
    import traceback
    traceback.print_exc()
