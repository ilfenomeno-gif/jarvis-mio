"""
Stub minimale di "jarvis_core" usato per provare i plugin da soli,
senza dover avviare l'intero assistente Jarvis.

Uso rapido:
    python jarvis_core_stub.py

Sostituisci pure con la tua vera classe JarvisCore quando integri
questi plugin nel tuo progetto reale (jarvis-mio / spark-framework-engine).
"""

from plugin_manager import PluginManager


class Accessibility:
    def speak(self, text):
        # Nella tua versione reale qui c'è il motore TTS.
        print(f"[JARVIS DICE]: {text}")


class JarvisCore:
    def __init__(self):
        self.accessibility = Accessibility()


if __name__ == "__main__":
    jarvis = JarvisCore()
    manager = PluginManager(jarvis)

    print("\nPlugin caricati:", manager.list_plugins())

    # Alcuni test rapidi (commenta/decommenta quelli che vuoi provare)
    manager.call("pomodoro", "start_timer", minutes=0.05)   # ~3 secondi, per test veloce
    manager.call("calories", "add_food", food_name="Mela", calories=95)
    manager.call("calories", "get_total")
    manager.call("sysmon", "check_status")
    manager.call("notes", "add_note", note_text="Provare integrazione meteo")
    manager.call("notes", "read_notes")
    manager.call("smart_home", "control_device", device_name="Luce Salotto", state=True)

    import time
    time.sleep(4)  # lascia il tempo al timer pomodoro di scattare
