
from setuptools import setup, find_packages

setup(
    name="tennis-betting-sota",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "numpy",
        "scikit-learn",
        "xgboost",
        "lightgbm",
        "joblib",
        "pyyaml",
        "textual",
        "rich",
    ],
    entry_points={
        "console_scripts": [
            "tennis=src.ui.app:main",
        ],
    },
)
