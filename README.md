# Middleware de Impresión - Windows

Este middleware permite recibir archivos PDF y TXT a través de HTTP y enviarlos directamente a una impresora en Windows.

## 📁 Estructura del Proyecto

```
middleware/
├── middleware.py           # Punto de entrada principal
├── app.py                 # Factory de aplicación Flask
├── config.py              # Configuración centralizada
├── requirements.txt       # Dependencias del proyecto
├── routes/
### Resumen

Estas instrucciones cubren la preparación mínima en Windows para que el middleware funcione en varias máquinas locales. Las dependencias nativas requeridas por el proyecto son:

# Middleware de Impresión - Windows

Este middleware recibe archivos (PDF y TXT) por HTTP y los envía a una impresora en Windows.

## Estructura del proyecto

```
Middleware/
├── middleware.py           # Punto de entrada (arranca la app y verifica wkhtml)
├── app.py                  # Factory Flask
├── config.py               # Configuración y utilidades (detección de IP, rutas, timeouts)
├── impresoraConf.py       # Obtener/guardar impresora predeterminada
├── requirements.txt        # Dependencias Python
├── routes/
│   ├── __init__.py
│   └── main.py             # Endpoints: /, /print-pdf, /print/label, /printers, /impresora/predeterminada
├── services/
│   ├── __init__.py
│   └── print_service.py    # Lógica de impresión (SumatraPDF, PowerShell, imgkit, WeasyPrint)
├── templates/
│   └── label.html          # Plantilla para etiquetas
├── utils/
│   ├── validation.py      # Validaciones de payload y sistema
│   └── wkhtml_check.py    # Verifica/encuentra wkhtmltoimage y configura imgkit
└── test_upload.ps1         # Script PowerShell para pruebas
```

---

## Requisitos mínimos (Windows)

- Windows 10/11 (64-bit recomendado)
- Python 3.7+
- PowerShell 5.1+
- SumatraPDF (para impresión de PDFs)
- wkhtmltoimage / wkhtmltopdf (para imgkit -> render HTML->imagen)
- MSYS2 (si usas WeasyPrint; instala cairo/pango/glib/gdk-pixbuf)

> Nota: Algunos paquetes Python (WeasyPrint, imgkit) requieren bibliotecas nativas que no se instalan por pip. Sigue la sección de instalación para los pasos nativos.

---

## Instalación (resumen rápido)

1. Clonar el repositorio:

```powershell
git clone https://github.com/Facudominguezz/Middleware.git
cd Middleware
```

2. Crear y activar entorno virtual:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Instalar dependencias Python:

```powershell
pip install -r requirements.txt
```

4. Instalar SumatraPDF (recomendado via winget):

```powershell
winget install SumatraPDF.SumatraPDF
```

5. Instalar wkhtmltoimage / wkhtmltopdf (para imgkit):
- Descargar el binario para Windows (64-bit si tu Python es 64-bit) desde la web oficial y añadir la carpeta con `wkhtmltoimage.exe` al PATH.
- (Alternativa) `choco install wkhtmltopdf -y` si usas Chocolatey.

6. (Sólo si usas WeasyPrint) Instalar MSYS2 y paquetes nativos:
- Instala MSYS2 desde https://www.msys2.org/
- En "MSYS2 MinGW 64-bit":

```bash
pacman -Syu
# cerrar y reabrir la shell si se solicita
pacman -Su
pacman -S --needed mingw-w64-x86_64-cairo mingw-w64-x86_64-pango mingw-w64-x86_64-gdk-pixbuf2 mingw-w64-x86_64-glib2 mingw-w64-x86_64-fontconfig mingw-w64-x86_64-libjpeg-turbo
```

- Añade `C:\msys64\mingw64\bin` al PATH para que Python encuentre las DLLs.

---

## Endpoints principales

- GET / -> Health check ("Middleware de impresión activo")
- POST /print-pdf -> Recibe archivo (form field `file`) y lo imprime (soporta `.pdf` y `.txt`)
- POST /print/label -> Recibe JSON con datos de etiqueta, genera imagen desde `label.html` y la imprime
- GET /printers -> Lista impresoras detectadas en el sistema (usando WMI)
- POST /impresora/predeterminada -> Establece la impresora predeterminada (JSON:{"nombre":"Nombre Impresora"})

---

## Flujo de impresión (resumen técnico)

- Recepción de archivo en `/print-pdf`:
   - Se valida el archivo con `utils.validation`.
   - Se guarda temporalmente en `tempfile.gettempdir()`.
   - Si es `.txt` se envía con PowerShell (`Get-Content | Out-Printer`).
   - Si es `.pdf` se intenta imprimir con SumatraPDF (rutas configuradas en `config.py`).
   - Si falla, se intenta un respaldo usando `win32api.ShellExecute('print', ...)`.
   - El archivo temporal se programa para eliminación en segundo plano (timeout configurable).

- Etiquetas (`/print/label`):
   - Genera códigos de barras en memoria (PIL + python-barcode).
   - Renderiza `label.html` con `render_template` y luego usa `imgkit` para crear la imagen.
   - Redimensiona la imagen a las dimensiones de la etiqueta y la envía a la impresora.

---

## Comprobaciones útiles

- Verificar wkhtmltoimage:

```powershell
wkhtmltoimage --version
```

- Verificar que Python detecta `gobject` (tras instalar MSYS2 y añadir al PATH):

```powershell
python -c "from ctypes.util import find_library; print('gobject:', find_library('gobject-2.0'))"
```

- Ejecutar el middleware:

```powershell
.venv\Scripts\Activate.ps1
python middleware.py
```

Al iniciarse, `middleware.py` llama a `utils.wkhtml_check.ensure_wkhtml_installed()` y muestra rutas detectadas para `wkhtmltoimage`/`wkhtmltopdf`.

---

## Notas y recomendaciones

- Asegúrate de que la arquitectura (32/64-bit) de las dependencias nativas coincida con tu Python.
- SumatraPDF debe estar instalado y accesible desde alguna de las rutas listadas en `config.RUTAS_SUMATRA` o en el PATH.
- MSYS2 es la forma recomendada para instalar las librerías nativas necesarias por WeasyPrint en Windows; su instalación requiere interacción del usuario.
- El proyecto ya incluye comprobación/ayuda para `wkhtmltoimage` pero no instala automáticamente MSYS2 ni SumatraPDF por seguridad.

---

Si quieres, puedo:
- Añadir un script `setup_windows.ps1` que automatice la creación del `.venv`, `pip install -r requirements.txt` y verifique `wkhtmltoimage` y `SumatraPDF`.
- Añadir una sección de troubleshooting más detallada (logs comunes y soluciones).

Dime cuál prefieres y lo implemento.
```powershell
pip install -r requirements.txt

