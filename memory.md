# Memoria del Proyecto: Banco Dashboard

Este documento resume la evolución, las decisiones de diseño y las necesidades específicas implementadas en el sistema de Dashboard Financiero para Banco Macro.

## 🎯 Objetivo del Proyecto
Transformar los resúmenes bancarios de Banco Macro (Excel) en un dashboard visual, interactivo y accesible, con un sistema de categorización inteligente.

## 🧠 Lógica de Procesamiento (Python)
Se han implementado reglas dinámicas en `generate_dashboard.py` para limpiar y dar sentido a los datos:

### 1. Mapeo de Egresos (CUITs)
*   **Identificación Automática**: Se detectan patrones como `"EGRESO:ID-CUIT"`.
*   **Traducción de Nombres**: Los CUITs técnicos se traducen a nombres comerciales legibles.
    *   *Ejemplo*: `30703088534` → `MERCADOLIBRE S.R.L.`

### 2. Categorización Inteligente
*   **Compensaciones**: Se fuerzan descripciones como `"DB TR $ M.TIT"` o `"TRANSFERENCIA MISMO TITULAR"` a la categoría de Compensaciones para que no afecten el balance de gastos/ingresos operativos.
*   **Impuestos**: Unificación de descripciones técnicas de tasas bancarias bajo el nombre `"IMPUESTO SOBRE LOS DEBITOS Y CREDITOS BANCARIOS"`.

### 3. Sistema de Agrupación (Comisiones)
*   Se creó un nivel de jerarquía superior llamado `"COMISIONES BANCO MACRO"`.
*   **Funcionamiento**: Agrupa varios conceptos (IVA, Sellos, Frecuencia Especial) bajo un solo título en el dashboard, pero permite ver el detalle original al expandir el elemento.

## 🎨 Diseño y Frontend
El dashboard ha evolucionado hacia una estética **Premium y Accesible**:

### 1. Arquitectura Mobile-First
*   Diseñado específicamente para ser consultado desde el celular de forma cómoda.
*   Uso de "Cards" táctiles y acordeones con áreas de presión generosas.

### 2. Estética "Dark Luxury"
*   **Fondo**: Negro puro (`#000000`) para máximo contraste.
*   **Tipografía**:
    *   `DM Serif Display`: Para una sensación editorial y clásica.
    *   `Figtree`: Para lectura clara de datos técnicos.
*   **Nombres de Meses**: Se muestran en **MAYÚSCULAS** y con tamaño resaltado para diferenciar las secciones rápidamente.

### 3. Accesibilidad para Personas Mayores
*   **Alto Contraste**: Uso de blanco puro sobre negro y colores neón vibrantes para montos (Verde: Ingresos, Rojo: Gastos, Ámbar: Compensaciones).
*   **Jerarquía Clara**: Resumen global en el header y desglose mensual con balances netos resaltados.

## 🚀 Despliegue y Seguridad
*   **Versionado**: Repositorio Git en GitHub.
*   **Publicación**: GitHub Pages ([Enlace](https://juanmatiasavila.github.io/bancoDashboard/)).
*   **Privacidad**: El archivo `.gitignore` excluye permanentemente los archivos `.xlsx`, asegurando que los datos privados nunca se suban al servidor de GitHub.

---
*Última actualización: 9 de abril de 2026*
