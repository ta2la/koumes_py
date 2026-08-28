# main_window.py

Okno a všechno drátování v něm: postaví čtyři panely, připojí je na sběrnici a
na příkazovou vrstvu.

Co se sem chodí hledat nejčastěji:

- `_on_file_selected` / `_on_dir_changed` - co se stane, když se vybere soubor
  nebo se změní adresář
- `_set_info_path` / `_set_info_viewer` - řádky v info baru pod záhlavím panelu
- `_wire_infobar_clicks` - klik na jméno zobrazovače ho otevře v `p1`
- `_load_view_html` - sestavení URL, se kterou se zobrazovač načte

Drátování tlačítek tady **není** - to je v `toolbar.py`, protože co panel má za
tlačítka je věc `panel.py` a co ta tlačítka dělají je věc příkazů.