Deberías obtener una ruta o el nombre de la DLL; si devuelve `None` o vacío, revisa que `C:\msys64\mingw64\bin` esté en el PATH y que la arquitectura (32/64 bit) coincida con tu Python.

Luego prueba ejecutar el middleware:

```powershell
```

### 4. Instalar SumatraPDF (necesario para imprimir PDFs)

Si ves errores relacionados con `gobject-2.0` o `cairo`, revisa los pasos anteriores (MSYS2 y PATH).

---

Si quieres, puedo añadir un script `setup_windows.ps1` automatizado que:

1. Cree y active el entorno `.venv` (no puede activar automáticamente en la sesión del usuario desde un script sin interacción),
2. Instale dependencias pip,
3. Compruebe `wkhtmltoimage` y muestre pasos para instalar MSYS2 y añadir al PATH (la instalación de MSYS2 requiere interacción manual y reinicio por seguridad).

Dime si quieres que lo genere y lo añado al repo.
```powershell
winget install SumatraPDF.SumatraPDF
```

## ⚙️ Configuración

### 1. Configurar la impresora

Edita el archivo `config.py` y cambia el nombre de la impresora:

```python
# Cambiar por el nombre exacto de tu impresora en Windows
PRINTER_NAME = "Brother PT-P950NW"  # ← Cambiar aquí
```

Para encontrar el nombre exacto de tu impresora:
```powershell
Get-WmiObject -Class Win32_Printer | Select-Object Name
```

