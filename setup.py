from setuptools import setup, find_packages

setup(
    name="bitahub",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "click>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "bitahub=bitahub.cli:main",
        ],
    },
    author="HuZhangchi",
    description="A CLI tool for BitaHub platform",
    python_requires=">=3.8",
)
