"""Crea el primer usuario ADMIN sin credenciales embebidas.

Uso:
    python -m app.scripts.create_admin --email admin@example.com --name "Admin"

La contraseña se solicita de forma interactiva. ``--password`` existe para
automatizaciones controladas, pero no se recomienda porque puede quedar en el
historial del shell.
"""

import argparse
import getpass
import sys

from app.repositories.auth import AuthRepository
from app.services_admin import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(description="Crear un usuario ADMIN en RDS")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", help="Evitar en shells compartidos; si se omite se solicita de forma segura")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Contraseña ADMIN (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Repite la contraseña: ") if not args.password else password
    if password != confirmation:
        parser.error("Las contraseñas no coinciden.")
    if len(password) < 12:
        parser.error("La contraseña debe tener al menos 12 caracteres.")

    try:
        user_id = AuthRepository().create_user_with_role(
            email=args.email.strip().lower(),
            name=args.name.strip(),
            password_hash=hash_password(password),
            role_code="ADMIN",
        )
    except Exception as exc:
        print(f"No se pudo crear el ADMIN: {exc}", file=sys.stderr)
        return 1

    print(f"ADMIN creado correctamente. id_usuario={user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