### 2. Verificar que la impresora funciona

Prueba imprimir un documento desde cualquier aplicación para asegurarte de que la impresora esté correctamente configurada.

# Middleware de Impresión - Windows

Este middleware permite recibir archivos PDF y TXT a través de HTTP y enviarlos directamente a una impresora en Windows.

## 📁 Estructura del Proyecto

```
middleware/
├── middleware.py           # Punto de entrada principal
├── app.py                 # Factory de aplicación Flask
├── config.py              # Configuración centralizada
├── requirements.txt       # Dependencias del proyecto
├── routes/
│   ├── __init__.py
│   └── main.py            # Rutas/endpoints de la API
├── services/
│   ├── __init__.py
│   └── print_service.py   # Lógica de impresión
└── utils/
   ├── __init__.py
   └── validation.py      # Utilidades de validación
```

## 📝 Nota sobre IPs en ejemplos

En este documento verás referencias como:
- `tu-ip-local`: Tu IP local específica (ej: 192.168.1.100, 10.0.0.50, etc.)
- `tu-ip-publica`: Tu IP pública para acceso desde internet
- El middleware detecta automáticamente tu IP local al iniciarse

## 📋 Requisitos del Sistema

- **Sistema Operativo**: Windows 10/11
- **Python**: 3.7 o superior
- **PowerShell**: 5.1 o superior (incluido en Windows)
- **Impresora**: Compatible con Windows (probado con Brother PT-P950NW)

## 🚀 Instalación

Estas instrucciones cubren la preparación mínima en Windows para que el middleware funcione en varias máquinas locales. Las dependencias nativas requeridas por el proyecto son:

- SumatraPDF (para renderizar/imprimir PDFs)
- wkhtmltoimage / wkhtmltopdf (usado por imgkit para generar imágenes/HTML -> imagen)
- MSYS2 (para instalar dependencias nativas que requiere WeasyPrint: cairo, pango, glib, gdk-pixbuf, etc.)

Sigue los pasos a continuación en cada máquina destino.

### 1. Clonar el repositorio

```powershell
git clone https://github.com/Facudominguezz/Middleware.git
cd Middleware
```

### 2. Crear y activar un entorno virtual de Python

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Instalar dependencias de Python

```powershell
pip install -r requirements.txt
```

> Nota: `WeasyPrint` y `imgkit` dependen de librerías nativas que no se instalan por pip. Los pasos siguientes instalan esas dependencias nativas.

### 4. Instalar SumatraPDF (requerido para imprimir PDFs)

Opción recomendada: usar winget si está disponible:

```powershell
winget install SumatraPDF.SumatraPDF
```

Si no tienes winget, descarga e instala SumatraPDF manualmente desde la página oficial y asegúrate de que la instalación agregue el ejecutable (`SumatraPDF.exe`) en el PATH o recuerda la ruta completa.

### 5. Instalar wkhtmltoimage / wkhtmltopdf (para imgkit)

imgkit usa wkhtmltoimage para convertir HTML a imagen. Instálalo así:

Opción A — Descarga manual (recomendado):

1. Ve a la página de descargas oficiales de wkhtmltopdf/wkhtmltoimage y descarga el instalador/precompilado para Windows (elige 64-bit si tu Python es 64-bit).
2. Ejecuta el instalador o extrae el zip y copia el binario `wkhtmltoimage.exe` a una carpeta accesible.
3. Añade la carpeta que contiene `wkhtmltoimage.exe` al PATH de Windows (o colócala junto al ejecutable del proyecto).

Opción B — Chocolatey (si lo usas):

```powershell
# Requiere Chocolatey
choco install wkhtmltopdf -y
```

> Verifica la instalación:

```powershell
wkhtmltoimage --version
```

### 6. Instalar MSYS2 y dependencias nativas para WeasyPrint

WeasyPrint necesita librerías nativas (cairo, pango, glib, gdk-pixbuf, fontconfig). La forma más fiable en Windows es usar MSYS2 y su gestor `pacman`.

1. Descarga e instala MSYS2 desde https://www.msys2.org/ (elige el instalador oficial). Sigue las instrucciones de la web para la instalación inicial.

