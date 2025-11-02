import shutil
import zipfile
from pathlib import Path
from subprocess import run
from typing import Optional

from avocados import __version__


REPO_PATH = Path(__file__).parents[1]
PYTHON_SC2_GITHUB = 'https://github.com/BurnySc2/python-sc2'


def zip_directory(folder_path: Path, output_path: Optional[Path] = None, *, overwrite: bool = True):
    if output_path is None:
        output_path = folder_path.parent / (folder_path.name + '.zip')
    if output_path.exists() and overwrite:
        shutil.rmtree(output_path)
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in folder_path.rglob('*'):
            if file.is_file():
                zipf.write(file, file.relative_to(folder_path))


def build_ladder_zip(scr_path: Path, build_path: Path, *, overwrite: bool = True) -> None:
    zip_path = build_path / f'AvocaDOS_{__version__}'
    if zip_path.exists() and overwrite:
        shutil.rmtree(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = build_path / 'temp'
    temp_path.mkdir(parents=True, exist_ok=True)
    shutil.copytree(scr_path / 'avocados', zip_path / 'avocados', dirs_exist_ok=True)
    shutil.copy('ladder_files/run.py', zip_path / 'run.py')
    run(f'git clone {PYTHON_SC2_GITHUB}', shell=True, cwd=temp_path)
    shutil.copytree(temp_path / 'python-sc2/sc2', zip_path / 'sc2')
    #shutil.rmtree(temp_path / 'python-sc2')
    zip_directory(zip_path, overwrite=overwrite)


if __name__ == "__main__":
    build_ladder_zip(REPO_PATH / 'src', REPO_PATH / 'build')
