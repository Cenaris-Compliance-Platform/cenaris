#!/usr/bin/env python3
"""ADLS debug helper.

NOTE: This is a manual diagnostic script (network I/O).
It must not execute during pytest collection.
"""

import os

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()

    try:
        from azure.storage.filedatalake import DataLakeServiceClient

        conn_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        container = os.getenv('AZURE_ML_CONTAINER', 'results')

        print("=" * 60)
        print("Testing ADLS File Read")
        print("=" * 60)
        print(f"Container: {container}")
        print("Path: compliance-results/2025/11/user_1/compliance_summary.csv")
        print()

        service_client = DataLakeServiceClient.from_connection_string(conn_str)
        file_system_client = service_client.get_file_system_client(container)

        print("Listing files in: compliance-results/2025/11/user_1/")
        try:
            paths = file_system_client.get_paths(path="compliance-results/2025/11/user_1")

            found_files: list[str] = []
            for path in paths:
                if not path.is_directory:
                    found_files.append(path.name)
                    print(f"  ✓ Found: {path.name}")
                    print(f"    Size: {path.content_length} bytes")
                    print(f"    Modified: {path.last_modified}")

            if not found_files:
                print("  ❌ No files found in this path!")
                print("\n  Trying to list parent folder: compliance-results/2025/11/")
                paths = file_system_client.get_paths(path="compliance-results/2025/11")
                for path in paths:
                    print(f"    {path.name} {'[DIR]' if path.is_directory else ''}")

            if found_files:
                print("\n" + "=" * 60)
                print("Reading file content:")
                print("=" * 60)

                file_path = "compliance-results/2025/11/user_1/compliance_summary.csv"
                file_client = service_client.get_file_client(container, file_path)

                download = file_client.download_file()
                content = download.readall().decode('utf-8')

                print(content)
                print("\n✓ File read successfully!")

                import csv
                import io

                print("\n" + "=" * 60)
                print("Parsed Data:")
                print("=" * 60)

                csv_reader = csv.DictReader(io.StringIO(content))
                for row in csv_reader:
                    print(f"  Framework: {row.get('Framework')}")
                    print(f"  Score: {row.get('Compliance_Score')}")
                    print(f"  Status: {row.get('Status')}")
                    print()

        except Exception as e:
            print(f"  ❌ Error: {e}")

            print("\n  Trying to list root of compliance-results/")
            try:
                paths = file_system_client.get_paths(path="compliance-results")
                print("  Contents of compliance-results/:")
                for path in list(paths)[:20]:
                    print(f"    {path.name} {'[DIR]' if path.is_directory else ''}")
            except Exception as e2:
                print(f"  ❌ Error listing root: {e2}")

        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