2. Abre la terminal "MSYS2 MinGW 64-bit" (para sistemas 64-bit) y actualiza el sistema:

```bash
# Dentro de MSYS2 (MinGW 64-bit)
pacman -Syu
# Si la actualización pide reiniciar la shell, ciérrala y vuelve a abrir "MSYS2 MinGW 64-bit"
pacman -Su
```

3. Instala las librerías que necesita WeasyPrint (mingw-w64 para 64-bit):

```bash
pacman -S --needed mingw-w64-x86_64-cairo mingw-w64-x86_64-pango mingw-w64-x86_64-gdk-pixbuf2 mingw-w64-x86_64-glib2 mingw-w64-x86_64-fontconfig mingw-w64-x86_64-libjpeg-turbo
```

4. Añade la carpeta `mingw64\bin` de MSYS2 al PATH de Windows para que Python pueda cargar las DLLs (hazlo con cuidado para no truncar el PATH):

Opciones para agregar al PATH:

- Manual (recomendado): Panel de Control → Sistema → Configuración avanzada del sistema → Variables de entorno → editar `Path` → Añadir `C:\msys64\mingw64\bin`.
- Temporal (solo sesión actual de PowerShell):

```powershell
$env:PATH += ";C:\msys64\mingw64\bin"
```

- Persistente desde PowerShell (usa con precaución; se concatena la variable actual):

```powershell
setx PATH "$($env:PATH);C:\msys64\mingw64\bin"
```

> Reinicia la terminal (o VS Code) después de actualizar el PATH para que los cambios surtan efecto.

### 7. Verificaciones finales

Con el entorno virtual activado y el PATH actualizado, prueba desde Python que las librerías nativas son detectables:

```powershell
# En PowerShell con .venv activado
python -c "from ctypes.util import find_library; print('gobject:', find_library('gobject-2.0'))"
```

Deberías obtener una ruta o el nombre de la DLL; si devuelve `None` o vacío, revisa que `C:\msys64\mingw64\bin` esté en el PATH y que la arquitectura (32/64 bit) coincida con tu Python.

Luego prueba ejecutar el middleware:

```powershell
.venv\Scripts\Activate.ps1
python middleware.py
```

Si ves errores relacionados con `gobject-2.0` o `cairo`, revisa los pasos anteriores (MSYS2 y PATH).

---

Si quieres, puedo añadir un script `setup_windows.ps1` automatizado que:

1. Cree y active el entorno `.venv` (no puede activar automáticamente en la sesión del usuario desde un script sin interacción),
2. Instale dependencias pip,
3. Compruebe `wkhtmltoimage` y muestre pasos para instalar MSYS2 y añadir al PATH (la instalación de MSYS2 requiere interacción manual y reinicio por seguridad).

Dime si quieres que lo genere y lo añado al repo.

## ⚙️ Configuración

### 1. Configurar la impresora

Edita el archivo `config.py` y cambia el nombre de la impresora:

```python
# Cambiar por el nombre exacto de tu impresora en Windows
PRINTER_NAME = "Brother PT-P950NW"  # ← Cambiar aquí
```

Para encontrar el nombre exacto de tu impresora:
```powershell
Get-WmiObject -Class Win32_Printer | Select-Object Name
```

### 2. Verificar que la impresora funciona

Prueba imprimir un documento desde cualquier aplicación para asegurarte de que la impresora esté correctamente configurada.

## 🖥️ Uso

### Iniciar el servidor

```powershell
# Activar entorno virtual
.venv\Scripts\Activate.ps1

# Iniciar el middleware
python middleware.py
```

### 🌐 Configuración de IP del servidor

**El servidor detecta automáticamente tu IP local** y solo acepta conexiones desde la red local para mayor seguridad.

Cuando inicias el middleware verás algo como:
```
🌐 Servidor iniciando en: http://tu-ip-local:5000
📍 IP local detectada: tu-ip-local
🖨️  Impresora configurada: Brother PT-P950NW
📡 Servidor accesible solo desde la red local
```

... (el resto del README permanece igual)
app.run(host='0.0.0.0', port=5000, debug=True)
