import pandas as pd
import glob
import json
from datetime import datetime
import locale

# Intenta configurar locale en español pero si no funciona sigue
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES')
    except:
        pass

def parse_date(date_val):
    if pd.isna(date_val):
        return None
    if isinstance(date_val, datetime):
        return date_val
    try:
        return pd.to_datetime(date_val)
    except:
        return None

def main():
    # Leer todos los archivos excel
    files = glob.glob('*.xlsx')
    dfs = []
    
    for f in files:
        try:
            df = pd.read_excel(f)
            
            # Determinar el tipo de cuenta basado en el nombre del archivo
            fname = f.upper()
            if 'CA' in fname and 'CC' not in fname:
                df['AccountType'] = 'CA'
            elif 'CC' in fname and 'CA' not in fname:
                df['AccountType'] = 'CC'
            elif 'CAJA DE AHORRO' in fname:
                df['AccountType'] = 'CA'
            elif 'CUENTA CORRIENTE' in fname:
                df['AccountType'] = 'CC'
            else:
                # Fallback
                if 'CA' in fname:
                    df['AccountType'] = 'CA'
                elif 'CC' in fname:
                    df['AccountType'] = 'CC'
                else:
                    df['AccountType'] = 'CA' # Por defecto si es indescifrable
            
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not dfs:
        print("No se encontraron archivos Excel.")
        return

    df = pd.concat(dfs, ignore_index=True)
    
    # Limpiar
    df = df.dropna(subset=['Fecha', 'Importe'])
    df['Fecha'] = df['Fecha'].apply(parse_date)
    df = df.dropna(subset=['Fecha'])
    df['Importe'] = pd.to_numeric(df['Importe'], errors='coerce')
    df = df.dropna(subset=['Importe'])
    
    # Sort
    df = df.sort_values('Fecha', ascending=False)
    
    # Agrupar
    df['Year'] = df['Fecha'].dt.year
    df['Month'] = df['Fecha'].dt.month
    
    meses_es = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio', 
                7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
    df['MonthName'] = df['Month'].map(meses_es)
    
    # Mapa de CUITs para reemplazo de descripciones (puedes agregar más aquí)
    cuit_map = {
        "30703088534": "MERCADOLIBRE S.R.L."
    }

    # Mapa de renombres por descripción exacta (puedes agregar más aquí)
    descripcion_rename_map = {
        "DBCR 25413 S/CR TASA GRAL": "IMPUESTO SOBRE LOS DEBITOS Y CREDITOS BANCARIOS",
        "DBCR 25413 S/DB TASA GRAL": "IMPUESTO SOBRE LOS DEBITOS Y CREDITOS BANCARIOS",
    }

    # Agrupadores: varias descripciones originales → un único nombre de grupo en el acordeón
    # La descripción original se conserva dentro del detalle de cada ítem
    descripcion_group_map = {
        "COMISION RESUMEN DE CTA FRECUENCIA ESPECIAL": "COMISIONES BANCO MACRO",
        "DEBITO FISCAL IVA BASICO":                   "COMISIONES BANCO MACRO",
        "DGR SELLOS CORDOBA":                         "COMISIONES BANCO MACRO",
        "INTER.ADEL.CC S/ACUERD":                     "COMISIONES BANCO MACRO",
        # Agrega más entradas aquí para futuros agrupadores
    }

    def format_descripcion(desc):
        desc = str(desc)
        # 1. Renombres por descripción exacta
        if desc in descripcion_rename_map:
            return descripcion_rename_map[desc]
        # 2. Mapeo de EGRESO por CUIT
        if desc.startswith("EGRESO:"):
            parts = desc.split('-')
            if len(parts) > 1:
                cuit = parts[-1]
                if cuit in cuit_map:
                    return f"{cuit_map[cuit]} - {cuit}"
        return desc

    # Reemplazar NaN en descripción
    df['Descripción'] = df['Descripción'].fillna('Sin Descripción')
    df['Descripción'] = df['Descripción'].apply(format_descripcion)
    
    df['Nro. Transacción'] = df['Nro. Transacción'].fillna('-')
    
    # Descripciones que siempre deben clasificarse como Compensacion
    compensacion_keywords = [
        'COMPENSACION',
        'COMPENSACIÓN',
        'DB TR $ M.TIT',          # Transferencia mismo titular (débito CC)
        'TRANSFERENCIA MISMO TITULAR',  # Transferencia mismo titular (CA)
    ]

    def clasificar_tipo(row):
        desc = str(row['Descripción']).upper()
        for kw in compensacion_keywords:
            if kw.upper() in desc:
                return 'Compensacion'
        if row['Importe'] > 0:
            return 'Ingreso'
        else:
            return 'Gasto'

    df['Tipo'] = df.apply(clasificar_tipo, axis=1)
    df['ImporteAbs'] = df['Importe'].abs()

    # Columna 'Grupo': igual a 'Descripción' salvo para las descripciones que tienen agrupador
    df['Grupo'] = df['Descripción'].apply(
        lambda d: descripcion_group_map.get(d, d)
    )
    
    # Estructura de salida
    data_by_account = {'CA': [], 'CC': []}
    
    for account_type, account_df in df.groupby('AccountType'):
        if account_type not in data_by_account:
            data_by_account[account_type] = []
            
        data_structure = []
        
        # Group by Year, Month para esta cuenta particular
        for (year, month), group in account_df.groupby(['Year', 'Month'], sort=False):
            month_name = group['MonthName'].iloc[0]
            
            # Clasificaciones de este mes
            ingresos_df = group[group['Tipo'] == 'Ingreso']
            gastos_df = group[group['Tipo'] == 'Gasto']
            compensaciones_df = group[group['Tipo'] == 'Compensacion']
            
            total_ingresos = float(ingresos_df['ImporteAbs'].sum())
            total_gastos = float(gastos_df['ImporteAbs'].sum())
            total_compensaciones = float(compensaciones_df['ImporteAbs'].sum())
            
            def procesar_lista(sub_df):
                lista = []
                # Agrupar por 'Grupo' (que puede ser el nombre de grupo o la descripción misma)
                for grupo, grupo_group in sub_df.groupby('Grupo'):
                    total_desc = float(grupo_group['ImporteAbs'].sum())
                    items = []
                    for _, row in grupo_group.iterrows():
                        items.append({
                            "fecha": row['Fecha'].strftime('%d/%m/%Y'),
                            "nro": str(row['Nro. Transacción']),
                            # Se conserva la descripción ORIGINAL en el detalle
                            "descripción": row['Descripción'],
                            "importe": float(row['ImporteAbs'])
                        })
                    items.sort(key=lambda x: datetime.strptime(x['fecha'], "%d/%m/%Y"), reverse=True)
                    lista.append({
                        # El acordeón muestra el nombre del grupo
                        "descripcion": grupo,
                        "total": total_desc,
                        "items": items
                    })
                lista.sort(key=lambda x: x['total'], reverse=True)
                return lista
            
            ingresos_list = procesar_lista(ingresos_df)
            gastos_list = procesar_lista(gastos_df)
            compensaciones_list = procesar_lista(compensaciones_df)
            
            data_structure.append({
                "year": int(year),
                "month": int(month),
                "monthName": month_name,
                "totalIngresos": total_ingresos,
                "totalGastos": total_gastos,
                "totalCompensaciones": total_compensaciones,
                "balance": total_ingresos - total_gastos,
                "ingresos": ingresos_list,
                "gastos": gastos_list,
                "compensaciones": compensaciones_list
            })
            
        # Sort data by year desc, month desc
        data_structure.sort(key=lambda x: (x['year'], x['month']), reverse=True)
        data_by_account[account_type] = data_structure
        
    json_data = json.dumps(data_by_account)
    
    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="theme-color" content="#0a0a0f">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>Dashboard Financiero · Banco Macro</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Figtree:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/@phosphor-icons/web"></script>
    <style>
        :root {{
            --bg:       #000000;
            --surface:  #121212;
            --surface2: #1e1e1e;
            --surface3: #2a2a2a;
            --border:   rgba(255,255,255,0.15);
            --border2:  rgba(255,255,255,0.25);
            --text:     #ffffff;
            --muted:    #b0b0b0;
            --faint:    #606060;
            --gold:     #ffcc00;
            --gold-dim: rgba(255,204,0,0.15);
            --gold-glow:rgba(255,204,0,0.08);
            --green:    #00ff88;
            --green-dim:rgba(0,255,136,0.15);
            --red:      #ff4444;
            --red-dim:  rgba(255,68,68,0.15);
            --amber:    #ffaa00;
            --amber-dim:rgba(255,170,0,0.15);
            --serif:    'DM Serif Display', Georgia, serif;
            --sans:     'Figtree', system-ui, sans-serif;
            --mono:     'DM Mono', 'Courier New', monospace;
            --radius:   14px;
            --radius-sm:8px;
            --safe-bottom: env(safe-area-inset-bottom, 0px);
        }}

        *, *::before, *::after {{
            margin: 0; padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }}

        html {{ scroll-behavior: smooth; }}

        body {{
            font-family: var(--sans);
            background: var(--bg);
            color: var(--text);
            min-height: 100dvh;
            line-height: 1.5;
            overflow-x: hidden;
            padding-bottom: calc(60px + var(--safe-bottom));
        }}

        /* Noise texture overlay */
        body::before {{
            content: '';
            position: fixed;
            inset: 0;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
            pointer-events: none;
            z-index: 0;
            opacity: 0.6;
        }}

        /* Header */
        header {{
            position: sticky;
            top: 0;
            z-index: 100;
            background: rgba(10,10,15,0.88);
            backdrop-filter: blur(20px) saturate(1.4);
            -webkit-backdrop-filter: blur(20px) saturate(1.4);
            border-bottom: 1px solid var(--border);
        }}

        .header-inner {{
            max-width: 700px;
            margin: 0 auto;
            padding: 0.85rem 1.25rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }}

        .brand {{ display: flex; align-items: center; gap: 0.6rem; }}

        .brand-icon {{
            width: 34px; height: 34px;
            border-radius: 9px;
            background: var(--gold-dim);
            border: 1px solid rgba(201,168,76,0.3);
            display: flex; align-items: center; justify-content: center;
            color: var(--gold);
            font-size: 1rem;
            flex-shrink: 0;
        }}

        .brand-text {{
            font-family: var(--serif);
            font-size: 1.05rem;
            color: var(--text);
            letter-spacing: -0.01em;
            line-height: 1.2;
        }}

        .brand-sub {{
            font-family: var(--sans);
            font-size: 0.62rem;
            color: var(--muted);
            font-weight: 400;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}

        .global-pills {{
            display: flex;
            gap: 0.4rem;
            flex-wrap: wrap;
            justify-content: flex-end;
        }}

        .gpill {{
            display: flex; align-items: center; gap: 0.3rem;
            padding: 0.28rem 0.6rem;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 600;
            font-family: var(--mono);
            border: 1px solid transparent;
            white-space: nowrap;
        }}
        .gpill.inc {{ background: var(--green-dim); color: var(--green); border-color: rgba(74,222,128,0.2); }}
        .gpill.exp {{ background: var(--red-dim);   color: var(--red);   border-color: rgba(248,113,113,0.2); }}
        .gpill.cmp {{ background: var(--amber-dim); color: var(--amber); border-color: rgba(251,191,36,0.2); }}

        /* Layout */
        .container {{
            max-width: 700px;
            margin: 0 auto;
            padding: 1.1rem 0.875rem;
            position: relative;
            z-index: 1;
        }}

        /* Account Tabs */
        .account-tabs {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.6rem;
            margin-bottom: 1.25rem;
        }}

        .acc-btn {{
            padding: 0.8rem 1rem;
            border-radius: var(--radius-sm);
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--muted);
            font-family: var(--sans);
            font-size: 0.83rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex; align-items: center; justify-content: center; gap: 0.4rem;
        }}

        .acc-btn i {{ font-size: 1rem; }}
        .acc-btn:active {{ transform: scale(0.97); }}
        .acc-btn.active {{
            background: var(--gold-dim);
            border-color: rgba(201,168,76,0.4);
            color: var(--gold);
        }}

        /* Month Accordion */
        .month-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            margin-bottom: 0.65rem;
            overflow: hidden;
            transition: border-color 0.2s;
        }}

        .month-card.open {{ border-color: var(--border2); }}

        .month-header {{
            width: 100%;
            background: none; border: none;
            color: var(--text);
            font-family: var(--sans);
            cursor: pointer;
            padding: 0.9rem 1.1rem;
            display: flex; flex-direction: column; gap: 0.7rem;
            text-align: left;
            transition: background 0.15s;
        }}

        .month-header:active {{ background: var(--surface2); }}

        .month-header-top {{
            display: flex; align-items: center; justify-content: space-between;
        }}

        .month-label {{ display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }}
        .month-label i {{ font-size: 0.9rem; color: var(--gold); opacity: 0.8; }}

        .month-name {{
            font-family: var(--serif);
            font-size: 1.25rem;
            color: var(--text);
            letter-spacing: 0.05em;
            text-transform: uppercase;
            font-weight: 700;
        }}

        .month-chevron {{
            font-size: 1rem;
            color: var(--muted);
            transition: transform 0.3s ease;
            flex-shrink: 0;
        }}

        .month-card.open .month-chevron {{ transform: rotate(180deg); }}

        .month-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.45rem;
        }}

        .mstat {{
            background: var(--surface2);
            border-radius: 8px;
            padding: 0.45rem 0.55rem;
        }}

        .mstat-label {{
            font-size: 0.6rem;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            color: var(--muted);
            font-weight: 600;
        }}

        .mstat-value {{
            font-family: var(--mono);
            font-size: 0.78rem;
            font-weight: 500;
            line-height: 1.3;
            margin-top: 0.1rem;
        }}

        .mstat.inc .mstat-value {{ color: var(--green); }}
        .mstat.exp .mstat-value {{ color: var(--red); }}
        .mstat.cmp .mstat-value {{ color: var(--amber); }}

        .balance-chip {{
            display: inline-flex; align-items: center; gap: 0.25rem;
            padding: 0.18rem 0.55rem;
            border-radius: 999px;
            font-size: 0.68rem; font-weight: 600;
            font-family: var(--mono);
        }}

        .balance-chip.pos {{ background: var(--green-dim); color: var(--green); }}
        .balance-chip.neg {{ background: var(--red-dim);   color: var(--red); }}

        /* Month Content */
        .month-content {{ display: none; border-top: 1px solid var(--border); }}
        .month-content.open {{ display: block; animation: slideDown 0.22s ease; }}

        @keyframes slideDown {{
            from {{ opacity: 0; transform: translateY(-5px); }}
            to   {{ opacity: 1; transform: translateY(0); }}
        }}

        /* Type Tabs */
        .type-tabs {{
            display: flex;
            overflow-x: auto;
            -ms-overflow-style: none; scrollbar-width: none;
            border-bottom: 1px solid var(--border);
            padding: 0 1rem; gap: 0;
        }}
        .type-tabs::-webkit-scrollbar {{ display: none; }}

        .type-tab {{
            flex-shrink: 0;
            padding: 0.75rem 0.9rem;
            font-family: var(--sans);
            font-size: 0.78rem; font-weight: 600;
            color: var(--muted);
            background: none; border: none;
            cursor: pointer; position: relative;
            letter-spacing: 0.02em;
            transition: color 0.2s;
            white-space: nowrap;
        }}

        .type-tab.active {{ color: var(--text); }}
        .type-tab.active::after {{
            content: '';
            position: absolute;
            bottom: 0; left: 0; right: 0;
            height: 2px;
            background: var(--gold);
            border-radius: 2px 2px 0 0;
        }}

        .tab-panel {{ padding: 0.65rem; }}

        /* Group Accordion */
        .group-item {{
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            margin-bottom: 0.45rem;
            overflow: hidden;
            transition: border-color 0.15s;
        }}

        .group-item.open {{ border-color: var(--border2); }}

        .group-header {{
            width: 100%; background: none; border: none;
            color: var(--text); font-family: var(--sans);
            cursor: pointer;
            padding: 0.8rem 0.9rem;
            display: flex; align-items: center; gap: 0.7rem;
            text-align: left;
            transition: background 0.15s;
        }}

        .group-header:active {{ background: var(--surface3); }}

        .group-icon {{
            width: 30px; height: 30px; border-radius: 7px;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.85rem; flex-shrink: 0;
        }}

        .group-icon.inc {{ background: var(--green-dim); color: var(--green); }}
        .group-icon.exp {{ background: var(--red-dim);   color: var(--red); }}
        .group-icon.cmp {{ background: var(--amber-dim); color: var(--amber); }}

        .group-info {{ flex: 1; min-width: 0; }}

        .group-name {{
            font-size: 0.8rem; font-weight: 500;
            color: var(--text);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            line-height: 1.3;
        }}

        .movs-badge {{
            font-size: 0.63rem; color: var(--muted);
            background: var(--surface3);
            padding: 0.08rem 0.35rem; border-radius: 4px; font-weight: 500;
            display: inline-block; margin-top: 0.15rem;
        }}

        .group-right {{
            display: flex; flex-direction: column; align-items: flex-end; gap: 0.2rem;
            flex-shrink: 0;
        }}

        .group-amount {{
            font-family: var(--mono); font-size: 0.87rem; font-weight: 500;
        }}

        .group-amount.inc {{ color: var(--green); }}
        .group-amount.exp {{ color: var(--red); }}
        .group-amount.cmp {{ color: var(--amber); }}

        .group-chevron {{
            font-size: 0.78rem; color: var(--faint);
            transition: transform 0.25s ease;
        }}

        .group-item.open .group-chevron {{ transform: rotate(180deg); }}

        /* Transaction list */
        .group-content {{
            display: none;
            border-top: 1px solid var(--border);
            background: rgba(0,0,0,0.25);
        }}

        .group-content.open {{ display: block; }}

        .tx-list {{ padding: 0.4rem 0.75rem 0.65rem; }}

        .tx-card {{
            display: flex; justify-content: space-between; align-items: flex-start;
            gap: 0.65rem; padding: 0.6rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }}

        .tx-card:last-child {{ border-bottom: none; }}

        .tx-left {{ flex: 1; min-width: 0; }}

        .tx-desc {{
            font-size: 0.77rem; color: var(--text);
            font-weight: 400; line-height: 1.35;
            word-break: break-word;
        }}

        .tx-meta {{
            display: flex; align-items: center; gap: 0.45rem;
            margin-top: 0.2rem; flex-wrap: wrap;
        }}

        .tx-date {{ font-size: 0.67rem; color: var(--muted); font-family: var(--mono); }}
        .tx-nro {{
            font-size: 0.62rem; color: var(--faint); font-family: var(--mono);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 110px;
        }}

        .tx-amount {{
            font-family: var(--mono); font-size: 0.83rem; font-weight: 500;
            flex-shrink: 0;
        }}

        .tx-amount.inc {{ color: var(--green); }}
        .tx-amount.exp {{ color: var(--red); }}
        .tx-amount.cmp {{ color: var(--amber); }}

        .empty-state {{
            padding: 1.75rem 1rem; text-align: center;
            color: var(--muted); font-size: 0.82rem;
        }}

        .empty-state i {{ font-size: 1.75rem; margin-bottom: 0.5rem; display: block; opacity: 0.35; }}

        /* Desktop */
        @media (min-width: 580px) {{
            .container {{ padding: 1.5rem 1.25rem; }}
            .month-header {{ padding: 1.1rem 1.4rem; }}
            .mstat-value {{ font-size: 0.88rem; }}
            .tab-panel {{ padding: 0.9rem; }}
            .group-header {{ padding: 0.9rem 1.1rem; }}
            .group-name {{ font-size: 0.85rem; }}
            .group-amount {{ font-size: 0.95rem; }}
            .tx-list {{ padding: 0.4rem 1rem 0.8rem; }}
            .tx-desc {{ font-size: 0.82rem; }}
            .tx-amount {{ font-size: 0.88rem; }}
        }}

        ::-webkit-scrollbar {{ width: 4px; height: 4px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: var(--faint); border-radius: 2px; }}
    </style>
