import traceback
try:
    from src.masters.designations import designations_bp
    print("designations OK")
except Exception as e:
    traceback.print_exc()

try:
    from src.masters.departments import departments_bp
    print("departments OK")
except Exception as e:
    traceback.print_exc()

try:
    import app
    print("app OK")
except Exception as e:
    traceback.print_exc()

print("DONE")

