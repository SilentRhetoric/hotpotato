from collections.abc import Sequence
from pathlib import Path
from shutil import rmtree

from beaker import Application

from smart_contracts.hotpotato import app as hot_potato_app


class Lab:
    def __init__(self, apps: Sequence[Application]) -> None:
        self.apps = apps

    def distill(self, output_dir: Path) -> None:
        output_dir = output_dir.resolve()
        if output_dir.exists():
            rmtree(output_dir)
        output_dir.mkdir(exist_ok=False)
        for app in self.apps:
            app_output_dir = output_dir / app.name
            print(f"Exporting {app.name} to {app_output_dir}")
            specification = app.build()
            specification.export(app_output_dir)


my_lab = Lab(
    apps=[hot_potato_app],
)
