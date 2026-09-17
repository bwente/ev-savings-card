"""Create a manual-install archive containing only integration runtime files."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path('custom_components/ev_savings')
Path('dist').mkdir(exist_ok=True)
with ZipFile('dist/ev-savings-integration.zip', 'w', ZIP_DEFLATED) as archive:
    for path in sorted(root.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            archive.write(path, path.as_posix())
print('Created dist/ev-savings-integration.zip')
