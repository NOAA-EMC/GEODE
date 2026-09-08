import os
import shutil
import sys

import yaml

AppName = "geode"
GeodeConfigName = f"{AppName}.yaml"


class _ConfigPaths:
    @staticmethod
    def get_package_config_dir() -> str:
        return os.path.realpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "configs")
        )

    @classmethod
    def get_geode_config_path(cls) -> str:
        return os.path.join(cls._get_geode_config_dir(), GeodeConfigName)

    @classmethod
    def _get_geode_config_dir(cls) -> str:
        def _quick_config_check(config_path: str) -> None:
            if not os.path.exists(config_path):
                print(f"Configuration file {config_path} not found. Please create it!")
                sys.exit(1)

            with open(config_path) as config_file:
                conf = yaml.safe_load(config_file)

            if conf["root_dir"] == "":
                print(
                    f"Configuration file {config_path} has an empty root_dir. Please set it correctly!"
                )
                sys.exit(1)

        def _init_config_dir(config_dir: str) -> None:
            if os.path.exists(config_dir):
                return

            os.makedirs(config_dir, exist_ok=True)

            package_config_file = os.path.join(
                cls.get_package_config_dir(), GeodeConfigName
            )
            target_config_file = os.path.join(config_dir, GeodeConfigName)
            if os.path.exists(package_config_file) and not os.path.exists(
                target_config_file
            ):
                shutil.copy(package_config_file, target_config_file)

                print(
                    f"Fresh {GeodeConfigName} copied to {target_config_file}. Customize it!"
                )
                sys.exit(0)

        xdg_config = os.environ.get("XDG_CONFIG_HOME")

        if xdg_config:
            base_dir = os.path.realpath(xdg_config)
        else:
            base_dir = os.path.realpath(
                os.path.join(os.path.expanduser("~"), ".config")
            )

        config_dir = os.path.join(base_dir, AppName)

        _init_config_dir(config_dir)
        _quick_config_check(os.path.join(config_dir, GeodeConfigName))

        return config_dir


class _TestConfigPaths:
    @staticmethod
    def get_package_config_dir() -> str:
        return os.path.realpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "test", "configs")
        )

    @classmethod
    def get_geode_config_path(cls) -> str:
        return os.path.join(cls.get_package_config_dir(), GeodeConfigName)


if "pytest" in sys.modules:
    _config_class = _TestConfigPaths
else:
    _config_class = _ConfigPaths

PackageConfigDir = _config_class.get_package_config_dir()
GeodeConfigPath = _config_class.get_geode_config_path()
