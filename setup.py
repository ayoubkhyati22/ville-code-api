from setuptools import setup, find_packages

setup(
    name="villecode-api",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "flask==2.2.3",
        "flask-cors==3.0.10",
        "fuzzywuzzy==0.18.0",
        "python-Levenshtein==0.21.1",
        "gunicorn==20.1.0",
        # Spécifier pandas en dernier avec la version exacte
        "pandas==1.5.3",
    ],
    python_requires=">=3.7",
)