</head>
<body>

<header>
    <div class="header-inner">
        <div class="brand">
            <div class="brand-icon"><i class="ph ph-bank"></i></div>
            <div>
                <div class="brand-text">Dashboard</div>
                <div class="brand-sub">Banco Macro</div>
            </div>
        </div>
        <div class="global-pills" id="global-pills"></div>
    </div>
</header>

<main class="container">
    <div class="account-tabs">
        <button class="acc-btn active" id="btn-CA" onclick="selectAccount('CA')">
            <i class="ph ph-wallet"></i> Caja de Ahorro
        </button>
        <button class="acc-btn" id="btn-CC" onclick="selectAccount('CC')">
            <i class="ph ph-briefcase"></i> Cta. Corriente
        </button>
    </div>
    <div id="dashboard"></div>
</main>

<script>
    const allData = {json_data};
    let currentAccount = 'CA';

    const fmt = (v) => new Intl.NumberFormat('es-AR', {{style:'currency',currency:'ARS',maximumFractionDigits:0}}).format(v);
    const fmtFull = (v) => new Intl.NumberFormat('es-AR', {{style:'currency',currency:'ARS'}}).format(v);

    function selectAccount(acc) {{
        currentAccount = acc;
        ['CA','CC'].forEach(a => document.getElementById('btn-'+a).classList.toggle('active', a===acc));
        render();
    }}

    function render() {{
        const data = allData[currentAccount] || [];
        const container = document.getElementById('dashboard');
        const pills = document.getElementById('global-pills');

        if (!data.length) {{
            container.innerHTML = '<div class="empty-state"><i class="ph ph-folder-open"></i>Sin datos</div>';
            pills.innerHTML = '';
            return;
        }}

        let gInc=0, gExp=0, gCmp=0;
        data.forEach(m => {{ gInc+=m.totalIngresos; gExp+=m.totalGastos; gCmp+=m.totalCompensaciones; }});

        pills.innerHTML = `
            <span class="gpill inc"><i class="ph ph-trend-up"></i>${{fmt(gInc)}}</span>
            <span class="gpill exp"><i class="ph ph-trend-down"></i>${{fmt(gExp)}}</span>
            <span class="gpill cmp"><i class="ph ph-arrows-left-right"></i>${{fmt(gCmp)}}</span>
        `;

        container.innerHTML = data.map((m, mi) => {{
            const bal = m.balance;
            const chip = `<span class="balance-chip ${{bal>=0?'pos':'neg'}}"><i class="ph ${{bal>=0?'ph-arrow-up':'ph-arrow-down'}}"></i>${{fmtFull(Math.abs(bal))}}</span>`;
            return `
            <div class="month-card" id="mc-${{mi}}">
                <button class="month-header" onclick="toggleMonth(${{mi}})">
                    <div class="month-header-top">
                        <div class="month-label">
                            <i class="ph ph-calendar-blank"></i>
                            <span class="month-name">${{m.monthName}} ${{m.year}}</span>
                            ${{chip}}
                        </div>
                        <i class="ph ph-caret-down month-chevron"></i>
                    </div>
                    <div class="month-stats">
                        <div class="mstat inc"><div class="mstat-label">Ingresos</div><div class="mstat-value">${{fmt(m.totalIngresos)}}</div></div>
                        <div class="mstat exp"><div class="mstat-label">Gastos</div><div class="mstat-value">${{fmt(m.totalGastos)}}</div></div>
                        <div class="mstat cmp"><div class="mstat-label">Compensac.</div><div class="mstat-value">${{fmt(m.totalCompensaciones)}}</div></div>
                    </div>
                </button>
                <div class="month-content" id="mcon-${{mi}}">
                    <div class="type-tabs" id="ttabs-${{mi}}">
                        <button class="type-tab active" onclick="switchTab(${{mi}},'gastos')">Gastos</button>
                        <button class="type-tab" onclick="switchTab(${{mi}},'ingresos')">Ingresos</button>
                        <button class="type-tab" onclick="switchTab(${{mi}},'comp')">Compensaciones</button>
                    </div>
                    <div class="tab-panel" id="tp-${{mi}}-gastos">${{renderGroups(m.gastos,'exp',mi,'gastos')}}</div>
                    <div class="tab-panel" id="tp-${{mi}}-ingresos" style="display:none">${{renderGroups(m.ingresos,'inc',mi,'ingresos')}}</div>
                    <div class="tab-panel" id="tp-${{mi}}-comp" style="display:none">${{renderGroups(m.compensaciones,'cmp',mi,'comp')}}</div>
                </div>
            </div>`;
        }}).join('');
    }}

    function renderGroups(groups, cls, mi, type) {{
        if (!groups || !groups.length) return '<div class="empty-state"><i class="ph ph-receipt"></i>Sin movimientos</div>';
        const iconMap = {{inc:'ph-arrow-up-right', exp:'ph-arrow-down-right', cmp:'ph-arrows-left-right'}};
        const icon = iconMap[cls];
        return groups.map((g, gi) => {{
            const id = `g-${{mi}}-${{type}}-${{gi}}`;
            return `
            <div class="group-item" id="gi-${{id}}">
                <button class="group-header" onclick="toggleGroup('${{id}}')">
                    <div class="group-icon ${{cls}}"><i class="ph ${{icon}}"></i></div>
                    <div class="group-info">
                        <div class="group-name">${{g.descripcion}}</div>
                        <span class="movs-badge">${{g.items.length}} mov${{g.items.length!==1?'s':''}}</span>
                    </div>
                    <div class="group-right">
                        <span class="group-amount ${{cls}}">${{fmtFull(g.total)}}</span>
                        <i class="ph ph-caret-down group-chevron"></i>
                    </div>
                </button>
                <div class="group-content" id="${{id}}">
                    <div class="tx-list">${{renderTxs(g.items, cls)}}</div>
                </div>
            </div>`;
        }}).join('');
    }}

    function renderTxs(items, cls) {{
        return items.map(item => `
            <div class="tx-card">
                <div class="tx-left">
                    <div class="tx-desc">${{item['descripci\u00f3n'] || item.descripcion || '\u2014'}}</div>
                    <div class="tx-meta">
                        <span class="tx-date">${{item.fecha}}</span>
                        <span class="tx-nro">#${{item.nro}}</span>
                    </div>
                </div>
                <div class="tx-amount ${{cls}}">${{fmtFull(item.importe)}}</div>
            </div>
        `).join('');
    }}

    function toggleMonth(mi) {{
        const card = document.getElementById('mc-'+mi);
        const content = document.getElementById('mcon-'+mi);
        const isOpen = card.classList.toggle('open');
        content.classList.toggle('open', isOpen);
    }}

    function toggleGroup(id) {{
        const item = document.getElementById('gi-'+id);
        const content = document.getElementById(id);
        const isOpen = item.classList.toggle('open');
        content.classList.toggle('open', isOpen);
    }}

    function switchTab(mi, tab) {{
        ['gastos','ingresos','comp'].forEach(t => {{
            document.getElementById(`tp-${{mi}}-${{t}}`).style.display = t===tab ? '' : 'none';
        }});
        document.getElementById('ttabs-'+mi).querySelectorAll('.type-tab').forEach((btn,i) => {{
            btn.classList.toggle('active', ['gastos','ingresos','comp'][i]===tab);
        }});
    }}

    if (allData['CA']?.length) selectAccount('CA');
    else if (allData['CC']?.length) selectAccount('CC');
    else selectAccount('CA');
</script>
</body>
</html>
"""
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_template)
        
    print("Dashboard generado exitosamente en 'index.html'.")

if __name__ == '__main__':
    main()
