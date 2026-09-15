# Plugin Pack per Jarvis

Contiene i 9 plugin descritti nei tuoi documenti, pronti da copiare
nella cartella `plugins/` del tuo repository (es. `jarvis-mio` /
`spark-framework-engine`), più un `PluginManager` corretto.

## Struttura

```
jarvis_plugins_pack/
├── plugin_manager.py       ← sostituisce il tuo PluginManager
├── jarvis_core_stub.py     ← stub minimale per testare i plugin da soli
├── requirements.txt
└── plugins/
    ├── __init__.py         ← NECESSARIO, vedi bug #1 sotto
    ├── calories.py
    ├── pomodoro.py
    ├── smart_home.py
    ├── sysmon.py
    ├── news.py
    ├── file_manager.py
    ├── weather.py
    ├── media.py
    └── notes.py
```

## Come provarli subito

```bash
pip install -r requirements.txt
python jarvis_core_stub.py
```

Questo avvia uno stub minimale di Jarvis, carica tutti i plugin e ne
prova alcuni automaticamente in console.

## Bug corretti rispetto al codice originale

1. **`plugins/__init__.py` mancante** — `PluginManager` faceva
   `importlib.import_module(f"plugins.{module_name}")`, ma senza
   `__init__.py` la cartella `plugins/` non è un pacchetto Python
   valido: su molte installazioni l'import falliva con
   `ModuleNotFoundError: No module named 'plugins'`. Il nuovo
   `plugin_manager.py` lo crea automaticamente se manca.

2. **`file_manager.py` → `clean_downloads`** — il docstring diceva
   "Sposta i file vecchi", ma il codice si limitava a *contare* i
   file senza spostare nulla. Ora sposta davvero i file più vecchi di
   N giorni (default 30) in `Downloads/archivio`.

3. **`file_manager.py` → `empty_trash`** — chiamava
   `send2trash.send2trash("")`, che non svuota il cestino di sistema
   (send2trash serve solo a mandare UN file specifico nel cestino).
   Ora c'è un'implementazione best-effort per Windows (PowerShell
   `Clear-RecycleBin`), macOS (AppleScript su Finder) e Linux
   (svuotamento di `~/.local/share/Trash`). Ho anche aggiunto
   `send_to_trash(path)` per l'uso corretto originale di send2trash.

4. **`sysmon.py` → `kill_process`** — cercava il nome come
   sottostringa di *qualsiasi* processo attivo, col rischio di
   chiudere processi di sistema critici per un match involontario
   (es. chiedere di chiudere "system" avrebbe potuto colpire
   processi delicati). Aggiunta una blacklist di processi protetti e
   il conteggio dei processi effettivamente terminati.

5. **`news.py`** — era solo un placeholder che diceva sempre la
   stessa frase fissa senza mai leggere notizie vere. Ora fa un fetch
   reale da un feed RSS (default ANSA) tramite `feedparser`, con
   fallback pulito se la libreria non è installata o la rete non è
   raggiungibile.

6. **`pomodoro.py`** — il timer non poteva essere interrotto una
   volta avviato. Aggiunto `stop_timer()` e protezione contro timer
   sovrapposti.

7. **`media.py`** — `pyautogui` richiede un ambiente grafico attivo;
   su sistemi senza display (o senza la libreria installata) le
   chiamate potevano sollevare eccezioni non gestite. Aggiunta
   verifica di disponibilità e try/except su ogni azione.

Gli altri plugin (`calories.py`, `smart_home.py`, `weather.py`,
`notes.py`) non avevano bug bloccanti: ho aggiunto solo piccole
validazioni di robustezza (input non numerici, note vuote, timeout
di rete separati dagli altri errori), descritte nei commenti in
cima a ciascun file.

## Integrazione nel tuo progetto

1. Copia `plugins/` (con `__init__.py` incluso) e `plugin_manager.py`
   nella root del tuo progetto Jarvis, sovrascrivendo la vecchia
   cartella `plugins/`.
2. Assicurati che la tua classe `JarvisCore` esponga
   `self.accessibility.speak(text)`, come nello stub incluso.
3. Installa le dipendenze con `pip install -r requirements.txt`.
