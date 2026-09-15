import os
import re
import shutil
import tempfile

PLUGIN_DIRNAME = "raster_caster_plugin"
INCLUDED_FILES = ("README.md", "metadata.txt", "LICENSE")
INCLUDED_SUFFIXES = (".py", ".svg", ".png", ".ico")
INCLUDED_DIRS = ("algorithms",)


def get_version(directory: str) -> str:
    metadata = os.path.join(directory, "metadata.txt")
    reg = "\nversion=(.+)\n"
    version = ""
    with open(metadata, "r") as f:
        m0 = re.search(reg, f.read())
        if m0:
            version = m0.group(1)
    return version


def copy_plugin_files(source_dir: str, target_dir: str) -> None:
    os.makedirs(target_dir, exist_ok=True)
    for entry in os.listdir(source_dir):
        source = os.path.join(source_dir, entry)
        if os.path.isdir(source):
            if entry in INCLUDED_DIRS:
                shutil.copytree(
                    source,
                    os.path.join(target_dir, entry),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
        elif entry in INCLUDED_FILES or entry.endswith(INCLUDED_SUFFIXES):
            shutil.copy2(source, os.path.join(target_dir, entry))


if __name__ == "__main__":
    this_dir = os.path.dirname(os.path.realpath(__file__))
    plugin_version = get_version(this_dir)
    zip_filename = f"{PLUGIN_DIRNAME}.{plugin_version}.zip"

    with tempfile.TemporaryDirectory() as staging_dir:
        copy_plugin_files(this_dir, os.path.join(staging_dir, PLUGIN_DIRNAME))
        build_dir = tempfile.mkdtemp()
        try:
            built_zip = shutil.make_archive(
                os.path.join(build_dir, zip_filename[: -len(".zip")]),
                "zip",
                staging_dir,
                PLUGIN_DIRNAME,
            )
            plugin_zip_path = os.path.join(this_dir, zip_filename)
            shutil.copy2(built_zip, plugin_zip_path)
        finally:
            shutil.rmtree(build_dir, ignore_errors=True)

    print(f"Created {plugin_zip_path}")
