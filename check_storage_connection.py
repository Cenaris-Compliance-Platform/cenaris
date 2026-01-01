    #!/usr/bin/env python3
"""Quick Azure Storage connectivity + container check.

- Uses AZURE_STORAGE_CONNECTION_STRING from environment.
- Verifies Blob + ADLS Gen2 clients can connect.
- Ensures required containers exist (documents + ML results).

This script prints NO secrets.

Usage (PowerShell):
    $Env:AZURE_STORAGE_CONNECTION_STRING = "..."
    $Env:AZURE_CONTAINER_NAME = "user-uploads"  # documents/PDFs
    $Env:AZURE_LOGOS_CONTAINER_NAME = "logos"   # org logos/branding
    $Env:AZURE_ML_CONTAINER = "results"
    python ./check_storage_connection.py --create
"""

from __future__ import annotations

import argparse
import os
import sys

# Try to load a local .env file for convenience in dev.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(override=False)
except Exception:
    pass

try:
    from azure.storage.blob import BlobServiceClient
except Exception:
    BlobServiceClient = None

try:
    from azure.storage.filedatalake import DataLakeServiceClient
    from azure.core.exceptions import ResourceNotFoundError
except Exception:
    DataLakeServiceClient = None
    ResourceNotFoundError = Exception


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _ensure_container_or_filesystem(
    *,
    blob_service: BlobServiceClient | None,
    datalake_service: DataLakeServiceClient | None,
    name: str,
) -> tuple[bool, str]:
    """Ensure a container/file-system exists. Returns (ok, message)."""
    if not name:
        return False, "missing container name"

    # Prefer ADLS Gen2 filesystem checks if available.
    if datalake_service is not None:
        fs = datalake_service.get_file_system_client(name)
        try:
            fs.get_file_system_properties()
            return True, f"exists (ADLS file system): {name}"
        except ResourceNotFoundError:
            try:
                datalake_service.create_file_system(name)
                return True, f"created (ADLS file system): {name}"
            except Exception as e:
                # fall back to blob container create below
                adls_error = str(e)
        except Exception as e:
            return False, f"error checking ADLS file system '{name}': {e}"
    else:
        adls_error = None

    if blob_service is None:
        return False, f"cannot create '{name}' (no client); ADLS error: {adls_error}" if adls_error else f"cannot create '{name}' (no client)"

    try:
        container_client = blob_service.get_container_client(name)
        if container_client.exists():
            return True, f"exists (Blob container): {name}"
        blob_service.create_container(name)
        return True, f"created (Blob container): {name}"
    except Exception as e:
        if adls_error:
            return False, f"failed to create '{name}': ADLS error: {adls_error}; Blob error: {e}"
        return False, f"failed to create '{name}': {e}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Azure Storage connection and required containers (documents, logos, ML results)"
    )
    parser.add_argument("--create", action="store_true", help="Create required containers if missing")
    parser.add_argument("--documents-container", default=_env("AZURE_CONTAINER_NAME", "compliance-documents"))
    parser.add_argument("--logos-container", default=_env("AZURE_LOGOS_CONTAINER_NAME"))
    parser.add_argument("--ml-container", default=_env("AZURE_ML_CONTAINER", "results"))
    args = parser.parse_args()

    conn_str = _env("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        print("❌ AZURE_STORAGE_CONNECTION_STRING is not set")
        return 2

    print("Azure Storage connection string: ✓ set")
    print(f"Documents container (AZURE_CONTAINER_NAME): {args.documents_container}")
    if args.logos_container:
        print(f"Logos container (AZURE_LOGOS_CONTAINER_NAME): {args.logos_container}")
    print(f"ML results container (AZURE_ML_CONTAINER): {args.ml_container}")

    blob_service = None
    datalake_service = None

    if BlobServiceClient is None:
        print("⚠️  azure-storage-blob not importable in this env")
    else:
        try:
            blob_service = BlobServiceClient.from_connection_string(conn_str)
            # lightweight call
            _ = next(blob_service.list_containers(results_per_page=1), None)
            print("BlobServiceClient: ✓ connected")
        except Exception as e:
            print(f"❌ BlobServiceClient connect failed: {e}")

    if DataLakeServiceClient is None:
        print("⚠️  azure-storage-file-datalake not importable in this env")
    else:
        try:
            datalake_service = DataLakeServiceClient.from_connection_string(conn_str)
            _ = next(datalake_service.list_file_systems(results_per_page=1), None)
            print("DataLakeServiceClient: ✓ connected")
        except Exception as e:
            print(f"❌ DataLakeServiceClient connect failed: {e}")

    if not args.create:
        print("\n(no --create) Not creating containers. Use --create to ensure they exist.")
        return 0

    print("\nEnsuring required containers exist...")
    ok1, msg1 = _ensure_container_or_filesystem(
        blob_service=blob_service,
        datalake_service=datalake_service,
        name=args.documents_container,
    )
    print(("✓" if ok1 else "❌"), msg1)

    ok2, msg2 = _ensure_container_or_filesystem(
        blob_service=blob_service,
        datalake_service=datalake_service,
        name=args.ml_container,
    )
    print(("✓" if ok2 else "❌"), msg2)

    ok3 = True
    if args.logos_container:
        ok3, msg3 = _ensure_container_or_filesystem(
            blob_service=blob_service,
            datalake_service=datalake_service,
            name=args.logos_container,
        )
        print(("✓" if ok3 else "❌"), msg3)

    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == "__main__":
    raise SystemExit(main())
