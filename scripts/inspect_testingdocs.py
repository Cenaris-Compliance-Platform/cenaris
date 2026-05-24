from pathlib import Path

from pypdf import PdfReader


def main() -> None:
    for path in sorted(Path('testingdocs').glob('*.pdf')):
        try:
            reader = PdfReader(str(path))
            text = ''.join((page.extract_text() or '') for page in reader.pages[:2])
            snippet = ' '.join(text.split())[:400]
            if not snippet:
                snippet = '[no extractable text in first 2 pages]'
        except Exception as exc:
            snippet = f'[error: {exc}]'
        print(f'{path.name}: {snippet}')


if __name__ == '__main__':
    main()
