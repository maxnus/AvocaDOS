import shutil
import zipfile
from pathlib import Path
from subprocess import run
from typing import Optional

from avocados import __version__


REPO_PATH = Path(__file__).parents[1]
PYTHON_SC2_GITHUB = 'https://github.com/BurnySc2/python-sc2'


def zip_directory(folder_path: Path, output_path: Optional[Path] = None):
    if output_path is None:
        output_path = folder_path.parent / (folder_path.name + '.zip')
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in folder_path.rglob('*'):
            if file.is_file():
                zipf.write(file, file.relative_to(folder_path))


def build_ladder_zip(scr_path: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(scr_path / 'avocados', zip_path / 'avocados', dirs_exist_ok=True)
    shutil.copy('ladder_files/run.py', zip_path / 'run.py')
    run(f'git clone {PYTHON_SC2_GITHUB}', shell=True, cwd=zip_path)
    shutil.move(zip_path / 'python-sc2/sc2', zip_path / 'sc2')
    shutil.rmtree(zip_path / 'python-sc2')
    zip_directory(zip_path)


if __name__ == "__main__":
    bot_path = REPO_PATH / 'src'
    zip_path = REPO_PATH / f'build/AvocaDOS_{__version__}'
    build_ladder_zip(bot_path, zip_path)
