try:
    import pandas
    print("Pandas imported successfully")
except Exception as e:
    print(e)
    import traceback
    traceback.print_exc()
