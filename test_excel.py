import pandas as pd

try:
    df_ca = pd.read_excel('BancoMacroCA.xlsx', nrows=10)
    print("--- BancoMacroCA.xlsx ---")
    print(df_ca.head(10))
    print(df_ca.columns.tolist())
except Exception as e:
    print("Error reading CA:", e)

try:
    df_cc = pd.read_excel('BancoMacroCC.xlsx', nrows=10)
    print("\n--- BancoMacroCC.xlsx ---")
    print(df_cc.head(10))
    print(df_cc.columns.tolist())
except Exception as e:
    print("Error reading CC:", e)
