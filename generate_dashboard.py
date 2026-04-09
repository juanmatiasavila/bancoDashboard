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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Financiero - Banco Macro</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <!-- Phosphor Icons -->
    <script src="https://unpkg.com/@phosphor-icons/web"></script>
    <style>
        :root {{
            --bg-color: #0f172a;
            --surface-color: #1e293b;
            --surface-hover: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-blue: #3b82f6;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --border: #334155;
            --font-main: 'Outfit', sans-serif;
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: var(--font-main);
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.5;
            padding-bottom: 40px;
        }}

        header {{
            background: rgba(30, 41, 59, 0.8);
            backdrop-filter: blur(12px);
            position: sticky;
            top: 0;
            z-index: 50;
            padding: 1.5rem 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 2rem;
            box-shadow: var(--shadow-md);
        }}

        .container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 0 1.5rem;
        }}

        .header-content {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-size: 1.5rem;
            font-weight: 700;
            color: #fff;
        }}

        .brand i {{
            color: var(--accent-blue);
            font-size: 2rem;
        }}

        .balance-summary {{
            display: flex;
            gap: 2rem;
            align-items: center;
            background: var(--surface-color);
            padding: 0.75rem 1.5rem;
            border-radius: 9999px;
            border: 1px solid var(--border);
        }}

        .balance-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.875rem;
            font-weight: 500;
        }}

        .balance-item.success {{ color: var(--success); }}
        .balance-item.danger {{ color: var(--danger); }}
        .balance-item.warning {{ color: var(--warning); }}
        
        /* Account Selector Tab */
        .account-selector {{
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .acc-btn {{
            flex: 1;
            padding: 1rem;
            border-radius: 1rem;
            background: var(--surface-color);
            border: 2px solid var(--border);
            color: var(--text-muted);
            font-family: var(--font-main);
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 0.5rem;
        }}

        .acc-btn:hover {{
            border-color: #475569;
            color: var(--text-main);
        }}

        .acc-btn.active {{
            background: rgba(59, 130, 246, 0.1);
            border-color: var(--accent-blue);
            color: var(--accent-blue);
        }}

        /* Acordeones */
        .accordion-item {{
            margin-bottom: 1.5rem;
            border-radius: 1rem;
            background: var(--surface-color);
            border: 1px solid var(--border);
            overflow: hidden;
            box-shadow: var(--shadow-md);
            transition: all 0.3s ease;
        }}

        .accordion-item:hover {{
            border-color: #475569;
        }}

        .accordion-header {{
            width: 100%;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.5rem;
            background: transparent;
            border: none;
            color: var(--text-main);
            font-family: var(--font-main);
            cursor: pointer;
            transition: background 0.2s ease;
        }}

        .accordion-header:hover {{
            background: var(--surface-hover);
        }}

        .month-title {{
            display: flex;
            align-items: center;
            gap: 1rem;
            font-size: 1.25rem;
            font-weight: 600;
        }}

        .month-stats {{
            display: flex;
            gap: 1.5rem;
            align-items: center;
        }}

        .stat {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }}

        .stat span:first-child {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .stat span:last-child {{
            font-weight: 600;
            font-size: 1.125rem;
        }}

        .stat.inc {{ color: var(--success); }}
        .stat.exp {{ color: var(--danger); }}
        .stat.comp {{ color: var(--warning); }}

        .accordion-icon {{
            font-size: 1.25rem;
            color: var(--text-muted);
            transition: transform 0.3s ease;
        }}
        
        .accordion-header.active .accordion-icon {{
            transform: rotate(180deg);
        }}

        .accordion-content {{
            display: none;
            padding: 0 1.5rem 1.5rem;
            border-top: 1px solid var(--border);
        }}

        .accordion-content.active {{
            display: block;
            animation: fadeIn 0.4s ease;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(-10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* Sub Acordeones (Ingresos / Gastos / Compensaciones) */
        .type-tabs {{
            display: flex;
            gap: 1rem;
            margin-top: 1.5rem;
            margin-bottom: 1rem;
            border-bottom: 2px solid var(--border);
        }}

        .type-tab {{
            padding: 0.75rem 1.5rem;
            font-weight: 600;
            color: var(--text-muted);
            background: none;
            border: none;
            cursor: pointer;
            position: relative;
            font-family: inherit;
            font-size: 1rem;
            transition: color 0.2s;
        }}

        .type-tab:hover {{
            color: var(--text-main);
        }}

        .type-tab.active {{
            color: var(--text-main);
        }}

        .type-tab.active::after {{
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--accent-blue);
            border-radius: 2px 2px 0 0;
        }}

        /* Group Acordeón (Descripción) */
        .group-accordion {{
            margin-bottom: 0.75rem;
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            background: rgba(15, 23, 42, 0.4);
            overflow: hidden;
        }}

        .group-header {{
            width: 100%;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 1.25rem;
            background: transparent;
            border: none;
            color: var(--text-main);
            font-family: inherit;
            cursor: pointer;
            transition: background 0.2s;
        }}

        .group-header:hover {{
            background: rgba(51, 65, 85, 0.5);
        }}

        .group-name {{
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            text-align: left;
        }}

        .group-total-container {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}

        .group-total {{
            font-weight: 600;
            font-family: monospace;
            font-size: 1.1rem;
        }}

        .group-content {{
            display: none;
            padding: 1rem;
            background: rgba(15, 23, 42, 0.8);
            border-top: 1px solid var(--border);
        }}

        .group-content.active {{
            display: block;
        }}

        /* Table */
        .transactions-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }}

        .transactions-table th, .transactions-table td {{
            text-align: left;
            padding: 0.75rem;
            border-bottom: 1px solid rgba(51, 65, 85, 0.4);
        }}

        .transactions-table th {{
            color: var(--text-muted);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }}

        .transactions-table tr:last-child td {{
            border-bottom: none;
        }}
        
        .transactions-table tr:hover {{
            background-color: rgba(51, 65, 85, 0.4);
        }}

        .amount-cell {{
            text-align: right;
            font-family: monospace;
            font-weight: 500;
        }}

        /* Utility */
        .color-success {{ color: var(--success); }}
        .color-danger {{ color: var(--danger); }}
        .color-warning {{ color: var(--warning); }}
        .badge {{
            background: var(--surface-hover);
            padding: 0.2rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .empty-state {{
            padding: 2rem;
            text-align: center;
            color: var(--text-muted);
        }}
    </style>
</head>
<body>

    <header>
        <div class="container header-content">
            <div class="brand">
                <i class="ph ph-bank"></i>
                Dashboard Financiero
            </div>
            <div class="balance-summary" id="global-summary">
                <!-- Se inyecta por JS -->
            </div>
        </div>
    </header>

    <main class="container">
        
        <div class="account-selector" id="account-selector">
            <button class="acc-btn active" id="btn-CA" onclick="selectAccount('CA')">
                <i class="ph ph-wallet"></i> Caja de Ahorro
            </button>
            <button class="acc-btn" id="btn-CC" onclick="selectAccount('CC')">
                <i class="ph ph-briefcase"></i> Cuenta Corriente
            </button>
        </div>

        <div id="dashboard-container">
            <!-- Dashboard items will be rendered here -->
        </div>

    </main>

    <script>
        const allData = {json_data};
        let currentAccount = 'CA'; 

        const formatCurrency = (val) => {{
            return new Intl.NumberFormat('es-AR', {{ style: 'currency', currency: 'ARS' }}).format(val);
        }};

        function selectAccount(acc) {{
            currentAccount = acc;
            
            document.getElementById('btn-CA').classList.remove('active');
            document.getElementById('btn-CC').classList.remove('active');
            
            const activeBtn = document.getElementById('btn-' + acc);
            if (activeBtn) activeBtn.classList.add('active');
            
            renderDashboard();
        }}

        function renderDashboard() {{
            const container = document.getElementById('dashboard-container');
            const summaryContainer = document.getElementById('global-summary');
            
            const data = allData[currentAccount] || [];

            let globalInc = 0;
            let globalExp = 0;
            let globalComp = 0;

            if (data.length === 0) {{
                container.innerHTML = `<div class="empty-state">No se encontraron datos para esta cuenta</div>`;
                summaryContainer.innerHTML = '';
                return;
            }}

            let html = '';

            data.forEach((monthData, mIndex) => {{
                globalInc += monthData.totalIngresos;
                globalExp += monthData.totalGastos;
                globalComp += monthData.totalCompensaciones;

                html += `
                <div class="accordion-item">
                    <button class="accordion-header" onclick="toggleAccordion('month-${{mIndex}}')">
                        <div class="month-title">
                            <i class="ph ph-calendar-blank"></i>
                            ${{monthData.monthName}} ${{monthData.year}}
                        </div>
                        <div class="month-stats">
                            <div class="stat inc">
                                <span>Ingresos</span>
                                <span>${{formatCurrency(monthData.totalIngresos)}}</span>
                            </div>
                            <div class="stat exp">
                                <span>Gastos</span>
                                <span>${{formatCurrency(monthData.totalGastos)}}</span>
                            </div>
                            <div class="stat comp">
                                <span>Compensac.</span>
                                <span>${{formatCurrency(monthData.totalCompensaciones)}}</span>
                            </div>
                            <i class="ph ph-caret-down accordion-icon"></i>
                        </div>
                    </button>
                    <div class="accordion-content" id="month-${{mIndex}}">
                        
                        <div class="type-tabs">
                            <button class="type-tab active" onclick="switchTab(this, 'gastos-${{mIndex}}', 'month-${{mIndex}}')">Gastos</button>
                            <button class="type-tab" onclick="switchTab(this, 'ingresos-${{mIndex}}', 'month-${{mIndex}}')">Ingresos</button>
                            <button class="type-tab" onclick="switchTab(this, 'comp-${{mIndex}}', 'month-${{mIndex}}')">Compensaciones</button>
                        </div>

                        <div id="gastos-${{mIndex}}" class="tab-content" style="display:block;">
                            ${{renderGroupList(monthData.gastos, 'gasto', mIndex)}}
                        </div>

                        <div id="ingresos-${{mIndex}}" class="tab-content" style="display:none;">
                            ${{renderGroupList(monthData.ingresos, 'ingreso', mIndex)}}
                        </div>
                        
                        <div id="comp-${{mIndex}}" class="tab-content" style="display:none;">
                            ${{renderGroupList(monthData.compensaciones, 'compensacion', mIndex)}}
                        </div>

                    </div>
                </div>
                `;
            }});

            container.innerHTML = html;

            summaryContainer.innerHTML = `
                <div class="balance-item success">
                    <i class="ph ph-trend-up"></i>
                    ${{formatCurrency(globalInc)}}
                </div>
                <div class="balance-item danger">
                    <i class="ph ph-trend-down"></i>
                    ${{formatCurrency(globalExp)}}
                </div>
                <div class="balance-item warning" title="Total Compensaciones">
                    <i class="ph ph-arrows-left-right"></i>
                    ${{formatCurrency(globalComp)}}
                </div>
            `;
        }}

        function renderGroupList(groups, type, mIndex) {{
            if (groups.length === 0) return `<div class="empty-state">No hay registros</div>`;
            
            let html = '';
            groups.forEach((g, gIndex) => {{
                let colorClass = type === 'ingreso' ? 'color-success' : 
                                 type === 'gasto' ? 'color-danger' : 'color-warning';
                let icon = type === 'ingreso' ? 'ph-arrow-up-right' : 
                           type === 'gasto' ? 'ph-arrow-down-right' : 'ph-arrows-left-right';
                const id = `${{type}}-${{mIndex}}-${{gIndex}}`;
                
                html += `
                <div class="group-accordion">
                    <button class="group-header" onclick="toggleGroupAccordion('${{id}}')">
                        <div class="group-name">
                            <i class="ph ${{icon}} ${{colorClass}}"></i>
                            ${{g.descripcion}}
                            <span class="badge">${{g.items.length}} movs</span>
                        </div>
                        <div class="group-total-container">
                            <span class="group-total ${{colorClass}}">${{formatCurrency(g.total)}}</span>
                            <i class="ph ph-caret-down accordion-icon text-muted"></i>
                        </div>
                    </button>
                    <div class="group-content" id="${{id}}">
                        <table class="transactions-table">
                            <thead>
                                <tr>
                                    <th>Fecha</th>
                                    <th>Nro. Transacción</th>
                                    <th>Descripción</th>
                                    <th class="amount-cell">Importe</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${{g.items.map(item => `
                                <tr>
                                    <td>${{item.fecha}}</td>
                                    <td>${{item.nro}}</td>
                                    <td>${{item.descripción}}</td>
                                    <td class="amount-cell ${{colorClass}}">${{formatCurrency(item.importe)}}</td>
                                </tr>
                                `).join('')}}
                            </tbody>
                        </table>
                    </div>
                </div>
                `;
            }});
            return html;
        }}

        function toggleAccordion(id) {{
            const content = document.getElementById(id);
            const header = content.previousElementSibling;
            
            content.classList.toggle('active');
            header.classList.toggle('active');
        }}

        function toggleGroupAccordion(id) {{
            const content = document.getElementById(id);
            const header = content.previousElementSibling;
            
            content.classList.toggle('active');
            header.classList.toggle('active');
        }}

        function switchTab(btn, showId, containerId) {{
            // active button
            const siblings = btn.parentElement.children;
            for(let s of siblings) s.classList.remove('active');
            btn.classList.add('active');

            // Find all content tabs inside the current month accordion container
            const currentAccordion = document.getElementById(containerId);
            const allTabs = currentAccordion.querySelectorAll('.tab-content');
            allTabs.forEach(tab => {{
                tab.style.display = 'none';
            }});

            // Show selected
            document.getElementById(showId).style.display = 'block';
        }}

        // Initialize with logic to choose CA or CC
        if (allData['CA'] && allData['CA'].length > 0) {{
            selectAccount('CA');
        }} else if (allData['CC'] && allData['CC'].length > 0) {{
            selectAccount('CC');
        }} else {{
            selectAccount('CA'); // Default if empty
        }}
    </script>
</body>
</html>
"""
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_template)
        
    print("Dashboard generado exitosamente en 'index.html'.")

if __name__ == '__main__':
    main()
