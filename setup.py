#!/usr/bin/env python3
"""Setup script for MDFlex."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_path = Path(__file__).parent / "README.md"
long_description = ""
if readme_path.exists():
    long_description = readme_path.read_text(encoding="utf-8")

setup(
    name="mdflex",
    version="1.0.0",
    author="Redz",
    author_email="redzdev@pm.me",
    description="A simplistic, modern markdown reader and editor",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/NoPeRedz/MDFlex",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Text Editors",
        "Topic :: Text Processing :: Markup :: Markdown",
    ],
    python_requires=">=3.9",
    install_requires=[
        "PyQt6>=6.4.0",
        "PyQt6-WebEngine>=6.4.0",
        "markdown>=3.4.0",
        "Pygments>=2.14.0",
    ],
    entry_points={
        "console_scripts": [
            "mdflex=mdflex_app.main:main",
        ],
        "gui_scripts": [
            "mdflex-gui=mdflex_app.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "mdflex_app": ["resources/*", "icons/*.svg"],
    },
    data_files=[
        ("share/applications", ["data/mdflex.desktop"]),
        ("share/icons/hicolor/scalable/apps", ["data/mdflex.svg"]),
    ],
)
