# Documentación del Proyecto: Dashboard Financiero - Banco Macro

## Contexto y Objetivos del Proyecto
El cliente necesita un "Dashboard" para visualizar y ordenar de manera agrupada el histórico de transacciones bancarias descargadas en formato Excel (`.xlsx`) desde su entidad financiera (Banco Macro).

El objetivo principal es estructurar un caos de transacciones lineales individuales para presentar rápidamente resultados financieros por mes y mostrar en detalle en qué se gastó o ingresó el dinero y de dónde provino exactamente cada peso contabilizado, logrando una interfaz de usuario visualmente pulida, "Premium" (Rich Aesthetics), en modo oscuro (Dark Theme) que asombre al usuario.

## Requerimientos Funcionales y Reglas de Agrupación
El sistema procesa archivos de Excel de Banco Macro con el siguiente formato base:
`Fecha | Nro. Transacción | Descripción | Importe | Saldo`

La lógica de despliegue exige estructurar la información siguiendo exactamente la siguiente jerarquía estilo "Acordeón":
1. **Tipo de Cuenta:** Cuenta Corriente (CC) independiente de Caja de Ahorro (CA).
2. **Fecha:** Año -> Mes (Sección principal, muestra Ingresos/Gastos Totales).
3. **Tipo de Flujo:** Ingresos (Importe > 0) y Gastos (Importe < 0) separados en pestañas.
4. **Grupo de Transacción (Descripción):** Agrupación temporal de todas las transacciones bajo el mismo concepto o "Descripción". Se muestra el total consolidado de plata movida por dicha descripción.
5. **Transacción Individual:** Despliegue en tabla de las transacciones unitarias (`Fecha`, `Nro. Transacción`, `Descripción`, `Importe`) que conforman la suma anterior.

## ¿Por qué se utilizó esta arquitectura? (Python + HTML/JS Inyectado)

### Arquitectura "Estática Inteligente"
El cliente especificó que quería que la web fuera una página estática simple a la cual los datos se le van "subiendo" o actualizando periódicamente conforme descarga los reportes mensuales de Banco Macro. Por lo tanto, en lugar de levantar un entorno *backend* complejo (Node/Express, Django, o Base de Datos SQL), se optó por una arquitectura de **Generación de Sitios Estáticos (SSG)** local manual:

*   **El Procesador (Base de datos):** `generate_dashboard.py` funciona como el cerebro estructurador de la base de datos.
    *   Lee todos los archivos Excel que existan en la carpeta, permitiendo escalabilidad en el tiempo (el usuario solo debe añadir el nuevo Excel de cada mes, y el script recalculará todo el historial automáticamente).
    *   Usa la robusta librería `pandas` para combinar, limpiar y estructurar en diccionarios jerárquicos los datos separados por el tipo de cuenta.
*   **El Visualizador (Frontend Independiente):** En lugar de exportar un archivo `.json` aparte (lo cual traería problemas de "CORS" al intentar ser leído por el navegador de forma local vía `file:///`), el script de Python toma el JSON masivo generado y **lo inyecta dinámicamente** como una variable dentro del código fuente de `.html`.
    *   El resultado es un único archivo compilado mágico e independiente llamado `index.html`. 
    *   Este archivo no requiere servidores locales ni configuraciones; el cliente puede mandarlo por e-mail, abrirlo con doble clic en Windows, o subirlo a cualquier hosting estático barato.

## Lógica Técnica del Procesamiento (Python)
1. **Detección Automática de Cuentas:** El código iterará por todos los `*.xlsx` en el directorio. Clasificará los datos analizando de antemano si en el nombre del archivo dice "CC", "CA", "Caja de Ahorro" o "Cuenta Corriente" para marcar el registro bajo una u otra categoría antes de concatenar y procesar las celdas.
2. **Transformación:** Descarta valores NaN y los limpia para parsear correctamente las Fechas usando `.dt.year` y `.dt.month`.
3. **Estructura Dinámica JSON:** La data es reducida a un gran diccionario organizado de la siguiente forma anidada:
   `{'CA': [{'year': 2026, 'month': 3, 'ingresos': [...], 'gastos': [...]}, ...], 'CC': [...]}`

