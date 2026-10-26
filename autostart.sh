#!/bin/sh
# /storage/.config/autostart.sh  (bestehende Datei: nur die Zeile unten ergaenzen)
(sleep 10; python3 /storage/.config/iomega-keyd/iomega_keyd.py > /storage/.kodi/temp/iomega_keyd.log 2>&1) &
