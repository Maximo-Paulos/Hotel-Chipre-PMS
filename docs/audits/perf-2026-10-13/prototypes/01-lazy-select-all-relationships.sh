#!/usr/bin/env bash
# PROTOTIPO DE MEDICIÓN (no mergear tal cual). Cambia las 138 relaciones ORM eager a carga perezosa.
# Ejecutar sobre una COPIA del repo, nunca sobre el árbol de trabajo.
set -euo pipefail
sed -i 's/lazy="joined"/lazy="select"/g; s/lazy="selectin"/lazy="select"/g' app/models/*.py