## Frontend & CSS (HTML Generado)
Dentro del mismo archivo de Python se encuentra la plantilla base (un "Template literal").
- **Estilos:** Se escribió en CSS puro moderno, sin depender de Tailwind CSS o frameworks para asegurar portabilidad e inmediatez de despliegue por parte del cliente. Se utilizan variables lógicas (var(--bg-color)) para un diseño ultra-premium y profesional (tonos `#0f172a`, bordes sutiles, y tipografía moderna `'Outfit'`).
- **Javascript Interno:** Lee la variable `allData` inyectada estáticamente y se encarga de crear HTML dinámico bajo demanda construyendo los fragmentos de los Acordeones. Maneja estados para alternar fácilmente (Tablas "CA/CC" y "Ingresos/Gastos") con transiciones suaves en el CSS.

## Archivos y Mantenibilidad del Sistema
1. **`generate_dashboard.py`**: Único script original de la lógica backend/creador (el que debe ejecutar un Agente si quiere generar o modificar las agrupaciones o estructuras o cálculos matemáticos, y su estilo gráfico).
2. **`index.html`**: Archivo final hiper-compilado; toda modificación en este estático manual (como un estilo CSS) es frágil si se pierde porque se destruirá la próxima vez que se corra el generador. Las reglas de oro de este sistema dictan que los estilos de diseño deben editarse dentro de las strings de Python de `generate_dashboard.py`.
3. **`test_excel.py`**: Script miniatura de lectura y diagnóstico por consola para leer cómo viene formateado un Excel en caso de que Banco Macro rompa/cambie el modelo de sus columnas en un futuro.
4. **Entorno Requerido**: El entorno de trabajo exige `python` instalado, junto a los comandos `pip install pandas openpyxl`.

## 📌 Historial de Cambios y Nuevas Funcionalidades (Registro para Agentes)
**INSTRUCCIÓN CRÍTICA PARA FUTUROS AGENTES:** 
Este documento (`DOCUMENTACION.md`) es la fuente de la verdad (Source of Truth) del proyecto. Siempre que el usuario solicite agregar nuevas funcionalidades, *features* o cambiar la lógica core del sistema, **DEBES obligatoriamente** registrar aquí mismo cada actualización.

Para cada nuevo cambio, debes documentar:
*   **Fecha y Módulo afectado:** Cuándo se hizo y qué parte del código (`generate_dashboard.py`, CSS, lógica de agrupamiento, etc.) fue modificada.
*   **Feature / Cambio:** Qué se agregó o arregló.
*   **Lógica Funcional:** Explicar *cómo* funciona la nueva funcionalidad y *por qué* se diseñó así (su racionalidad arquitectónica).

Esto asegurará que sin importar qué agente de IA continúe trabajando en el futuro, disponga de todo el historial ordenado de cómo ha mutado el código para evitar refactorizaciones cíclicas o roturas indeseadas. Aquí abajo comenzará el registro continuo del proyecto:

### Changelog / Registro de Versiones
- **(Versión Inicial)**: Creación de la arquitectura estática base. Agrupación por Mes y Descripción en `index.html`. Procesamiento automático de Excel de Banco Macro mediante Pandas en `generate_dashboard.py`.
- **(Actualización Automática CA/CC)**: Se agregó la funcionalidad para detectar dinámicamente si los Excels pertenecen a "Caja de Ahorro" (CA) o "Cuenta Corriente" (CC) basándose en su nombre. Se integró una botonera estilo tab en el frontend CSS/JS para navegar ambas cuentas sin recargar la página. Se implementó lógica de resguardo (`escape`) de f-strings en Python mediante `{{` y `}}` en reglas de hover CSS.
- **(Feature: Filtro de Compensaciones)**: Se implementó un filtro condicional en el procesamiento de Python para que toda transacción cuya descripción contenga la palabra "Compensacion" (o variaciones) no altere matemáticamente los Ingresos ni Gastos netos. 
  - **Lógica Funcional**: Estas transacciones entre cuentas propias distorsionaban los balances. Ahora `generate_dashboard.py` les asigna la categoría `"Compensacion"`. En la Interfaz de Usuario, ahora se despliega una tercera y nueva pestaña en naranja/ámbar llamada *Compensaciones*, que utiliza la misma lógica, colores distintos e incorpora sus propios contadores totales independientes en la cabecera, preservando el comportamiento estilo acordeón.
